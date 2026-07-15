from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from tk_pack_builder.recipe import Recipe, StatPatch, recipe_from_dict
from tk_pack_builder.validation import (
    ValidationMessage,
    allow_reference_backed_clone_sources,
    has_errors,
    messages_to_dicts,
    validate,
)


def _make_session(
    *,
    game_key: str = "three_kingdoms",
    tables: list[str] | None = None,
    table_rows: dict[str, list[dict]] | None = None,
    missing_tables: list[str] | None = None,
) -> Any:
    """Build a minimal mock PackSession for validation tests."""
    from tk_pack_builder.analyzer import PackAnalysis

    session = MagicMock()
    session.pack_path = MagicMock()
    session.list_tables.return_value = tables or []

    def _read_table(name, source="pack"):
        if table_rows and name in table_rows:
            return table_rows[name]
        return []

    session.read_table.side_effect = _read_table
    session.metadata.return_value = {"gameKey": game_key}

    return session


def _empty_recipe(**kwargs) -> Recipe:
    data = {"modName": "test"}
    data.update(kwargs)
    return recipe_from_dict(data)


class HasErrorsTest(unittest.TestCase):
    def test_returns_false_when_no_messages(self) -> None:
        self.assertFalse(has_errors([]))

    def test_returns_false_for_only_warnings(self) -> None:
        msgs = [ValidationMessage("warning", "empty_recipe", "nothing here")]
        self.assertFalse(has_errors(msgs))

    def test_returns_true_when_any_error(self) -> None:
        msgs = [
            ValidationMessage("warning", "warn_code", "just a warning"),
            ValidationMessage("error", "err_code", "an error"),
        ]
        self.assertTrue(has_errors(msgs))

    def test_returns_true_for_single_error(self) -> None:
        msgs = [ValidationMessage("error", "some_error", "boom")]
        self.assertTrue(has_errors(msgs))


class MessagesToDictsTest(unittest.TestCase):
    def test_converts_all_fields(self) -> None:
        msg = ValidationMessage("error", "test_code", "test message")
        result = messages_to_dicts([msg])
        self.assertEqual(result, [{"level": "error", "code": "test_code", "message": "test message"}])

    def test_empty_list_returns_empty_list(self) -> None:
        self.assertEqual(messages_to_dicts([]), [])

    def test_multiple_messages(self) -> None:
        msgs = [
            ValidationMessage("error", "a", "msg_a"),
            ValidationMessage("warning", "b", "msg_b"),
        ]
        dicts = messages_to_dicts(msgs)
        self.assertEqual(len(dicts), 2)
        self.assertEqual(dicts[1]["level"], "warning")


class AllowReferenceBackedCloneSourcesTest(unittest.TestCase):
    def _msg(self, code: str, message: str, level: str = "error") -> ValidationMessage:
        return ValidationMessage(level, code, message)

    def test_allows_source_initial_ceo_not_found(self) -> None:
        msgs = [self._msg("invalid_character_clone", "Source initial CEO not found: some_key")]
        result = allow_reference_backed_clone_sources(msgs)
        self.assertEqual(result, [])

    def test_allows_source_age_range_not_found(self) -> None:
        msgs = [self._msg("invalid_character_clone", "Source age range not found: some_key")]
        result = allow_reference_backed_clone_sources(msgs)
        self.assertEqual(result, [])

    def test_allows_source_character_art_rows_not_found(self) -> None:
        msgs = [self._msg("invalid_character_clone", "Source character art rows not found: some_set")]
        result = allow_reference_backed_clone_sources(msgs)
        self.assertEqual(result, [])

    def test_allows_character_template_not_found_for_patch(self) -> None:
        msgs = [self._msg("invalid_character_patch", "Character template not found: some_template")]
        result = allow_reference_backed_clone_sources(msgs)
        self.assertEqual(result, [])

    def test_allows_source_land_unit_not_found(self) -> None:
        msgs = [self._msg("invalid_land_unit_clone", "Source land unit not found: some_unit")]
        result = allow_reference_backed_clone_sources(msgs)
        self.assertEqual(result, [])

    def test_allows_equipment_stat_mapping_not_found(self) -> None:
        msgs = [self._msg("invalid_stat_patch", "Equipment stat mapping not found: some_key")]
        result = allow_reference_backed_clone_sources(msgs)
        self.assertEqual(result, [])

    def test_allows_missing_table_for_stat_patch(self) -> None:
        msgs = [self._msg("invalid_stat_patch", "Required table is missing: melee_weapons")]
        result = allow_reference_backed_clone_sources(msgs)
        self.assertEqual(result, [])

    def test_allows_missing_table_message(self) -> None:
        msgs = [self._msg("missing_table", "Required table is missing: melee_weapons")]
        result = allow_reference_backed_clone_sources(msgs)
        self.assertEqual(result, [])

    def test_keeps_other_errors_unchanged(self) -> None:
        msgs = [
            self._msg("invalid_character_clone", "Some unrelated error"),
            self._msg("duplicate_character_clone", "Duplicate key"),
        ]
        result = allow_reference_backed_clone_sources(msgs)
        self.assertEqual(len(result), 2)

    def test_keeps_warning_messages(self) -> None:
        msgs = [self._msg("empty_recipe", "Recipe has nothing", level="warning")]
        result = allow_reference_backed_clone_sources(msgs)
        self.assertEqual(len(result), 1)

    def test_mixed_allowed_and_blocked(self) -> None:
        msgs = [
            self._msg("invalid_character_clone", "Source initial CEO not found: x"),
            self._msg("duplicate_character_clone", "Duplicate: y"),
        ]
        result = allow_reference_backed_clone_sources(msgs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].code, "duplicate_character_clone")


class ValidateForbiddenKeysTest(unittest.TestCase):
    """Tests for validation() that don't require a real pack session.
    We use a MockPackSession from adapters.
    """

    def _make_mock_session(self) -> Any:
        from pathlib import Path
        from tk_pack_builder.adapters import MockPackSession
        return MockPackSession(
            pack_path=Path("starter.pack"),
            envelope={
                "gameKey": "three_kingdoms",
                "packName": "starter",
                "tables": {
                    "melee_weapons": [],
                    "unit_armour_types": [],
                    "projectiles": [],
                    "ceos_to_equipment_variants_weapons": [],
                    "ceos_to_equipment_variants_armours": [],
                    "missile_weapons": [],
                    "land_units": [],
                    "main_units": [],
                    "character_generation_templates": [],
                    "character_generation_template_game_mode_details": [],
                    "campaign_character_art_sets": [],
                    "campaign_character_arts": [],
                    "character_generation_spawn_age_ranges": [],
                    "ceo_initial_datas": [],
                },
                "loc": {},
                "files": [],
                "metadata": {},
            },
        )

    def test_forbidden_key_new_equipment_produces_error(self) -> None:
        session = self._make_mock_session()
        recipe = recipe_from_dict({"modName": "test", "newEquipment": [{"equipmentKey": "x"}]})
        messages = validate(session, recipe)
        codes = [m.code for m in messages]
        self.assertIn("forbidden_equipment_operation", codes)

    def test_forbidden_key_clone_equipment_produces_error(self) -> None:
        session = self._make_mock_session()
        recipe = recipe_from_dict({"modName": "test", "cloneEquipment": [{"equipmentKey": "x"}]})
        messages = validate(session, recipe)
        codes = [m.code for m in messages]
        self.assertIn("forbidden_equipment_operation", codes)

    def test_equipment_create_operation_is_forbidden(self) -> None:
        session = self._make_mock_session()
        recipe = recipe_from_dict({
            "modName": "test",
            "equipment": [{"operation": "create"}],
        })
        messages = validate(session, recipe)
        codes = [m.code for m in messages]
        self.assertIn("forbidden_equipment_operation", codes)

    def test_equipment_clone_operation_is_forbidden(self) -> None:
        session = self._make_mock_session()
        recipe = recipe_from_dict({
            "modName": "test",
            "equipment": [{"operation": "clone"}],
        })
        messages = validate(session, recipe)
        codes = [m.code for m in messages]
        self.assertIn("forbidden_equipment_operation", codes)

    def test_equipment_patch_operation_is_allowed(self) -> None:
        session = self._make_mock_session()
        recipe = recipe_from_dict({
            "modName": "test",
            "equipment": [{"operation": "patch"}],
        })
        messages = validate(session, recipe)
        codes = [m.code for m in messages]
        self.assertNotIn("forbidden_equipment_operation", codes)

    def test_equipment_effect_patches_key_produces_error(self) -> None:
        session = self._make_mock_session()
        recipe = recipe_from_dict({"modName": "test"})
        # Manually inject the forbidden key into raw
        recipe = Recipe(
            mod_name="test",
            raw={"equipmentEffectPatches": []},
        )
        messages = validate(session, recipe)
        codes = [m.code for m in messages]
        self.assertIn("unsupported_recipe_key", codes)

    def test_empty_recipe_produces_warning(self) -> None:
        session = self._make_mock_session()
        recipe = recipe_from_dict({"modName": "test"})
        messages = validate(session, recipe)
        codes = [m.code for m in messages]
        self.assertIn("empty_recipe", codes)
        self.assertFalse(any(m.level == "error" for m in messages if m.code == "empty_recipe"))

    def test_invalid_output_path_extension_produces_error(self) -> None:
        session = self._make_mock_session()
        recipe = recipe_from_dict({"modName": "test"})
        messages = validate(session, recipe, output_path="output.json")
        codes = [m.code for m in messages]
        self.assertIn("invalid_output_path", codes)

    def test_valid_output_path_is_accepted(self) -> None:
        session = self._make_mock_session()
        recipe = recipe_from_dict({"modName": "test"})
        messages = validate(session, recipe, output_path="output.pack")
        codes = [m.code for m in messages]
        self.assertNotIn("invalid_output_path", codes)

    def test_birth_year_999_sentinel_is_rejected(self) -> None:
        session = self._make_mock_session()
        recipe = recipe_from_dict({
            "modName": "test",
            "ageRangeClones": [{
                "sourceKey": "source_age",
                "newKey": "hby_age_test",
                "overrides": {"birth_year": 999},
            }],
        })

        messages = validate(session, recipe)

        self.assertIn("invalid_birth_year", [message.code for message in messages])

    def test_fixed_birth_year_is_accepted(self) -> None:
        session = self._make_mock_session()
        recipe = recipe_from_dict({
            "modName": "test",
            "ageRangeClones": [{
                "sourceKey": "source_age",
                "newKey": "hby_age_test",
                "overrides": {"birth_year": 176},
            }],
        })

        messages = validate(session, recipe)

        self.assertNotIn("invalid_birth_year", [message.code for message in messages])

    def test_non_numeric_stat_value_produces_error(self) -> None:
        session = self._make_mock_session()
        recipe = recipe_from_dict({
            "modName": "test",
            "equipmentStatPatches": [{
                "equipmentKey": "some_key",
                "statTable": "melee_weapon",
                "column": "damage",
                "value": "bad_string",
            }],
        })
        messages = validate(session, recipe)
        codes = [m.code for m in messages]
        self.assertIn("invalid_stat_value", codes)

    def test_audio_type_must_be_non_empty_string(self) -> None:
        session = self._make_mock_session()
        recipe = recipe_from_dict({
            "modName": "test",
            "equipmentStatPatches": [{
                "equipmentKey": "some_key",
                "statTable": "armour",
                "column": "audio_type",
                "value": 123,
            }],
        })
        messages = validate(session, recipe)
        codes = [m.code for m in messages]
        self.assertIn("invalid_stat_value", codes)

    def test_audio_type_accepts_valid_string(self) -> None:
        session = self._make_mock_session()
        # Provide the armour variant rows needed for resolve_stat_target
        session.envelope["tables"].update({
            "ceos_to_equipment_variants_armours": [
                {"ceos_key": "some_key", "armour": "armour_row_key", "game_mode": "historical"},
            ],
            "unit_armour_types": [
                {"key": "armour_row_key", "armour_value": 50, "audio_type": "metal"},
            ],
        })
        recipe = recipe_from_dict({
            "modName": "test",
            "equipmentStatPatches": [{
                "equipmentKey": "some_key",
                "statTable": "armour",
                "column": "audio_type",
                "value": "leather",
                "gameMode": "historical",
            }],
        })
        messages = validate(session, recipe)
        invalid_stat_value_errors = [m for m in messages if m.code == "invalid_stat_value"]
        self.assertEqual(invalid_stat_value_errors, [])


class ValidateAmbiguousWeaponTest(unittest.TestCase):
    def _make_session_with_dual_mode_weapon(self) -> Any:
        from pathlib import Path
        from tk_pack_builder.adapters import MockPackSession
        return MockPackSession(
            pack_path=Path("starter.pack"),
            envelope={
                "gameKey": "three_kingdoms",
                "packName": "starter",
                "tables": {
                    "ceos_to_equipment_variants_weapons": [
                        {
                            "ceos_key": "3k_mtu_ancillary_weapon_comet_spear",
                            "primary_melee_weapon": "weapon_key_historical",
                            "game_mode": "historical",
                        },
                        {
                            "ceos_key": "3k_mtu_ancillary_weapon_comet_spear",
                            "primary_melee_weapon": "weapon_key_romance",
                            "game_mode": "romance",
                        },
                    ],
                    "melee_weapons": [
                        {"key": "weapon_key_historical", "damage": 100},
                        {"key": "weapon_key_romance", "damage": 200},
                    ],
                    "unit_armour_types": [],
                    "ceos_to_equipment_variants_armours": [],
                    "missile_weapons": [],
                    "projectiles": [],
                    "land_units": [],
                    "main_units": [],
                    "character_generation_templates": [],
                    "character_generation_template_game_mode_details": [],
                    "campaign_character_art_sets": [],
                    "campaign_character_arts": [],
                    "character_generation_spawn_age_ranges": [],
                    "ceo_initial_datas": [],
                },
                "loc": {},
                "files": [],
                "metadata": {},
            },
        )

    def test_ambiguous_weapon_without_game_mode_produces_error(self) -> None:
        session = self._make_session_with_dual_mode_weapon()
        recipe = recipe_from_dict({
            "modName": "test",
            "equipmentStatPatches": [{
                "equipmentKey": "3k_mtu_ancillary_weapon_comet_spear",
                "statTable": "melee_weapon",
                "column": "damage",
                "value": 99,
            }],
        })
        messages = validate(session, recipe)
        error_messages = [m for m in messages if m.level == "error"]
        self.assertTrue(any("gameMode" in m.message or "provide gameMode" in m.message for m in error_messages))

    def test_weapon_with_game_mode_is_resolved(self) -> None:
        session = self._make_session_with_dual_mode_weapon()
        recipe = recipe_from_dict({
            "modName": "test",
            "equipmentStatPatches": [{
                "equipmentKey": "3k_mtu_ancillary_weapon_comet_spear",
                "statTable": "melee_weapon",
                "column": "damage",
                "value": 99,
                "gameMode": "historical",
            }],
        })
        messages = validate(session, recipe)
        stat_errors = [m for m in messages if m.code == "invalid_stat_patch"]
        self.assertEqual(stat_errors, [])


if __name__ == "__main__":
    unittest.main()
