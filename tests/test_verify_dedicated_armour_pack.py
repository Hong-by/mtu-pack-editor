from __future__ import annotations

import unittest

from scripts.verify_dedicated_armour_pack import _read_all_table_rows


class _FakeSession:
    def list_tables(self) -> list[str]:
        return [
            "db/ceos_to_equipment_variants_tables/armours",
            "db/ceos_to_equipment_variants_tables/weapons",
            "db/unrelated_tables/data__",
        ]

    def read_table(self, path: str) -> list[dict[str, str]]:
        return {
            "db/ceos_to_equipment_variants_tables/armours": [
                {"ceos_key": "armour"}
            ],
            "db/ceos_to_equipment_variants_tables/weapons": [
                {"ceos_key": "weapon"}
            ],
        }[path]


class VerifyDedicatedArmourPackTest(unittest.TestCase):
    def test_reads_all_matching_db_table_fragments(self) -> None:
        rows = _read_all_table_rows(
            _FakeSession(),
            "ceos_to_equipment_variants",
        )
        self.assertEqual(
            [row["ceos_key"] for row in rows],
            ["armour", "weapon"],
        )


if __name__ == "__main__":
    unittest.main()
