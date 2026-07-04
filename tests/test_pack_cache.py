from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tk_pack_builder.pack_cache import PackCache


class PackCacheTest(unittest.TestCase):
    def test_open_payload_cache_invalidates_when_pack_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_path = root / "sample.pack"
            pack_path.write_bytes(b"first")
            cache = PackCache(root / "cache.sqlite3")

            cache.put_open_payload(
                pack_path,
                include_vanilla=False,
                analysis={"packName": "sample.pack"},
                characters={"pack": {"characters": [{"key": "a"}]}},
            )

            cached = cache.get_open_payload(pack_path, include_vanilla=False)
            self.assertIsNotNone(cached)
            self.assertTrue(cached["cache"]["hit"])
            self.assertEqual(cached["characters"]["pack"]["characters"][0]["key"], "a")

            pack_path.write_bytes(b"changed")
            self.assertIsNone(cache.get_open_payload(pack_path, include_vanilla=False))

    def test_asset_cache_round_trips_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_path = root / "sample.pack"
            pack_path.write_bytes(b"pack")
            cache = PackCache(root / "cache.sqlite3")

            cache.put_asset(pack_path, "ui/a.png", "image/png", b"png-data")
            cached = cache.get_asset(pack_path, "ui/a.png")

            self.assertEqual(cached, ("image/png", b"png-data"))

    def test_open_payload_cache_prunes_old_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_path = root / "sample.pack"
            cache = PackCache(root / "cache.sqlite3")

            for index in range(6):
                pack_path.write_bytes(f"pack-{index}".encode("utf-8"))
                cache.put_open_payload(
                    pack_path,
                    include_vanilla=False,
                    analysis={"packName": "sample.pack", "index": index},
                    characters={"pack": {"characters": [{"key": str(index)}]}},
                )

            with cache._connect() as connection:
                count = connection.execute("select count(*) from pack_open_cache").fetchone()[0]

            self.assertEqual(count, 4)


if __name__ == "__main__":
    unittest.main()
