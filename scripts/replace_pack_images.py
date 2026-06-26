from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".dds", ".tga"}


@dataclass(frozen=True)
class Entry:
    path: str
    size: int
    offset: int
    compressed: bool
    size_index_offset: int


@dataclass(frozen=True)
class PackLayout:
    file_bytes: bytes
    files_index_offset: int
    data_offset: int
    entries: list[Entry]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace uncompressed image files in a Total War PFH pack and write a new pack."
    )
    parser.add_argument("--input", required=True, type=Path, help="Source .pack file.")
    parser.add_argument("--output", required=True, type=Path, help="Output .pack file.")
    parser.add_argument(
        "--replacement-root",
        type=Path,
        help="Folder whose files mirror internal pack paths, for example ui/units/.../*.png.",
    )
    parser.add_argument(
        "--replace",
        action="append",
        default=[],
        metavar="PACK_PATH=LOCAL_FILE",
        help="Single replacement mapping. Can be passed multiple times.",
    )
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if input_path == output_path:
        raise SystemExit("Refusing to overwrite the input pack. Choose a different --output path.")
    if output_path.suffix.lower() != ".pack":
        raise SystemExit("--output must end with .pack")

    layout = read_layout(input_path)
    replacements = collect_replacements(layout, args.replacement_root, args.replace)
    if not replacements:
        raise SystemExit("No replacement files were found.")

    output_bytes, changed = rebuild_pack(layout, replacements)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(output_bytes)

    print(f"Wrote {output_path}")
    print(f"Replaced {changed} image file(s):")
    for path in sorted(replacements):
        print(f"  {path}")
    return 0


def read_layout(pack_path: Path) -> PackLayout:
    data = pack_path.read_bytes()
    cursor = 0
    magic = data[cursor : cursor + 4]
    cursor += 4
    if not magic.startswith(b"PFH"):
        raise SystemExit("Input is not a Total War PFH pack.")

    pack_type_and_flags, cursor = read_u32(data, cursor)
    bitmask = pack_type_and_flags & ~15
    if bitmask & 0b0000_0000_1000_0000:
        raise SystemExit("Encrypted PFH indexes are not supported.")

    _packs_count, cursor = read_u32(data, cursor)
    packs_index_size, cursor = read_u32(data, cursor)
    files_count, cursor = read_u32(data, cursor)
    files_index_size, cursor = read_u32(data, cursor)
    _timestamp, cursor = read_u32(data, cursor)

    if bitmask & 0b0000_0001_0000_0000:
        cursor += 20

    cursor += packs_index_size
    files_index_offset = cursor
    files_index = data[files_index_offset : files_index_offset + files_index_size]
    data_offset = files_index_offset + files_index_size
    index_cursor = 0
    data_cursor = data_offset
    entries: list[Entry] = []

    for _ in range(files_count):
        size_index_offset = index_cursor
        size, index_cursor = read_u32(files_index, index_cursor)
        if bitmask & 0b0000_0000_0100_0000:
            _entry_timestamp, index_cursor = read_u32(files_index, index_cursor)
        compressed = files_index[index_cursor] != 0
        index_cursor += 1
        path, index_cursor = read_null_string(files_index, index_cursor)
        entries.append(
            Entry(
                path=path.replace("\\", "/"),
                size=size,
                offset=data_cursor,
                compressed=compressed,
                size_index_offset=files_index_offset + size_index_offset,
            )
        )
        data_cursor += size

    return PackLayout(data, files_index_offset, data_offset, entries)


def collect_replacements(
    layout: PackLayout, replacement_root: Path | None, explicit_replacements: list[str]
) -> dict[str, Path]:
    pack_paths = {entry.path.lower(): entry for entry in layout.entries}
    replacements: dict[str, Path] = {}

    if replacement_root is not None:
        root = replacement_root.resolve()
        for local_path in root.rglob("*"):
            if not local_path.is_file() or local_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            packed_path = local_path.relative_to(root).as_posix()
            entry = pack_paths.get(packed_path.lower())
            if entry is not None:
                replacements[entry.path] = local_path

    for value in explicit_replacements:
        if "=" not in value:
            raise SystemExit(f"Invalid --replace mapping: {value}")
        packed_path, local_file = value.split("=", 1)
        entry = pack_paths.get(packed_path.replace("\\", "/").lower())
        if entry is None:
            raise SystemExit(f"Packed file not found: {packed_path}")
        replacements[entry.path] = Path(local_file).resolve()

    for packed_path, local_path in replacements.items():
        if not local_path.is_file():
            raise SystemExit(f"Replacement file does not exist for {packed_path}: {local_path}")
        if local_path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise SystemExit(f"Replacement is not a supported image file: {local_path}")
    return replacements


def rebuild_pack(layout: PackLayout, replacements: dict[str, Path]) -> tuple[bytes, int]:
    output = bytearray(layout.file_bytes[: layout.data_offset])
    changed = 0

    for entry in layout.entries:
        replacement = replacements.get(entry.path)
        if replacement is not None:
            if entry.compressed:
                raise SystemExit(f"Cannot replace compressed packed file: {entry.path}")
            entry_data = replacement.read_bytes()
            output[entry.size_index_offset : entry.size_index_offset + 4] = struct.pack("<I", len(entry_data))
            changed += 1
        else:
            entry_data = layout.file_bytes[entry.offset : entry.offset + entry.size]
        output.extend(entry_data)

    return bytes(output), changed


def read_u32(data: bytes, cursor: int) -> tuple[int, int]:
    return struct.unpack("<I", data[cursor : cursor + 4])[0], cursor + 4


def read_null_string(data: bytes, cursor: int) -> tuple[str, int]:
    end = data.find(b"\0", cursor)
    if end == -1:
        raise SystemExit("Unterminated string in PFH file index.")
    return data[cursor:end].decode("utf-8", errors="replace"), end + 1


if __name__ == "__main__":
    raise SystemExit(main())
