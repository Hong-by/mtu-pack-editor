from __future__ import annotations

import unittest

from tk_pack_builder.recipe import (
    AgeRangeClone,
    AttributeSetClone,
    CharacterClone,
    CharacterPatch,
    LandUnitClone,
    Recipe,
    SkillSetClone,
    StatPatch,
    _canonical_equipment_key,
    _coalesce_stat_patches,
    _derived_age_range_key,
    _normalize_age_range_clones,
    recipe_from_dict,
)


class CanonicalEquipmentKeyTest(unittest.TestCase):
    def test_ancilliary_is_normalised_to_ancillary(self) -> None:
        self.assertEqual(
            _canonical_equipment_key("3k_mtu_ancilliary_weapon_comet_spear"),
            "3k_mtu_ancillary_weapon_comet_spear",
        )

    def test_already_correct_spelling_is_unchanged(self) -> None:
        self.assertEqual(
            _canonical_equipment_key("3k_mtu_ancillary_weapon_comet_spear"),
            "3k_mtu_ancillary_weapon_comet_spear",
        )

    def test_key_without_ancill_prefix_is_unchanged(self) -> None:
        self.assertEqual(_canonical_equipment_key("melee_weapon_basic"), "melee_weapon_basic")


class CoalesceStatPatchesTest(unittest.TestCase):
    def _patch(self, key: str, table: str, col: str, val: int, game_mode=None) -> StatPatch:
        return StatPatch(equipment_key=key, stat_table=table, column=col, value=val, game_mode=game_mode)

    def test_last_duplicate_wins(self) -> None:
        patches = _coalesce_stat_patches([
            self._patch("key_a", "melee_weapon", "damage", 10),
            self._patch("key_a", "melee_weapon", "damage", 99),
        ])
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0].value, 99)

    def test_different_columns_are_kept_separately(self) -> None:
        patches = _coalesce_stat_patches([
            self._patch("key_a", "melee_weapon", "damage", 10),
            self._patch("key_a", "melee_weapon", "ap_damage", 5),
        ])
        self.assertEqual(len(patches), 2)

    def test_different_game_modes_are_kept_separately(self) -> None:
        patches = _coalesce_stat_patches([
            self._patch("key_a", "melee_weapon", "damage", 10, "historical"),
            self._patch("key_a", "melee_weapon", "damage", 20, "romance"),
        ])
        self.assertEqual(len(patches), 2)

    def test_canonical_key_is_used_for_dedup(self) -> None:
        patches = _coalesce_stat_patches([
            self._patch("3k_mtu_ancilliary_weapon_x", "melee_weapon", "damage", 10),
            self._patch("3k_mtu_ancillary_weapon_x", "melee_weapon", "damage", 99),
        ])
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0].value, 99)

    def test_order_of_first_occurrence_is_preserved(self) -> None:
        patches = _coalesce_stat_patches([
            self._patch("key_b", "melee_weapon", "damage", 1),
            self._patch("key_a", "melee_weapon", "damage", 2),
            self._patch("key_b", "melee_weapon", "damage", 3),
        ])
        self.assertEqual([p.equipment_key for p in patches], ["key_b", "key_a"])


class DerivedAgeRangeKeyTest(unittest.TestCase):
    def test_key_starts_with_hby_age(self) -> None:
        key = _derived_age_range_key("3k_main_age_fixed_historical_cao_cao_hero_earth", {"birth_year": 155})
        self.assertTrue(key.startswith("hby_age_"))

    def test_key_is_deterministic(self) -> None:
        key1 = _derived_age_range_key("source_key", {"birth_year": 200})
        key2 = _derived_age_range_key("source_key", {"birth_year": 200})
        self.assertEqual(key1, key2)

    def test_different_overrides_produce_different_keys(self) -> None:
        key1 = _derived_age_range_key("source_key", {"birth_year": 155})
        key2 = _derived_age_range_key("source_key", {"birth_year": 200})
        self.assertNotEqual(key1, key2)

    def test_key_length_is_at_most_120(self) -> None:
        long_source = "3k_main_age_fixed_historical_a_b_c_d_e_f_g_h_i_j_k_l_m_n_o_p_q_r_s_t_u_v_w_x_y_z"
        key = _derived_age_range_key(long_source, {"birth_year": 180})
        self.assertLessEqual(len(key), 120)


class NormalizeAgeRangeClonesTest(unittest.TestCase):
    def test_same_source_and_new_key_is_remapped(self) -> None:
        data = {
            "ageRangeClones": [{
                "sourceKey": "3k_main_age_fixed_historical_cao_cao_hero_earth",
                "newKey": "3k_main_age_fixed_historical_cao_cao_hero_earth",
                "overrides": {"birth_year": 155},
            }],
            "characterCloneRecipes": [{
                "newTemplateKey": "hby_template_test",
                "sourceTemplateKey": "source",
                "templateOverrides": {
                    "spawn_age_range": "3k_main_age_fixed_historical_cao_cao_hero_earth",
                },
                "detailOverrides": {},
            }],
        }
        normalized = _normalize_age_range_clones(data)

        remapped_age_key = normalized["ageRangeClones"][0]["newKey"]
        self.assertNotEqual(remapped_age_key, "3k_main_age_fixed_historical_cao_cao_hero_earth")
        self.assertTrue(remapped_age_key.startswith("hby_age_"))
        self.assertEqual(
            normalized["characterCloneRecipes"][0]["templateOverrides"]["spawn_age_range"],
            remapped_age_key,
        )

    def test_different_source_and_new_key_is_not_remapped(self) -> None:
        data = {
            "ageRangeClones": [{
                "sourceKey": "3k_main_age_src",
                "newKey": "hby_age_custom",
                "overrides": {"birth_year": 155},
            }],
        }
        normalized = _normalize_age_range_clones(data)
        self.assertEqual(normalized["ageRangeClones"][0]["newKey"], "hby_age_custom")

    def test_no_age_range_clones_returns_data_unchanged(self) -> None:
        data = {"modName": "test", "characterCloneRecipes": []}
        normalized = _normalize_age_range_clones(data)
        self.assertEqual(normalized["ageRangeClones"], [])


class RecipeFromDictTest(unittest.TestCase):
    def test_mod_name_defaults_when_missing(self) -> None:
        recipe = recipe_from_dict({})
        self.assertEqual(recipe.mod_name, "unnamed_mod")

    def test_mod_name_is_read(self) -> None:
        recipe = recipe_from_dict({"modName": "my_mod"})
        self.assertEqual(recipe.mod_name, "my_mod")

    def test_empty_dict_produces_empty_recipe(self) -> None:
        recipe = recipe_from_dict({})
        self.assertEqual(recipe.equipment_stat_patches, [])
        self.assertEqual(recipe.land_unit_clones, [])
        self.assertEqual(recipe.character_clones, [])
        self.assertEqual(recipe.character_patches, [])

    def test_stat_patches_are_parsed(self) -> None:
        recipe = recipe_from_dict({
            "equipmentStatPatches": [
                {"equipmentKey": "key_a", "statTable": "melee_weapon", "column": "damage", "value": 99},
            ]
        })
        self.assertEqual(len(recipe.equipment_stat_patches), 1)
        self.assertEqual(recipe.equipment_stat_patches[0].equipment_key, "key_a")
        self.assertEqual(recipe.equipment_stat_patches[0].value, 99)

    def test_stat_patch_game_mode_is_optional(self) -> None:
        recipe = recipe_from_dict({
            "equipmentStatPatches": [
                {"equipmentKey": "key_a", "statTable": "melee_weapon", "column": "damage", "value": 10},
            ]
        })
        self.assertIsNone(recipe.equipment_stat_patches[0].game_mode)

    def test_land_unit_clone_is_parsed(self) -> None:
        recipe = recipe_from_dict({
            "landUnitClones": [{
                "sourceKey": "3k_main_unit_a",
                "newKey": "hby_unit_a",
                "overrides": {"charge_bonus": 50},
            }]
        })
        self.assertEqual(len(recipe.land_unit_clones), 1)
        clone = recipe.land_unit_clones[0]
        self.assertEqual(clone.source_key, "3k_main_unit_a")
        self.assertEqual(clone.new_key, "hby_unit_a")
        self.assertEqual(clone.overrides["charge_bonus"], 50)
        self.assertIsNone(clone.source_retinue_key)

    def test_land_unit_clone_retinue_keys_are_parsed(self) -> None:
        recipe = recipe_from_dict({
            "landUnitClones": [{
                "sourceKey": "src",
                "newKey": "dst",
                "overrides": {},
                "sourceRetinueKey": "src_retinue",
                "newRetinueKey": "dst_retinue",
            }]
        })
        clone = recipe.land_unit_clones[0]
        self.assertEqual(clone.source_retinue_key, "src_retinue")
        self.assertEqual(clone.new_retinue_key, "dst_retinue")

    def test_skill_set_clone_replacements_are_parsed(self) -> None:
        recipe = recipe_from_dict({
            "skillSetClones": [{
                "sourceSetKey": "src_set",
                "newSetKey": "hby_new_set",
                "replacements": [
                    {"nodeKey": "node_a", "skillKey": "skill_b"},
                ],
            }]
        })
        clone = recipe.skill_set_clones[0]
        self.assertEqual(clone.new_set_key, "hby_new_set")
        self.assertEqual(clone.replacements, {"node_a": "skill_b"})

    def test_skill_set_clone_skips_empty_node_keys(self) -> None:
        recipe = recipe_from_dict({
            "skillSetClones": [{
                "sourceSetKey": "src",
                "newSetKey": "dst",
                "replacements": [
                    {"nodeKey": "", "skillKey": "skill_b"},
                    {"nodeKey": "node_a", "skillKey": "skill_a"},
                ],
            }]
        })
        self.assertEqual(list(recipe.skill_set_clones[0].replacements.keys()), ["node_a"])

    def test_attribute_set_clone_filters_non_numeric_overrides(self) -> None:
        recipe = recipe_from_dict({
            "attributeSetClones": [{
                "sourceSetKey": "src_attrs",
                "newSetKey": "hby_attrs",
                "overrides": {"authority": 77, "label": "bad_string"},
            }]
        })
        clone = recipe.attribute_set_clones[0]
        self.assertIn("authority", clone.overrides)
        self.assertNotIn("label", clone.overrides)

    def test_character_clone_display_name_falls_back_to_new_name(self) -> None:
        recipe = recipe_from_dict({
            "characterCloneRecipes": [{
                "newTemplateKey": "hby_template",
                "sourceTemplateKey": "src",
                "newName": "홍길동",
                "detailOverrides": {},
            }]
        })
        self.assertEqual(recipe.character_clones[0].display_name, "홍길동")

    def test_character_clone_display_name_prefers_display_name(self) -> None:
        recipe = recipe_from_dict({
            "characterCloneRecipes": [{
                "newTemplateKey": "hby_template",
                "sourceTemplateKey": "src",
                "displayName": "우선",
                "newName": "후순위",
                "detailOverrides": {},
            }]
        })
        self.assertEqual(recipe.character_clones[0].display_name, "우선")

    def test_character_clone_detail_source_defaults_to_source_template(self) -> None:
        recipe = recipe_from_dict({
            "characterCloneRecipes": [{
                "newTemplateKey": "hby_template",
                "sourceTemplateKey": "src_template",
                "detailOverrides": {},
            }]
        })
        clone = recipe.character_clones[0]
        self.assertEqual(clone.detail_source_template_key, "src_template")

    def test_character_patch_is_parsed(self) -> None:
        recipe = recipe_from_dict({
            "characterPatches": [{
                "templateKey": "3k_mtu_template_x",
                "templateOverrides": {"art_set_override": "some_art_set"},
                "detailOverrides": {},
            }]
        })
        patch = recipe.character_patches[0]
        self.assertEqual(patch.template_key, "3k_mtu_template_x")
        self.assertEqual(patch.template_overrides["art_set_override"], "some_art_set")

    def test_character_ceo_set_fields_are_parsed(self) -> None:
        recipe = recipe_from_dict({
            "characterCloneRecipes": [{
                "newTemplateKey": "hby_template",
                "sourceTemplateKey": "src",
                "detailOverrides": {},
                "titleCeoKey": "3k_main_ceo_career_historical_guan_yu",
                "removableTitleCeoKeys": ["3k_main_ceo_career_historical_generic_m_wood_general"],
                "traitSetKey": "warrior",
                "traitCeoKeys": ["trait_a"],
                "removableTraitCeoKeys": ["trait_old"],
                "equipmentSetKey": "sentinel",
                "equipmentCeoKeys": ["equipment_a"],
                "removableEquipmentCeoKeys": ["equipment_old"],
                "defaultEquipmentCeoKeys": ["default_armour"],
            }],
            "characterPatches": [{
                "templateKey": "3k_mtu_template_x",
                "templateOverrides": {},
                "detailOverrides": {},
                "titleCeoKey": "3k_main_ceo_career_historical_lu_bu",
                "traitSetKey": "commander",
                "traitCeoKeys": ["trait_b"],
            }],
        })

        clone = recipe.character_clones[0]
        self.assertEqual(clone.title_ceo_key, "3k_main_ceo_career_historical_guan_yu")
        self.assertEqual(
            clone.removable_title_ceo_keys,
            ("3k_main_ceo_career_historical_generic_m_wood_general",),
        )
        self.assertEqual(clone.trait_set_key, "warrior")
        self.assertEqual(clone.trait_ceo_keys, ("trait_a",))
        self.assertEqual(clone.removable_equipment_ceo_keys, ("equipment_old",))
        self.assertEqual(clone.default_equipment_ceo_keys, ("default_armour",))
        patch = recipe.character_patches[0]
        self.assertEqual(patch.title_ceo_key, "3k_main_ceo_career_historical_lu_bu")
        self.assertEqual(patch.trait_set_key, "commander")
        self.assertEqual(patch.trait_ceo_keys, ("trait_b",))

    def test_raw_data_is_preserved(self) -> None:
        data = {"modName": "test_mod", "custom_key": "custom_value"}
        recipe = recipe_from_dict(data)
        self.assertEqual(recipe.raw["custom_key"], "custom_value")

    def test_age_range_same_key_is_remapped_in_recipe(self) -> None:
        recipe = recipe_from_dict({
            "ageRangeClones": [{
                "sourceKey": "3k_main_age_fixed_historical_cao_cao_hero_earth",
                "newKey": "3k_main_age_fixed_historical_cao_cao_hero_earth",
                "overrides": {"birth_year": 155},
            }],
            "characterCloneRecipes": [{
                "newTemplateKey": "hby_template_test",
                "sourceTemplateKey": "source",
                "templateOverrides": {
                    "spawn_age_range": "3k_main_age_fixed_historical_cao_cao_hero_earth",
                },
                "detailOverrides": {},
            }],
        })
        remapped_key = recipe.age_range_clones[0].new_key
        self.assertNotEqual(remapped_key, "3k_main_age_fixed_historical_cao_cao_hero_earth")
        self.assertEqual(
            recipe.character_clones[0].template_overrides["spawn_age_range"],
            remapped_key,
        )


if __name__ == "__main__":
    unittest.main()
