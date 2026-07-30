from __future__ import annotations

from collections import Counter
from pathlib import Path
import unittest

from tk_pack_builder import ceo_ccd as ceo_ccd_module
from tk_pack_builder.ceo_ccd import (
    CeoCcd,
    CeoCcdError,
    clone_dedicated_armour_ceo,
    initial_ceo_active_ceos,
    rebase_dedicated_armour_ceo_as_regular,
    rebase_dedicated_armour_initial_ceo,
    _write_cauleb128,
)


ROOT = Path(__file__).resolve().parents[1]
POC_CCD = (
    ROOT
    / "tk_pack_builder"
    / "data"
    / "dedicated_armour_pools"
    / "vanilla-poc-mulu-001.ccd"
)
KOREA_CCD = ROOT / "work" / "dedicated_armour_poc" / "korea_base.ceo_data.ccd"
VANILLA_CCD = ROOT / "work" / "dedicated_armour_poc" / "vanilla_base.ceo_data.ccd"


class CeoCcdTest(unittest.TestCase):
    def assert_semantic_round_trip(self, original: bytes) -> None:
        decoded = CeoCcd.from_bytes(original)
        rebuilt = decoded.to_bytes()
        reparsed = CeoCcd.from_bytes(rebuilt)
        self.assertEqual(reparsed.root, decoded.root)
        self.assertEqual(reparsed.record_names, decoded.record_names)
        self.assertEqual(reparsed.strings_utf16.entries, decoded.strings_utf16.entries)
        self.assertEqual(reparsed.strings_utf8.entries, decoded.strings_utf8.entries)
        self.assertEqual(reparsed.to_bytes(), rebuilt)

    def test_cauleb128_examples(self) -> None:
        self.assertEqual(_write_cauleb128(0), b"\x00")
        self.assertEqual(_write_cauleb128(10), b"\x0a")
        self.assertEqual(_write_cauleb128(128), b"\x81\x00")
        self.assertEqual(_write_cauleb128(16_383), b"\xff\x7f")

    def test_poc_ccd_round_trips_semantically(self) -> None:
        self.assert_semantic_round_trip(POC_CCD.read_bytes())

    @unittest.skipUnless(KOREA_CCD.is_file(), "local Korea Add-On CCD fixture is unavailable")
    def test_korea_ccd_round_trips_semantically(self) -> None:
        self.assert_semantic_round_trip(KOREA_CCD.read_bytes())

    @unittest.skipUnless(VANILLA_CCD.is_file(), "local vanilla CCD fixture is unavailable")
    def test_additive_delta_reconstructs_poc_and_is_idempotent(self) -> None:
        vanilla = CeoCcd.from_path(VANILLA_CCD)
        poc = CeoCcd.from_path(POC_CCD)
        target = vanilla.clone()

        stats = target.apply_additive_delta(base=vanilla, augmented=poc)
        self.assertEqual(stats.groups_added, 13)
        self.assertEqual(stats.string_values_added, 16)
        self.assertEqual(stats.array_items_added, 12)

        expected = Counter(poc.all_strings())
        actual = Counter(target.all_strings())
        for key in (
            "hby_poc_ancillary_armour_mulu_dedicated_001",
            "hby_poc_ceo_initial_data_character_mulu_dedicated_001",
        ):
            self.assertEqual(actual[key], expected[key])

        second = target.apply_additive_delta(base=vanilla, augmented=poc)
        self.assertEqual(second.groups_added, 0)
        self.assertEqual(second.string_values_added, 0)
        self.assertEqual(second.array_items_added, 0)
        self.assertEqual(CeoCcd.from_bytes(target.to_bytes()).root, target.root)

    @unittest.skipUnless(
        VANILLA_CCD.is_file() and KOREA_CCD.is_file(),
        "local vanilla/Korea CCD fixtures are unavailable",
    )
    def test_additive_delta_preserves_korea_data(self) -> None:
        vanilla = CeoCcd.from_path(VANILLA_CCD)
        poc = CeoCcd.from_path(POC_CCD)
        korea = CeoCcd.from_path(KOREA_CCD)
        before = Counter(korea.all_strings())
        creation_date = korea.creation_date

        korea.apply_additive_delta(base=vanilla, augmented=poc)
        after = Counter(korea.all_strings())

        self.assertEqual(korea.creation_date, creation_date)
        self.assertTrue(all(after[value] >= count for value, count in before.items()))
        self.assertEqual(after["hby_poc_ancillary_armour_mulu_dedicated_001"], 33)
        self.assertEqual(
            after["hby_poc_ceo_initial_data_character_mulu_dedicated_001"],
            2,
        )
        self.assertEqual(CeoCcd.from_bytes(korea.to_bytes()).root, korea.root)

    @unittest.skipUnless(VANILLA_CCD.is_file(), "local vanilla CCD fixture is unavailable")
    def test_direct_clone_matches_bob_poc_references(self) -> None:
        vanilla = CeoCcd.from_path(VANILLA_CCD)
        poc = CeoCcd.from_path(POC_CCD)
        target = vanilla.clone()

        stats = clone_dedicated_armour_ceo(
            target,
            source_ceo_key="3k_dlc06_ancillary_armour_nanman_king_mulu_unique",
            source_initial_ceo_key=(
                "3k_dlc06_initial_data_character_historical_nanman_king_mulu"
            ),
            new_ceo_key="hby_poc_ancillary_armour_mulu_dedicated_001",
            new_initial_ceo_key=(
                "hby_poc_ceo_initial_data_character_mulu_dedicated_001"
            ),
        )

        self.assertEqual(stats.definition_rows_cloned, 10)
        self.assertEqual(stats.membership_rows_cloned, 3)
        expected = Counter(poc.all_strings())
        actual = Counter(target.all_strings())
        self.assertEqual(
            actual["hby_poc_ancillary_armour_mulu_dedicated_001"],
            expected["hby_poc_ancillary_armour_mulu_dedicated_001"],
        )
        self.assertEqual(
            actual["hby_poc_ceo_initial_data_character_mulu_dedicated_001"],
            expected["hby_poc_ceo_initial_data_character_mulu_dedicated_001"],
        )
        self.assertEqual(CeoCcd.from_bytes(target.to_bytes()).root, target.root)

    @unittest.skipUnless(KOREA_CCD.is_file(), "local Korea Add-On CCD fixture is unavailable")
    def test_direct_clone_supports_optional_mtu_ceo_tables(self) -> None:
        target = CeoCcd.from_path(KOREA_CCD)
        stats = clone_dedicated_armour_ceo(
            target,
            source_ceo_key=(
                "3k_mtu_ancillary_armour_lady_ma_yunlus_armour_unique"
            ),
            source_initial_ceo_key=(
                "3k_mtu_ceo_initial_data_character_historical_lady_ma_yunlu"
            ),
            new_ceo_key="hby_test_armour_ma_yunlu_001",
            new_initial_ceo_key="hby_test_initial_ma_yunlu_001",
        )

        self.assertEqual(stats.definition_rows_cloned, 6)
        strings = Counter(target.all_strings())
        self.assertGreater(strings["hby_test_armour_ma_yunlu_001"], 1)
        self.assertEqual(strings["hby_test_initial_ma_yunlu_001"], 2)
        self.assertEqual(CeoCcd.from_bytes(target.to_bytes()).root, target.root)

    @unittest.skipUnless(KOREA_CCD.is_file(), "local Korea Add-On CCD fixture is unavailable")
    def test_multiple_direct_clones_use_independent_ceo_rows(self) -> None:
        target = CeoCcd.from_path(KOREA_CCD)
        requests = (
            (
                "3k_mtu_ancillary_armour_lady_ma_yunlus_armour_unique",
                "3k_mtu_ceo_initial_data_character_historical_lady_ma_yunlu",
                "hby_test_armour_multi_001",
                "hby_test_initial_multi_001",
            ),
            (
                "3k_dlc06_ancillary_armour_nanman_king_mulu_unique",
                "3k_dlc06_initial_data_character_historical_nanman_king_mulu",
                "hby_test_armour_multi_002",
                "hby_test_initial_multi_002",
            ),
        )

        for source_ceo, source_initial, new_ceo, new_initial in requests:
            clone_dedicated_armour_ceo(
                target,
                source_ceo_key=source_ceo,
                source_initial_ceo_key=source_initial,
                new_ceo_key=new_ceo,
                new_initial_ceo_key=new_initial,
            )

        reopened = CeoCcd.from_bytes(target.to_bytes())
        strings = Counter(reopened.all_strings())
        for _, _, new_ceo, new_initial in requests:
            self.assertGreater(strings[new_ceo], 1)
            self.assertEqual(strings[new_initial], 2)
        self.assertEqual(reopened.root, target.root)

    @unittest.skipUnless(KOREA_CCD.is_file(), "local Korea Add-On CCD fixture is unavailable")
    def test_reads_source_title_and_traits_from_initial_ceo(self) -> None:
        ccd = CeoCcd.from_path(KOREA_CCD)

        active_ceos = initial_ceo_active_ceos(
            ccd,
            "3k_mtu_ceo_initial_data_character_historical_lady_ma_yunlu",
        )

        self.assertIn(
            "3k_mtu_ceo_career_historical_lady_ma_yunlu",
            active_ceos,
        )
        self.assertIn("3k_ytr_ceo_trait_personality_land_alert", active_ceos)
        self.assertIn("3k_main_ceo_trait_personality_brave", active_ceos)
        self.assertIn("3k_main_ceo_trait_personality_loyal", active_ceos)
        self.assertNotIn(
            "3k_main_ceo_permissions_trait_personality_all",
            active_ceos,
        )

    def test_rebases_fixed_armour_initial_with_complete_source_ceo_set(self) -> None:
        pool_ccd = (
            ROOT
            / "tk_pack_builder"
            / "data"
            / "dedicated_armour_pools"
            / "mtu-core-dedicated-armour-032.ccd"
        )
        ccd = CeoCcd.from_path(pool_ccd)
        source_initial = (
            "3k_mtu_ceo_initial_data_character_historical_lady_ma_yunlu"
        )
        source_armour = (
            "3k_mtu_ancillary_armour_lady_ma_yunlus_armour_unique"
        )
        destination_initial = (
            "hby_mtu_ceo_initial_data_character_dedicated_001"
        )
        destination_armour = "hby_mtu_ancillary_armour_dedicated_001"
        source_active = initial_ceo_active_ceos(ccd, source_initial)

        actual = rebase_dedicated_armour_initial_ceo(
            ccd,
            source_initial_ceo_key=source_initial,
            destination_initial_ceo_key=destination_initial,
            source_armour_ceo_key=source_armour,
            destination_armour_ceo_key=destination_armour,
        )

        expected = [
            destination_armour if key == source_armour else key
            for key in source_active
        ]
        self.assertEqual(actual, expected)
        self.assertIn("3k_mtu_ceo_career_historical_lady_ma_yunlu", actual)
        self.assertIn("3k_main_ceo_trait_personality_brave", actual)
        self.assertIn(destination_armour, actual)
        self.assertNotIn(source_armour, actual)
        reopened = CeoCcd.from_bytes(ccd.to_bytes())
        self.assertEqual(
            initial_ceo_active_ceos(reopened, destination_initial),
            expected,
        )

    def test_rebases_fixed_armour_ceo_as_grantable_regular_armour(self) -> None:
        pool_ccd = (
            ROOT
            / "tk_pack_builder"
            / "data"
            / "dedicated_armour_pools"
            / "mtu-core-dedicated-armour-032.ccd"
        )
        ccd = CeoCcd.from_path(pool_ccd)
        source = "3k_main_ancillary_armour_medium_armour_metal_extraordinary"
        destination = "hby_mtu_ancillary_armour_dedicated_001"
        before = Counter(ccd.all_strings())[destination]

        stats = rebase_dedicated_armour_ceo_as_regular(
            ccd,
            source_ceo_key=source,
            destination_ceo_key=destination,
        )

        self.assertGreaterEqual(stats.definition_rows_cloned, 2)
        self.assertGreater(Counter(ccd.all_strings())[destination], before)
        record_map = ceo_ccd_module._top_level_record_map(ccd.root)
        ceo_group = next(
            group
            for group in record_map["CEO_TABLE_POPULATE"][0].groups
            if ceo_ccd_module._group_key(group) == destination
        )
        effect_group = next(
            group
            for group in record_map["EFFECTS_LIST_TABLE_POPULATE"][0].groups
            if ceo_ccd_module._group_key(group) == destination
        )
        ceo_strings = [
            value
            for node in ceo_group
            for nested in node.walk()
            for value in nested.strings()
        ]
        effect_strings = [
            value
            for node in effect_group
            for nested in node.walk()
            for value in nested.strings()
        ]
        self.assertIn("exceptional", ceo_strings)
        self.assertNotIn("unique", ceo_strings)
        self.assertIn(
            "3k_dummy_effect_ceo_subcategory_armour_metal",
            effect_strings,
        )
        self.assertNotIn(
            "3k_dummy_effect_ceo_subcategory_armour_unique",
            effect_strings,
        )
        spawner_key = "hby_mtu_ceo_spawner_armour_dedicated_001"
        self.assertIn(spawner_key, ccd.all_strings())
        spawner_group = next(
            group
            for group in record_map["SPAWNER_TABLE_POPULATE"][0].groups
            if ceo_ccd_module._group_key(group) == spawner_key
        )
        self.assertTrue(
            any(
                value == destination
                for node in spawner_group
                for nested in node.walk()
                for value in nested.strings()
            )
        )
        reopened = CeoCcd.from_bytes(ccd.to_bytes())
        self.assertEqual(reopened.root, ccd.root)

    def test_rejects_unknown_signature(self) -> None:
        with self.assertRaises(CeoCcdError):
            CeoCcd.from_bytes(b"NOPE" + b"\0" * 20)


if __name__ == "__main__":
    unittest.main()
