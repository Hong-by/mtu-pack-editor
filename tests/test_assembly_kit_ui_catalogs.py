from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_assembly_kit_ui_catalogs import (
    build_ability_effect_catalog,
    build_skill_entries,
    build_title_entries,
    effect_text,
    scope_text,
    title_aliases,
)
from tk_pack_builder import web


def write_xml(path: Path, row_tag: str, rows: list[dict[str, str]]) -> None:
    body = []
    for row in rows:
        fields = "".join(f"<{key}>{value}</{key}>" for key, value in row.items())
        body.append(f"<{row_tag}>{fields}</{row_tag}>")
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?><dataroot>'
        + "".join(body)
        + "</dataroot>",
        encoding="utf-8",
    )


class AssemblyKitUiCatalogTests(unittest.TestCase):
    def test_effect_text_substitutes_game_number_tokens(self) -> None:
        loc = {
            "effects_description_test_armour": "갑옷 [[b]]%+n%[[/b]]",
        }
        self.assertEqual(effect_text("test_armour", {}, loc, 12), "갑옷 +12%")

    def test_scope_text_uses_korean_translation_tokens(self) -> None:
        loc = {
            "campaign_effect_scopes_localised_text_character_minister_to_faction": (
                "{{tr:only_if_faction_leader}}"
            )
        }
        self.assertEqual(
            scope_text("character_minister_to_faction", loc),
            "(세력 지도자일 경우)",
        )

    def test_expands_granted_ability_into_real_battle_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir)
            write_xml(
                db / "effect_bonus_value_unit_ability_junctions.xml",
                "effect_bonus_value_unit_ability_junctions",
                [
                    {
                        "bonus_value_id": "enable",
                        "effect": "test_grant_ability",
                        "unit_ability": "test_ability",
                    }
                ],
            )
            write_xml(
                db / "unit_abilities.xml",
                "unit_abilities",
                [
                    {
                        "key": "test_ability",
                        "onscreen_name": "Test Ability",
                        "tooltip_text": "Test tooltip",
                    }
                ],
            )
            write_xml(
                db / "unit_special_abilities.xml",
                "unit_special_abilities",
                [
                    {
                        "key": "test_ability",
                        "active_time": "30",
                        "affect_self": "1",
                        "effect_range": "75",
                        "num_uses": "-1",
                        "passive": "0",
                        "recharge_time": "120",
                        "splash_attack_damage": "0",
                    }
                ],
            )
            write_xml(
                db / "special_ability_to_special_ability_phase_junctions.xml",
                "special_ability_to_special_ability_phase_junctions",
                [
                    {
                        "order": "1",
                        "phase": "test_phase",
                        "special_ability": "test_ability",
                    }
                ],
            )
            write_xml(
                db / "special_ability_phases.xml",
                "special_ability_phases",
                [
                    {
                        "id": "test_phase",
                        "affects_allies": "1",
                        "affects_enemies": "0",
                        "duration": "30",
                        "recharge_time": "120",
                    }
                ],
            )
            write_xml(
                db / "special_ability_phase_stat_effects.xml",
                "special_ability_phase_stat_effects",
                [
                    {
                        "how": "add",
                        "phase": "test_phase",
                        "stat": "stat_melee_defence",
                        "value": "100",
                    }
                ],
            )
            write_xml(
                db / "special_ability_phase_attribute_effects.xml",
                "special_ability_phase_attribute_effects",
                [
                    {
                        "attribute": "unbreakable",
                        "attribute_type": "positive",
                        "phase": "test_phase",
                    }
                ],
            )
            loc = {
                "unit_abilities_onscreen_name_test_ability": "시험 능력",
                "unit_abilities_tooltip_text_test_ability": "시험 능력 설명",
                "unit_ability_types_onscreen_name_test_ability": "발동 시 강화",
                "unit_stat_localisations_onscreen_name_stat_melee_defence": "근접 회피",
                "unit_attributes_imued_effect_text_unbreakable": "불굴",
                "unit_attributes_bullet_text_unbreakable": (
                    "[[b]]불굴[[/b]]\\n\\n절대 패주하지 않습니다."
                ),
            }

            catalog = build_ability_effect_catalog(db, loc)
            summary = catalog["test_grant_ability"][0]["summary"]

            self.assertIn("능력: 시험 능력 — 시험 능력 설명", summary)
            self.assertIn("대상: 자신 및 범위 75m 내 아군", summary)
            self.assertIn("지속 30초 / 재사용 120초", summary)
            self.assertIn("근접 회피 +100", summary)
            self.assertIn("불굴 — 절대 패주하지 않습니다.", summary)

    def test_builds_skill_and_title_entries_from_real_relations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir)
            write_xml(
                db / "character_skills.xml",
                "character_skills",
                [
                    {
                        "key": "3k_main_skill_test",
                        "localised_name": "Test Skill",
                        "localised_description": "Test description",
                    }
                ],
            )
            write_xml(
                db / "character_skill_level_to_effects_junctions.xml",
                "character_skill_level_to_effects_junctions",
                [
                    {
                        "character_skill_key": "3k_main_skill_test",
                        "effect_key": "test_armour",
                        "effect_scope": "character_to_character_own",
                        "level": "1",
                        "value": "15",
                    }
                ],
            )
            write_xml(
                db / "ceo_nodes.xml",
                "ceo_nodes",
                [
                    {
                        "key": "3k_main_ceo_node_career_historical_test_01",
                        "ceo_effect_list": "test_title_list",
                        "title": "Test Title",
                        "description": "Test title description",
                    }
                ],
            )
            write_xml(
                db / "ceo_effect_list_to_effects.xml",
                "ceo_effect_list_to_effects",
                [
                    {
                        "effect_list": "test_title_list",
                        "effect": "test_armour",
                        "effect_scope": "character_to_character_own",
                        "value": "7",
                    }
                ],
            )
            write_xml(
                db / "effects.xml",
                "effects",
                [{"effect": "test_armour", "description": "Armour %+n%"}],
            )
            loc = {
                "character_skills_localised_name_3k_main_skill_test": "시험 기술",
                "character_skills_localised_description_3k_main_skill_test": "시험 설명",
                "ceo_nodes_title_3k_main_ceo_node_career_historical_test_01": "시험 칭호",
                "ceo_nodes_description_3k_main_ceo_node_career_historical_test_01": "시험 칭호 설명",
                "effects_description_test_armour": "갑옷 %+n%",
                "campaign_effect_scopes_localised_text_character_to_character_own": "(해당 인물)",
            }
            effects = {"test_armour": {"effect": "test_armour", "description": "Armour %+n%"}}

            skills = build_skill_entries(db, loc, effects, loc)
            titles = build_title_entries(db, loc, effects, loc)

            self.assertEqual(skills[0]["name"], "시험 기술")
            self.assertEqual(skills[0]["effectSummary"], "갑옷 +15% (해당 인물)")
            self.assertEqual(skills[0]["sourceKind"], "assembly_kit")
            self.assertEqual(titles[0]["title"], "시험 칭호")
            self.assertEqual(titles[0]["effects"], ["갑옷 +7% (해당 인물)"])
            self.assertIn(
                "3k_main_ceo_initial_data_character_historical_test",
                titles[0]["keys"],
            )

    def test_title_aliases_connect_node_career_and_initial_ceo(self) -> None:
        aliases = title_aliases("3k_main_ceo_node_career_historical_lu_meng_01")
        self.assertIn("3k_main_ceo_career_historical_lu_meng", aliases)
        self.assertIn("3k_main_ceo_initial_data_character_historical_lu_meng", aliases)

    def test_runtime_uses_assembly_kit_catalogs(self) -> None:
        web._load_skill_effect_catalog.cache_clear()
        web._load_title_effect_catalog.cache_clear()

        skill = web._catalog_skill_effect_info("3k_dlc04_skill_healer_tranquillity")
        title_lookup, _ = web._load_title_effect_catalog()
        title = web._title_effect_for_keys(
            title_lookup,
            "3k_main_ceo_node_career_historical_lu_meng_01",
        )

        self.assertEqual(skill["sourceKind"], "assembly_kit")
        self.assertEqual(skill["name"], "평안")
        self.assertIn("농업 수입 +3%", skill["effectSummary"])
        self.assertEqual(title["sourceKind"], "verified_game")
        self.assertEqual(title["title"], "만학도")
        self.assertIn("전문성 +15", title["effectSummary"])

        self.assertEqual(390, len(web._load_skill_effect_catalog()[1]))
        self.assertEqual(429, len(web._load_title_effect_catalog()[1]))
        self.assertEqual(
            [web.PACKAGED_ASSEMBLY_KIT_SKILL_EFFECT_CATALOG],
            web._skill_effect_catalog_paths(),
        )
        self.assertEqual(
            [web.PACKAGED_ASSEMBLY_KIT_TITLE_EFFECT_CATALOG],
            web._title_effect_catalog_paths(),
        )
        displayed_text = "\n".join(
            str(entry.get(field) or "")
            for entry in (
                *web._load_skill_effect_catalog()[1],
                *web._load_title_effect_catalog()[1],
            )
            for field in ("name", "title", "description", "effectSummary")
        )
        self.assertNotRegex(displayed_text, r"[A-Za-z][A-Za-z_]+")
        self.assertNotIn("능력: 발목 잡는 강타 +1", displayed_text)


if __name__ == "__main__":
    unittest.main()
