from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


HAS_EXTENDED_HEADER = 0b0000_0001_0000_0000
HAS_ENCRYPTED_INDEX = 0b0000_0000_1000_0000
HAS_INDEX_WITH_TIMESTAMPS = 0b0000_0000_0100_0000
HAS_ENCRYPTED_DATA = 0b0000_0000_0001_0000

PFH_FILE_TYPES = {
    0: "Boot",
    1: "Release",
    2: "Patch",
    3: "Mod",
    4: "Movie",
}


@dataclass(frozen=True)
class PfhEntry:
    path: str
    size: int
    offset: int
    compressed: bool
    timestamp: int

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "size": self.size,
            "offset": self.offset,
            "compressed": self.compressed,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class DbHeader:
    version: int
    has_guid: bool
    guid: str
    mysterious_byte: bool
    entry_count: int
    header_size: int

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "hasGuid": self.has_guid,
            "guid": self.guid,
            "mysteriousByte": self.mysterious_byte,
            "entryCount": self.entry_count,
            "headerSize": self.header_size,
        }


@dataclass(frozen=True)
class PfhIndex:
    path: str
    version: str
    pack_type: str
    bitmask: int
    packs_count: int
    files_count: int
    packs_index_size: int
    files_index_size: int
    data_offset: int
    entries: list[PfhEntry]

    def to_dict(self, limit: int | None = None) -> dict[str, object]:
        entries = self.entries if limit is None else self.entries[:limit]
        return {
            "path": self.path,
            "version": self.version,
            "packType": self.pack_type,
            "bitmask": self.bitmask,
            "packsCount": self.packs_count,
            "filesCount": self.files_count,
            "packsIndexSize": self.packs_index_size,
            "filesIndexSize": self.files_index_size,
            "dataOffset": self.data_offset,
            "entries": [entry.to_dict() for entry in entries],
        }


def read_pfh_index(path: Path) -> PfhIndex:
    with path.open("rb") as handle:
        magic = handle.read(4).decode("ascii", errors="replace")
        if not magic.startswith("PFH"):
            raise ValueError("Not a Total War PFH pack.")

        pack_type_and_flags = _read_u32(handle)
        pack_type = PFH_FILE_TYPES.get(pack_type_and_flags & 15, f"Unknown({pack_type_and_flags & 15})")
        bitmask = pack_type_and_flags & ~15
        if bitmask & HAS_ENCRYPTED_INDEX:
            raise ValueError("Encrypted PFH indexes are not supported by the lightweight parser.")

        packs_count = _read_u32(handle)
        packs_index_size = _read_u32(handle)
        files_count = _read_u32(handle)
        files_index_size = _read_u32(handle)
        _internal_timestamp = _read_u32(handle)

        extra_header_size = 20 if bitmask & HAS_EXTENDED_HEADER else 0
        if extra_header_size:
            handle.read(extra_header_size)

        packs_index = handle.read(packs_index_size)
        if _count_nulls(packs_index) < packs_count:
            raise ValueError("Pack dependency index is incomplete.")

        files_index = handle.read(files_index_size)
        data_offset = handle.tell()
        cursor = 0
        data_cursor = data_offset
        entries: list[PfhEntry] = []

        for _ in range(files_count):
            size, cursor = _read_u32_from(files_index, cursor)
            timestamp = 0
            if bitmask & HAS_INDEX_WITH_TIMESTAMPS:
                timestamp, cursor = _read_u32_from(files_index, cursor)
            compressed = files_index[cursor] != 0
            cursor += 1
            path_value, cursor = _read_null_terminated(files_index, cursor)
            entries.append(
                PfhEntry(
                    path=path_value.replace("\\", "/"),
                    size=size,
                    offset=data_cursor,
                    compressed=compressed,
                    timestamp=timestamp,
                )
            )
            data_cursor += size

        if cursor != len(files_index):
            raise ValueError("PFH file index was not consumed cleanly.")

    return PfhIndex(
        path=str(path),
        version=magic,
        pack_type=pack_type,
        bitmask=bitmask,
        packs_count=packs_count,
        files_count=files_count,
        packs_index_size=packs_index_size,
        files_index_size=files_index_size,
        data_offset=data_offset,
        entries=entries,
    )


def find_entry(index: PfhIndex, path: str) -> PfhEntry:
    normalized = path.replace("\\", "/").lower()
    for entry in index.entries:
        if entry.path.lower() == normalized:
            return entry
    raise ValueError(f"Packed file not found: {path}")


def read_entry_bytes(pack_path: Path, entry: PfhEntry) -> bytes:
    if entry.compressed:
        raise ValueError(f"Packed file is compressed and needs RPFM decode: {entry.path}")
    with pack_path.open("rb") as handle:
        handle.seek(entry.offset)
        data = handle.read(entry.size)
    if len(data) != entry.size:
        raise ValueError(f"Could not read full packed file: {entry.path}")
    return data


def extract_entry(pack_path: Path, packed_path: str, output_path: Path) -> PfhEntry:
    index = read_pfh_index(pack_path)
    entry = find_entry(index, packed_path)
    data = read_entry_bytes(pack_path, entry)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    return entry


def read_db_header_from_entry(pack_path: Path, packed_path: str) -> tuple[PfhEntry, DbHeader]:
    index = read_pfh_index(pack_path)
    entry = find_entry(index, packed_path)
    data = read_entry_bytes(pack_path, entry)
    return entry, read_db_header(data)


def read_db_header(data: bytes) -> DbHeader:
    cursor = 0
    guid = ""
    has_guid = data[cursor:cursor + 4] == b"\xfd\xfe\xfc\xff"
    if has_guid:
        cursor += 4
        guid, cursor = _read_sized_utf16(data, cursor)

    version = 0
    if data[cursor:cursor + 4] == b"\xfc\xfd\xfe\xff":
        cursor += 4
        version = struct.unpack("<i", data[cursor:cursor + 4])[0]
        cursor += 4

    if cursor + 5 > len(data):
        raise ValueError("DB table header is incomplete.")

    mysterious_byte = data[cursor] != 0
    cursor += 1
    entry_count = struct.unpack("<I", data[cursor:cursor + 4])[0]
    cursor += 4

    return DbHeader(
        version=version,
        has_guid=has_guid,
        guid=guid,
        mysterious_byte=mysterious_byte,
        entry_count=entry_count,
        header_size=cursor,
    )


def _read_u32(handle) -> int:
    data = handle.read(4)
    if len(data) != 4:
        raise ValueError("Unexpected EOF while reading u32.")
    return struct.unpack("<I", data)[0]


def _read_u32_from(data: bytes, cursor: int) -> tuple[int, int]:
    if cursor + 4 > len(data):
        raise ValueError("Unexpected EOF while reading index u32.")
    return struct.unpack("<I", data[cursor:cursor + 4])[0], cursor + 4


def _read_null_terminated(data: bytes, cursor: int) -> tuple[str, int]:
    end = data.find(b"\0", cursor)
    if end == -1:
        raise ValueError("Unterminated PFH index string.")
    return data[cursor:end].decode("utf-8", errors="replace"), end + 1


def _read_sized_utf16(data: bytes, cursor: int) -> tuple[str, int]:
    if cursor + 2 > len(data):
        raise ValueError("Unexpected EOF while reading UTF-16 length.")
    char_len = struct.unpack("<H", data[cursor:cursor + 2])[0]
    byte_len = char_len * 2
    cursor += 2
    end = cursor + byte_len
    if end > len(data):
        raise ValueError("Unexpected EOF while reading UTF-16 string.")
    return data[cursor:end].decode("utf-16-le", errors="replace"), end


def _count_nulls(data: bytes) -> int:
    return data.count(b"\0")
