from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from tk_pack_builder.pfh import (
    DbHeader,
    PfhEntry,
    PfhIndex,
    find_entry,
    read_db_header,
    read_entry_bytes,
    read_pfh_index,
)


def _build_pfh5(
    *,
    files: list[tuple[str, bytes]] | None = None,
    pack_type: int = 3,
    bitmask_extra: int = 0,
    packs: list[str] | None = None,
) -> bytes:
    """
    Build a minimal PFH5 (Mod) binary in memory.
    files: list of (internal_path, content_bytes)
    """
    files = files or []
    packs = packs or []

    packs_index = b"".join(p.encode("utf-8") + b"\0" for p in packs)

    # Build files index
    files_index = b""
    for path, content in files:
        files_index += struct.pack("<I", len(content))  # size
        files_index += b"\x00"  # not compressed
        files_index += path.encode("utf-8") + b"\0"

    pack_type_and_flags = (pack_type & 15) | bitmask_extra

    header = b"PFH5"
    header += struct.pack("<I", pack_type_and_flags)
    header += struct.pack("<I", len(packs))
    header += struct.pack("<I", len(packs_index))
    header += struct.pack("<I", len(files))
    header += struct.pack("<I", len(files_index))
    header += struct.pack("<I", 0)  # internal timestamp

    data_section = b"".join(content for _, content in files)

    return header + packs_index + files_index + data_section


class ReadPfhIndexTest(unittest.TestCase):
    def test_reads_empty_pack(self) -> None:
        raw = _build_pfh5()
        with tempfile.NamedTemporaryFile(suffix=".pack", delete=False) as f:
            f.write(raw)
            path = Path(f.name)
        try:
            index = read_pfh_index(path)
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(index.version, "PFH5")
        self.assertEqual(index.pack_type, "Mod")
        self.assertEqual(index.files_count, 0)
        self.assertEqual(index.entries, [])

    def test_reads_single_file_entry(self) -> None:
        raw = _build_pfh5(files=[("db/my_table/data__", b"hello")])
        with tempfile.NamedTemporaryFile(suffix=".pack", delete=False) as f:
            f.write(raw)
            path = Path(f.name)
        try:
            index = read_pfh_index(path)
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(index.files_count, 1)
        self.assertEqual(len(index.entries), 1)
        entry = index.entries[0]
        self.assertEqual(entry.path, "db/my_table/data__")
        self.assertEqual(entry.size, 5)
        self.assertFalse(entry.compressed)

    def test_reads_multiple_file_entries(self) -> None:
        raw = _build_pfh5(files=[
            ("db/a/data__", b"aaa"),
            ("db/b/data__", b"bb"),
        ])
        with tempfile.NamedTemporaryFile(suffix=".pack", delete=False) as f:
            f.write(raw)
            path = Path(f.name)
        try:
            index = read_pfh_index(path)
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(index.files_count, 2)
        self.assertEqual(index.entries[0].size, 3)
        self.assertEqual(index.entries[1].size, 2)

    def test_backslash_is_normalised_to_forward_slash(self) -> None:
        # Simulate a Windows path with backslashes embedded
        files_index = struct.pack("<I", 4) + b"\x00" + b"db\\my_table\\data__" + b"\x00"
        packs_index = b""
        pack_type_and_flags = 3
        header = (
            b"PFH5"
            + struct.pack("<I", pack_type_and_flags)
            + struct.pack("<I", 0)
            + struct.pack("<I", len(packs_index))
            + struct.pack("<I", 1)
            + struct.pack("<I", len(files_index))
            + struct.pack("<I", 0)
        )
        raw = header + packs_index + files_index + b"data"
        with tempfile.NamedTemporaryFile(suffix=".pack", delete=False) as f:
            f.write(raw)
            path = Path(f.name)
        try:
            index = read_pfh_index(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(index.entries[0].path, "db/my_table/data__")

    def test_raises_on_non_pfh_magic(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".pack", delete=False) as f:
            f.write(b"NOTAPFHFILE")
            path = Path(f.name)
        try:
            with self.assertRaises(ValueError, msg="Not a Total War PFH pack."):
                read_pfh_index(path)
        finally:
            path.unlink(missing_ok=True)

    def test_raises_on_encrypted_index(self) -> None:
        # HAS_ENCRYPTED_INDEX = 0x80
        raw = _build_pfh5(bitmask_extra=0x80)
        with tempfile.NamedTemporaryFile(suffix=".pack", delete=False) as f:
            f.write(raw)
            path = Path(f.name)
        try:
            with self.assertRaises(ValueError):
                read_pfh_index(path)
        finally:
            path.unlink(missing_ok=True)

    def test_data_offset_is_after_headers_and_indexes(self) -> None:
        raw = _build_pfh5(files=[("db/t/d", b"xyz")])
        with tempfile.NamedTemporaryFile(suffix=".pack", delete=False) as f:
            f.write(raw)
            path = Path(f.name)
        try:
            index = read_pfh_index(path)
        finally:
            path.unlink(missing_ok=True)
        # Data offset should be somewhere after the 24-byte base header
        self.assertGreater(index.data_offset, 24)

    def test_pack_type_release_is_decoded(self) -> None:
        raw = _build_pfh5(pack_type=1)
        with tempfile.NamedTemporaryFile(suffix=".pack", delete=False) as f:
            f.write(raw)
            path = Path(f.name)
        try:
            index = read_pfh_index(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(index.pack_type, "Release")

    def test_to_dict_respects_limit(self) -> None:
        raw = _build_pfh5(files=[
            ("a", b"1"),
            ("b", b"2"),
            ("c", b"3"),
        ])
        with tempfile.NamedTemporaryFile(suffix=".pack", delete=False) as f:
            f.write(raw)
            path = Path(f.name)
        try:
            index = read_pfh_index(path)
        finally:
            path.unlink(missing_ok=True)
        d = index.to_dict(limit=2)
        self.assertEqual(len(d["entries"]), 2)


class FindEntryTest(unittest.TestCase):
    def _make_index(self, paths: list[str]) -> PfhIndex:
        entries = [PfhEntry(path=p, size=1, offset=0, compressed=False, timestamp=0) for p in paths]
        return PfhIndex(
            path="test.pack",
            version="PFH5",
            pack_type="Mod",
            bitmask=0,
            packs_count=0,
            files_count=len(entries),
            packs_index_size=0,
            files_index_size=0,
            data_offset=0,
            entries=entries,
        )

    def test_finds_entry_by_exact_path(self) -> None:
        index = self._make_index(["db/my_table/data__"])
        entry = find_entry(index, "db/my_table/data__")
        self.assertEqual(entry.path, "db/my_table/data__")

    def test_lookup_is_case_insensitive(self) -> None:
        index = self._make_index(["DB/My_Table/data__"])
        entry = find_entry(index, "db/my_table/data__")
        self.assertEqual(entry.path, "DB/My_Table/data__")

    def test_backslash_in_query_is_normalised(self) -> None:
        index = self._make_index(["db/my_table/data__"])
        entry = find_entry(index, "db\\my_table\\data__")
        self.assertEqual(entry.path, "db/my_table/data__")

    def test_raises_when_not_found(self) -> None:
        index = self._make_index(["db/other/data__"])
        with self.assertRaises(ValueError):
            find_entry(index, "db/missing/data__")


class ReadEntryBytesTest(unittest.TestCase):
    def test_reads_correct_bytes_from_pack(self) -> None:
        payload = b"HELLO_WORLD"
        raw = _build_pfh5(files=[("db/t/d", payload)])
        with tempfile.NamedTemporaryFile(suffix=".pack", delete=False) as f:
            f.write(raw)
            path = Path(f.name)
        try:
            index = read_pfh_index(path)
            entry = index.entries[0]
            data = read_entry_bytes(path, entry)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(data, payload)

    def test_raises_when_entry_is_compressed(self) -> None:
        entry = PfhEntry(path="test", size=10, offset=0, compressed=True, timestamp=0)
        with tempfile.NamedTemporaryFile(suffix=".pack", delete=False) as f:
            f.write(b"\x00" * 50)
            path = Path(f.name)
        try:
            with self.assertRaises(ValueError):
                read_entry_bytes(path, entry)
        finally:
            path.unlink(missing_ok=True)

    def test_reads_second_file_at_correct_offset(self) -> None:
        raw = _build_pfh5(files=[
            ("first", b"FIRST"),
            ("second", b"SECOND"),
        ])
        with tempfile.NamedTemporaryFile(suffix=".pack", delete=False) as f:
            f.write(raw)
            path = Path(f.name)
        try:
            index = read_pfh_index(path)
            second = read_entry_bytes(path, index.entries[1])
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(second, b"SECOND")


class ReadDbHeaderTest(unittest.TestCase):
    def _make_header_bytes(
        self,
        *,
        version: int = 0,
        entry_count: int = 5,
        mysterious_byte: bool = False,
        with_guid: bool = False,
        guid: str = "",
        with_version_marker: bool = False,
    ) -> bytes:
        data = b""
        if with_guid:
            data += b"\xfd\xfe\xfc\xff"
            encoded = guid.encode("utf-16-le")
            data += struct.pack("<H", len(guid))
            data += encoded
        if with_version_marker or version > 0:
            data += b"\xfc\xfd\xfe\xff"
            data += struct.pack("<i", version)
        data += b"\x01" if mysterious_byte else b"\x00"
        data += struct.pack("<I", entry_count)
        return data

    def test_reads_minimal_header(self) -> None:
        data = self._make_header_bytes(entry_count=42)
        header = read_db_header(data)
        self.assertEqual(header.entry_count, 42)
        self.assertFalse(header.has_guid)
        self.assertEqual(header.guid, "")
        self.assertEqual(header.version, 0)

    def test_reads_header_with_version_marker(self) -> None:
        data = self._make_header_bytes(version=3, with_version_marker=True, entry_count=10)
        header = read_db_header(data)
        self.assertEqual(header.version, 3)
        self.assertEqual(header.entry_count, 10)

    def test_reads_header_with_guid(self) -> None:
        data = self._make_header_bytes(with_guid=True, guid="test-guid", entry_count=1)
        header = read_db_header(data)
        self.assertTrue(header.has_guid)
        self.assertEqual(header.guid, "test-guid")

    def test_mysterious_byte_true_when_nonzero(self) -> None:
        data = self._make_header_bytes(mysterious_byte=True, entry_count=0)
        header = read_db_header(data)
        self.assertTrue(header.mysterious_byte)

    def test_mysterious_byte_false_when_zero(self) -> None:
        data = self._make_header_bytes(mysterious_byte=False, entry_count=0)
        header = read_db_header(data)
        self.assertFalse(header.mysterious_byte)

    def test_raises_on_incomplete_header(self) -> None:
        with self.assertRaises((ValueError, struct.error)):
            read_db_header(b"\x00\x00")

    def test_header_size_accounts_for_consumed_bytes(self) -> None:
        data = self._make_header_bytes(entry_count=7)
        header = read_db_header(data)
        self.assertEqual(header.header_size, len(data))

    def test_to_dict_contains_all_fields(self) -> None:
        data = self._make_header_bytes(entry_count=3)
        header = read_db_header(data)
        d = header.to_dict()
        self.assertIn("version", d)
        self.assertIn("hasGuid", d)
        self.assertIn("guid", d)
        self.assertIn("mysteriousByte", d)
        self.assertIn("entryCount", d)
        self.assertIn("headerSize", d)


class PfhEntryToDictTest(unittest.TestCase):
    def test_to_dict_contains_expected_keys(self) -> None:
        entry = PfhEntry(path="db/t/d", size=10, offset=100, compressed=False, timestamp=0)
        d = entry.to_dict()
        self.assertEqual(d["path"], "db/t/d")
        self.assertEqual(d["size"], 10)
        self.assertEqual(d["offset"], 100)
        self.assertFalse(d["compressed"])


if __name__ == "__main__":
    unittest.main()
