from __future__ import annotations

import unittest
from pathlib import Path

from tk_pack_builder.adapters import RpfmPackSession


class RpfmPackSessionTest(unittest.TestCase):
    def test_names_prefers_mtu_character_names_table(self) -> None:
        session = RpfmPackSession(
            pack_path=Path("input.pack"),
            client=None,  # type: ignore[arg-type]
            pack_key="pack",
            pack_info={},
            file_infos=[
                {"path": "db/names_tables/data"},
                {"path": "db/names_tables/data__"},
                {"path": "db/names_tables/_mtu_characters_names"},
            ],
        )

        self.assertEqual(
            session._resolve_table_path("names"),
            "db/names_tables/_mtu_characters_names",
        )

    def test_names_falls_back_to_data_double_underscore(self) -> None:
        session = RpfmPackSession(
            pack_path=Path("input.pack"),
            client=None,  # type: ignore[arg-type]
            pack_key="pack",
            pack_info={},
            file_infos=[
                {"path": "db/names_tables/data"},
                {"path": "db/names_tables/data__"},
            ],
        )

        self.assertEqual(
            session._resolve_table_path("names"),
            "db/names_tables/data__",
        )


if __name__ == "__main__":
    unittest.main()
