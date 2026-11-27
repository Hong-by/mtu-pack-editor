from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import zlib
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.adapters import RpfmAdapter  # noqa: E402
from tk_pack_builder.delta_builder import (  # noqa: E402
    _loc_db_with_rows,
    _write_lua_text_file,
)
from tk_pack_builder.pfh import read_entry_bytes, read_pfh_index  # noqa: E402
from tk_pack_builder.web_runtime import _ensure_rpfm_server  # noqa: E402


GAME_PACK = Path(
    r"E:\SteamLibrary\steamapps\common\Total War THREE KINGDOMS\data"
    r"\zzz_mj_women_unit_all_in_one_player_only.pack"
)
GAME_DATA_DIR = GAME_PACK.parent
WORKSHOP_CONTENT_DIR = Path(
    r"E:\SteamLibrary\steamapps\workshop\content\779340"
)
MODIFIED_LOG = Path(os.environ.get("APPDATA", "")) / (
    r"The Creative Assembly\ThreeKingdoms\logs\modified.log"
)
OUTPUT_PACK = ROOT / "output" / GAME_PACK.name
TEMP_PACK = ROOT / "work" / "tmp_women_units_korea" / GAME_PACK.name

MAIN_UNITS_TABLE = "db/main_units_tables/women_unit_all_in_one"
LAND_UNITS_TABLE = "db/land_units_tables/women_unit_all_in_one"
REQUIREMENTS_TABLE = "db/campaign_unit_requirements_tables/women_unit_all_in_one"
PERMISSION_REQUIREMENTS_TABLE = (
    "db/campaign_unit_permission_requirements_tables/women_unit_all_in_one"
)
MILITARY_GROUPS_TABLE = (
    "db/units_to_groupings_military_permissions_tables/women_unit_all_in_one"
)
CAP_EFFECTS_TABLE = (
    "db/effect_bundles_to_effects_junctions_tables/women_unit_all_in_one"
)
CAMPAIGN_GROUP_BUNDLES_TABLE = (
    "db/campaign_group_faction_effect_bundles_tables/women_unit_all_in_one"
)
UNIT_CAP_JUNCTION_TABLE = (
    "db/effect_bonus_value_unit_record_junctions_tables/hby_mj_player_only_unit_caps"
)
UNIT_CAP_EFFECTS_TABLE = "db/effects_tables/hby_mj_player_only_unit_caps"
LAND_UNIT_TEMPLATES_TABLE = (
    "db/land_units_templates_tables/!!!!!FixedUnitNumbersYtr_mj"
)
UNIT_ABILITIES_TABLE = (
    "db/land_units_to_unit_abilites_junctions_tables/women_unit_all_in_one"
)
VARIANTS_TABLE = "db/variants_tables/women_unit_all_in_one"
UNIT_NAME_LOC = "text/db/mj_women_unit_names.loc"
CONFLICT_DB_PREFIXES = (
    "db/main_units_tables/",
    "db/land_units_tables/",
    "db/variants_tables/",
)

KOREAN_GENERALS_PERMISSION = "3k_mod_unit_permission_korean_generals"
HAN_MILITARY_GROUP = "3k_main_military_grouping_han_chinese"
CAP_BUNDLE = "hby_mj_women_units_player_only_cap"
CAP_VALUE = 99.0
PLAYER_ONLY_SCRIPT = "script/campaign/mod/hby_mj_women_units_player_only.lua"
CARD_ALIAS_ROOT = ROOT / "work" / "tmp_women_unit_card_aliases"

# Explicit legacy-to-unique mapping makes the converted units independent from
# vanilla and 190 Expanded rows.  Reusing the source keys caused whichever mod
# had the higher load priority to silently replace the requested balance.
LEGACY_UNIT_KEYS = (
    "3k_ytr_unit_earth_virtuous_noblemen",
    "ep_unit_water_qi_crossbowmen",
    "3k_ytr_unit_metal_arm_of_the_supreme_peace",
    "3k_dlc04_unit_fire_tyrant_slayers",
    "3k_dlc04_unit_metal_chosen_of_the_eight_immortals",
    "ep_unit_wood_qi_guardsmen",
    "3k_dlc07_unit_water_northern_mounted_archers",
    "3k_ytr_unit_water_archery_masters",
    "ep_unit_water_archers_of_jing",
    "3k_dlc04_unit_fire_righteous_vanguards",
    "3k_dlc04_unit_wood_gallants_of_the_people",
    "3k_dlc04_unit_earth_messengers_of_heaven",
    "3k_ytr_unit_metal_scholar_warriors",
    "3k_ytr_unit_metal_youxia",
)
UNIT_KEY_MAP = {key: f"hby_mj_{key}" for key in LEGACY_UNIT_KEYS}

# Explicit target values keep rebuilding this patch idempotent.  Do not derive
# these from an already patched pack, otherwise every rebuild would halve the
# costs and add the bonuses again.
LEGACY_BALANCE_TARGETS: dict[str, dict[str, int]] = {
    "3k_ytr_unit_earth_virtuous_noblemen": {
        "recruitment_cost": 600,
        "upkeep_cost": 160,
        "melee_defence": 26,
        "reload_time_reduction_percentage": 0,
    },
    "ep_unit_water_qi_crossbowmen": {
        "recruitment_cost": 360,
        "upkeep_cost": 95,
        "melee_defence": 17,
        "reload_time_reduction_percentage": 40,
    },
    "3k_ytr_unit_metal_arm_of_the_supreme_peace": {
        "recruitment_cost": 550,
        "upkeep_cost": 145,
        "melee_defence": 53,
        "reload_time_reduction_percentage": 0,
    },
    "3k_dlc04_unit_fire_tyrant_slayers": {
        "recruitment_cost": 600,
        "upkeep_cost": 160,
        "melee_defence": 42,
        "reload_time_reduction_percentage": 0,
    },
    "3k_dlc04_unit_metal_chosen_of_the_eight_immortals": {
        "recruitment_cost": 500,
        "upkeep_cost": 140,
        "melee_defence": 70,
        "reload_time_reduction_percentage": 0,
    },
    "ep_unit_wood_qi_guardsmen": {
        "recruitment_cost": 475,
        "upkeep_cost": 123,
        "melee_defence": 50,
        "reload_time_reduction_percentage": 0,
    },
    "3k_dlc07_unit_water_northern_mounted_archers": {
        "recruitment_cost": 500,
        "upkeep_cost": 122,
        "melee_defence": 28,
        "reload_time_reduction_percentage": 80,
    },
    "3k_ytr_unit_water_archery_masters": {
        "recruitment_cost": 550,
        "upkeep_cost": 145,
        "melee_defence": 22,
        "reload_time_reduction_percentage": 60,
    },
    "ep_unit_water_archers_of_jing": {
        "recruitment_cost": 350,
        "upkeep_cost": 100,
        "melee_defence": 37,
        "reload_time_reduction_percentage": 20,
    },
    "3k_dlc04_unit_fire_righteous_vanguards": {
        "recruitment_cost": 600,
        "upkeep_cost": 163,
        "melee_defence": 40,
        "reload_time_reduction_percentage": 0,
    },
    "3k_dlc04_unit_wood_gallants_of_the_people": {
        "recruitment_cost": 500,
        "upkeep_cost": 138,
        "melee_defence": 31,
        "reload_time_reduction_percentage": 0,
    },
    "3k_dlc04_unit_earth_messengers_of_heaven": {
        "recruitment_cost": 625,
        "upkeep_cost": 145,
        "melee_defence": 25,
        "reload_time_reduction_percentage": 0,
    },
    "3k_ytr_unit_metal_scholar_warriors": {
        "recruitment_cost": 450,
        "upkeep_cost": 135,
        "melee_defence": 70,
        "reload_time_reduction_percentage": 0,
    },
    "3k_ytr_unit_metal_youxia": {
        "recruitment_cost": 500,
        "upkeep_cost": 140,
        "melee_defence": 55,
        "reload_time_reduction_percentage": 0,
    },
}
BALANCE_TARGETS = {
    UNIT_KEY_MAP[legacy_key]: values
    for legacy_key, values in LEGACY_BALANCE_TARGETS.items()
}
ALL_DAMAGE_RESISTANCE_TARGET = 20


def main() -> int:
    if not GAME_PACK.is_file():
        raise FileNotFoundError(f"Game pack not found: {GAME_PACK}")

    TEMP_PACK.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PACK.parent.mkdir(parents=True, exist_ok=True)
    TEMP_PACK.unlink(missing_ok=True)
    _ensure_rpfm_server()

    patch_report = _patch_to_temp(GAME_PACK, TEMP_PACK)
    temp_verification = _verify_pack(TEMP_PACK)
    if not temp_verification["ok"]:
        raise RuntimeError(f"Temporary pack verification failed: {temp_verification}")

    shutil.copy2(TEMP_PACK, OUTPUT_PACK)
    shutil.copy2(TEMP_PACK, GAME_PACK)
    TEMP_PACK.unlink(missing_ok=True)

    installed_verification = _verify_pack(GAME_PACK)
    if not installed_verification["ok"]:
        raise RuntimeError(f"Installed pack verification failed: {installed_verification}")

    print(
        json.dumps(
            {
                "ok": True,
                "gamePack": str(GAME_PACK),
                "outputPack": str(OUTPUT_PACK),
                "sha256": _sha256(GAME_PACK),
                **patch_report,
                "verification": installed_verification,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _patch_to_temp(source: Path, target: Path) -> dict[str, int]:
    session = RpfmAdapter().open_pack(source)
    migrated_unit_rows = 0
    migrated_reference_rows = 0
    migrated_loc_rows = 0
    added_requirements = 0
    added_permissions = 0
    normalized_campaign_caps = 0
    added_card_aliases = 0
    balance_changes = 0
    try:
        main_units = session.read_table(MAIN_UNITS_TABLE)
        source_unit_keys = {
            str(row.get("unit") or "")
            for row in main_units
            if row.get("unit")
        }
        legacy_keys = set(UNIT_KEY_MAP)
        unique_keys = set(UNIT_KEY_MAP.values())
        if source_unit_keys == legacy_keys:
            migration = _migrate_to_unique_unit_keys(session)
            migrated_unit_rows = migration["unitRows"]
            migrated_reference_rows = migration["referenceRows"]
            migrated_loc_rows = migration["locRows"]
            main_units = session.read_table(MAIN_UNITS_TABLE)
        elif source_unit_keys != unique_keys:
            raise RuntimeError(
                "Women unit pack is partially migrated or has unexpected keys: "
                f"legacy={len(source_unit_keys & legacy_keys)}, "
                f"unique={len(source_unit_keys & unique_keys)}, "
                f"other={sorted(source_unit_keys - legacy_keys - unique_keys)}"
            )

        unit_keys = sorted({str(row.get("unit") or "") for row in main_units if row.get("unit")})
        if len(unit_keys) != 14:
            raise RuntimeError(f"Expected 14 women units, found {len(unit_keys)}")
        if set(unit_keys) != set(BALANCE_TARGETS):
            raise RuntimeError("Women unit keys do not match the balance target table")

        for row in main_units:
            if str(row.get("unit") or "") not in unit_keys:
                continue
            if row.get("campaign_cap") != 0:
                row["campaign_cap"] = 0
                normalized_campaign_caps += 1
        land_units = session.read_table(LAND_UNITS_TABLE)
        balance_changes = _apply_balance_targets(main_units, land_units)
        if normalized_campaign_caps or balance_changes:
            session.replace_table(MAIN_UNITS_TABLE, main_units)
        if balance_changes:
            session.replace_table(LAND_UNITS_TABLE, land_units)

        requirements = session.read_table(REQUIREMENTS_TABLE)
        requirement_keys = {str(row.get("key") or "") for row in requirements}
        permissions = session.read_table(PERMISSION_REQUIREMENTS_TABLE)
        permission_pairs = {
            (str(row.get("permission") or ""), str(row.get("unit") or ""))
            for row in permissions
        }

        for index, unit_key in enumerate(unit_keys, start=1):
            requirement_key = f"hby_mj_korea_no_requirement_{index:02d}"
            if requirement_key not in requirement_keys:
                requirements.append(_empty_requirement(requirement_key))
                requirement_keys.add(requirement_key)
                added_requirements += 1

            pair = (KOREAN_GENERALS_PERMISSION, unit_key)
            if pair not in permission_pairs:
                permissions.append(
                    {
                        "is_restriction": False,
                        "permission": KOREAN_GENERALS_PERMISSION,
                        "requirement": requirement_key,
                        "unit": unit_key,
                    }
                )
                permission_pairs.add(pair)
                added_permissions += 1

        if added_requirements:
            session.replace_table(REQUIREMENTS_TABLE, requirements)
        if added_permissions:
            session.replace_table(PERMISSION_REQUIREMENTS_TABLE, permissions)

        _write_lua_text_file(
            session,
            session.pack_key,
            PLAYER_ONLY_SCRIPT,
            _player_only_lua(unit_keys),
        )
        added_card_aliases = _add_unit_card_aliases(session, main_units)
        session.save_as_pack(target)
    finally:
        session.close()

    return {
        "migratedUnitRows": migrated_unit_rows,
        "migratedReferenceRows": migrated_reference_rows,
        "migratedLocRows": migrated_loc_rows,
        "addedEmptyRequirements": added_requirements,
        "addedKoreaPermissionRows": added_permissions,
        "normalizedCampaignCaps": normalized_campaign_caps,
        "addedUnitCardAliases": added_card_aliases,
        "balanceFieldChanges": balance_changes,
    }


def _migrate_to_unique_unit_keys(session: object) -> dict[str, int]:
    main_units = session.read_table(MAIN_UNITS_TABLE)
    land_units = session.read_table(LAND_UNITS_TABLE)
    reserved_indices = _vanilla_main_unit_unique_indices()
    generated_indices: set[int] = set()

    migrated_unit_rows = 0
    for row in main_units:
        legacy_key = str(row.get("unit") or "")
        unique_key = UNIT_KEY_MAP.get(legacy_key)
        if unique_key is None:
            continue
        row["unit"] = unique_key
        if str(row.get("land_unit") or "") == legacy_key:
            row["land_unit"] = unique_key
        unique_index = _unique_main_unit_index(
            unique_key,
            reserved_indices | generated_indices,
        )
        row["unique_index"] = unique_index
        generated_indices.add(unique_index)
        migrated_unit_rows += 1

    for row in land_units:
        legacy_key = str(row.get("key") or "")
        unique_key = UNIT_KEY_MAP.get(legacy_key)
        if unique_key is None:
            continue
        row["key"] = unique_key
        migrated_unit_rows += 1

    if migrated_unit_rows != len(UNIT_KEY_MAP) * 2:
        raise RuntimeError(
            "Not every main_units/land_units row was migrated: "
            f"{migrated_unit_rows}/{len(UNIT_KEY_MAP) * 2}"
        )
    session.replace_table(MAIN_UNITS_TABLE, main_units)
    session.replace_table(LAND_UNITS_TABLE, land_units)

    reference_rows = 0
    reference_rows += _migrate_exact_field(
        session,
        PERMISSION_REQUIREMENTS_TABLE,
        "unit",
    )
    reference_rows += _migrate_exact_field(
        session,
        MILITARY_GROUPS_TABLE,
        "unit",
    )
    reference_rows += _migrate_exact_field(
        session,
        UNIT_ABILITIES_TABLE,
        "land_unit",
    )
    reference_rows += _migrate_exact_field(
        session,
        VARIANTS_TABLE,
        "variant_name",
    )
    reference_rows += _migrate_land_unit_templates(session)
    reference_rows += _migrate_unit_cap_tables(session)
    loc_rows = _migrate_unit_name_loc(session)

    return {
        "unitRows": migrated_unit_rows,
        "referenceRows": reference_rows,
        "locRows": loc_rows,
    }


def _migrate_exact_field(session: object, table_path: str, field: str) -> int:
    rows = session.read_table(table_path)
    changes = 0
    for row in rows:
        legacy_key = str(row.get(field) or "")
        unique_key = UNIT_KEY_MAP.get(legacy_key)
        if unique_key is None:
            continue
        row[field] = unique_key
        changes += 1
    if changes:
        session.replace_table(table_path, rows)
    return changes


def _migrate_land_unit_templates(session: object) -> int:
    rows = session.read_table(LAND_UNIT_TEMPLATES_TABLE)
    changes = 0
    for row in rows:
        legacy_key = str(row.get("land_unit") or "")
        unique_key = UNIT_KEY_MAP.get(legacy_key)
        if unique_key is None:
            continue
        row["land_unit"] = unique_key
        # The main composed entity gets the cloned female variant.  Existing
        # standard-bearer variants remain shared because this source pack does
        # not define independent female standard-bearer variant rows.
        if str(row.get("composed_entity") or "") == legacy_key:
            row["composed_entity"] = unique_key
        changes += 1
    if changes:
        session.replace_table(LAND_UNIT_TEMPLATES_TABLE, rows)
    return changes


def _migrate_unit_cap_tables(session: object) -> int:
    changes = 0
    table_fields = (
        (UNIT_CAP_JUNCTION_TABLE, ("unit_record_key", "effect")),
        (UNIT_CAP_EFFECTS_TABLE, ("effect",)),
        (CAP_EFFECTS_TABLE, ("effect_key",)),
    )
    for table_path, fields in table_fields:
        rows = session.read_table(table_path)
        table_changes = 0
        for row in rows:
            row_changed = False
            for field in fields:
                value = str(row.get(field) or "")
                migrated = _replace_unit_key_tokens(value)
                if migrated == value:
                    continue
                row[field] = migrated
                row_changed = True
            if row_changed:
                table_changes += 1
        if table_changes:
            session.replace_table(table_path, rows)
            changes += table_changes
    return changes


def _migrate_unit_name_loc(session: object) -> int:
    rows = session.read_loc(UNIT_NAME_LOC)
    migrated_rows: dict[str, str] = {}
    changes = 0
    for key, text in rows.items():
        migrated_key = _replace_unit_key_tokens(key)
        if migrated_key != key:
            changes += 1
        if migrated_key in migrated_rows:
            raise RuntimeError(f"Duplicate migrated LOC key: {migrated_key}")
        migrated_rows[migrated_key] = text
    if changes != len(UNIT_KEY_MAP) * 3:
        raise RuntimeError(
            "Expected three name LOC rows per women unit, found "
            f"{changes}/{len(UNIT_KEY_MAP) * 3}"
        )
    loc_db = _loc_db_with_rows(session, migrated_rows)
    response = session.client.send(
        {
            "SavePackedFileFromView": [
                session.pack_key,
                UNIT_NAME_LOC,
                {"Loc": loc_db},
            ]
        }
    )
    if "Error" in response.get("data", {}):
        raise RuntimeError(str(response["data"]["Error"]))
    return changes


def _replace_unit_key_tokens(value: str) -> str:
    migrated = value
    for legacy_key, unique_key in UNIT_KEY_MAP.items():
        migrated = migrated.replace(legacy_key, unique_key)
    return migrated


def _unique_main_unit_index(unit_key: str, reserved: set[int]) -> int:
    salt = 0
    while True:
        token = unit_key if salt == 0 else f"{unit_key}:{salt}"
        candidate = 1_500_000_000 + (zlib.crc32(token.encode("utf-8")) % 500_000_000)
        if candidate not in reserved:
            return candidate
        salt += 1


def _vanilla_main_unit_unique_indices() -> set[int]:
    assembly_db = Path(
        r"E:\SteamLibrary\steamapps\common\Total War THREE KINGDOMS"
        r"\assembly_kit\raw_data\db"
    )
    indices: set[int] = set()
    for path in (
        assembly_db / "main_units.xml",
        assembly_db / "TWaD_main_units.xml",
    ):
        if not path.is_file():
            continue
        for _event, element in ElementTree.iterparse(path, events=("end",)):
            if element.tag != "main_units":
                continue
            value = element.findtext("unique_index")
            if value:
                try:
                    indices.add(int(value))
                except ValueError:
                    pass
            element.clear()
    return indices


def _empty_requirement(key: str) -> dict[str, object]:
    return {
        "building1": "",
        "building2": "",
        "key": key,
        "religion": "",
        "resource1": "",
        "resource2": "",
        "skill1": "",
        "skill2": "",
        "tech1": "",
        "tech2": "",
        "must_be_world_leader": False,
        "minimum_character_rank": 0,
        "agent_subtype": "",
        "ceo": "",
    }


def _verify_pack(path: Path) -> dict[str, object]:
    index = read_pfh_index(path)
    _ensure_rpfm_server()
    session = RpfmAdapter().open_pack(path)
    try:
        main_units = session.read_table(MAIN_UNITS_TABLE)
        land_units = session.read_table(LAND_UNITS_TABLE)
        unit_keys = {str(row.get("unit") or "") for row in main_units if row.get("unit")}
        requirements = {
            str(row.get("key") or ""): row
            for row in session.read_table(REQUIREMENTS_TABLE)
        }
        permissions = session.read_table(PERMISSION_REQUIREMENTS_TABLE)
        military_groups = session.read_table(MILITARY_GROUPS_TABLE)
        cap_effects = session.read_table(CAP_EFFECTS_TABLE)
        cap_junctions = session.read_table(UNIT_CAP_JUNCTION_TABLE)
        cap_effect_definitions = session.read_table(UNIT_CAP_EFFECTS_TABLE)
        land_unit_templates = session.read_table(LAND_UNIT_TEMPLATES_TABLE)
        unit_abilities = session.read_table(UNIT_ABILITIES_TABLE)
        variants = session.read_table(VARIANTS_TABLE)
        name_loc = session.read_loc(UNIT_NAME_LOC)
        group_bundles = session.read_table(CAMPAIGN_GROUP_BUNDLES_TABLE)
        player_only_script = session.read_file_bytes(PLAYER_ONLY_SCRIPT).decode(
            "utf-8", errors="replace"
        )
        packed_files = {path.lower() for path in session.list_files()}
    finally:
        session.close()

    korea_permission_rows = [
        row
        for row in permissions
        if str(row.get("permission") or "") == KOREAN_GENERALS_PERMISSION
        and str(row.get("unit") or "") in unit_keys
        and row.get("is_restriction") is False
    ]
    korea_units = {str(row.get("unit") or "") for row in korea_permission_rows}
    empty_requirement_units = {
        str(row.get("unit") or "")
        for row in korea_permission_rows
        if _is_empty_requirement(requirements.get(str(row.get("requirement") or "")))
    }
    han_group_units = {
        str(row.get("unit") or "")
        for row in military_groups
        if str(row.get("military_group") or "") == HAN_MILITARY_GROUP
    }
    cap_units = {
        str(row.get("effect_key") or "").removeprefix("hby_mj_effect_unit_cap_")
        for row in cap_effects
        if str(row.get("effect_bundle_key") or "") == CAP_BUNDLE
        and float(row.get("value") or 0) >= CAP_VALUE
    }
    human_bundle_rows = [
        row
        for row in group_bundles
        if str(row.get("effect_bundle") or "") == CAP_BUNDLE
        and row.get("apply_to_human") is True
        and row.get("apply_to_ai") is False
    ]
    zero_campaign_caps = all(row.get("campaign_cap") == 0 for row in main_units)
    balance_targets_valid = _balance_targets_valid(main_units, land_units)
    expected_card_aliases = _expected_unit_card_aliases(main_units)
    present_card_aliases = {
        path for path in expected_card_aliases if path.lower() in packed_files
    }
    expected_units = set(UNIT_KEY_MAP.values())
    land_unit_keys = {
        str(row.get("key") or "") for row in land_units if row.get("key")
    }
    main_land_links_valid = all(
        str(row.get("land_unit") or "") == str(row.get("unit") or "")
        for row in main_units
    )
    unique_indices = [int(row.get("unique_index") or 0) for row in main_units]
    vanilla_indices = _vanilla_main_unit_unique_indices()
    unique_indices_valid = (
        len(unique_indices) == len(set(unique_indices))
        and all(value > 0 for value in unique_indices)
        and not (set(unique_indices) & vanilla_indices)
    )

    variant_units = {
        str(row.get("variant_name") or "")
        for row in variants
        if row.get("variant_name")
    }
    missing_variant_assets = sorted(
        str(row.get("variant_filename") or "")
        for row in variants
        if _variant_asset_path(str(row.get("variant_filename") or "")).lower()
        not in packed_files
    )
    template_units = {
        str(row.get("land_unit") or "")
        for row in land_unit_templates
        if str(row.get("land_unit") or "") in expected_units
    }
    ability_units = {
        str(row.get("land_unit") or "")
        for row in unit_abilities
        if str(row.get("land_unit") or "") in expected_units
    }
    expected_ability_units = {
        UNIT_KEY_MAP["ep_unit_wood_qi_guardsmen"]
    }
    cap_junction_units = {
        str(row.get("unit_record_key") or "")
        for row in cap_junctions
        if str(row.get("unit_record_key") or "") in expected_units
    }
    cap_definition_effects = {
        str(row.get("effect") or "")
        for row in cap_effect_definitions
    }
    expected_cap_effects = {
        f"hby_mj_effect_unit_cap_{unit_key}" for unit_key in expected_units
    }
    expected_loc_keys = {
        f"{prefix}_{unit_key}"
        for unit_key in expected_units
        for prefix in (
            "land_units_onscreen_name",
            "main_units_onscreen_name",
            "units_onscreen_name",
        )
    }
    legacy_reference_count = _legacy_reference_count(
        main_units=main_units,
        land_units=land_units,
        permissions=permissions,
        military_groups=military_groups,
        cap_effects=cap_effects,
        cap_junctions=cap_junctions,
        cap_effect_definitions=cap_effect_definitions,
        land_unit_templates=land_unit_templates,
        unit_abilities=unit_abilities,
        variants=variants,
        loc_keys=set(name_loc),
        player_only_script=player_only_script,
    )
    external_conflicts = _external_unique_key_conflicts(path, expected_units)
    shared_game_mode_rows = all(
        "game_mode" not in row for row in [*main_units, *land_units]
    )

    ok = (
        index.pack_type == "Mod"
        and unit_keys == expected_units
        and land_unit_keys == expected_units
        and main_land_links_valid
        and unique_indices_valid
        and korea_units == unit_keys
        and empty_requirement_units == unit_keys
        and unit_keys <= han_group_units
        and unit_keys <= cap_units
        and bool(human_bundle_rows)
        and zero_campaign_caps
        and balance_targets_valid
        and _valid_player_only_script(player_only_script, unit_keys)
        and present_card_aliases == expected_card_aliases
        and variant_units == expected_units
        and not missing_variant_assets
        and template_units <= expected_units
        and ability_units == expected_ability_units
        and cap_junction_units == expected_units
        and expected_cap_effects <= cap_definition_effects
        and expected_loc_keys <= set(name_loc)
        and legacy_reference_count == 0
        and not external_conflicts
        and shared_game_mode_rows
    )
    return {
        "ok": ok,
        "packType": index.pack_type,
        "unitCount": len(unit_keys),
        "koreaPermissionUnitCount": len(korea_units),
        "emptyRequirementUnitCount": len(empty_requirement_units),
        "hanMilitaryGroupUnitCount": len(unit_keys & han_group_units),
        "cap99UnitCount": len(unit_keys & cap_units),
        "playerOnlyCapBundle": bool(human_bundle_rows),
        "allCampaignCapsZero": zero_campaign_caps,
        "balanceTargetsValid": balance_targets_valid,
        "npcRecruitmentRestricted": _valid_player_only_script(
            player_only_script, unit_keys
        ),
        "unitCardAliasPathCount": len(present_card_aliases),
        "expectedUnitCardAliasPathCount": len(expected_card_aliases),
        "independentMainUnitKeys": unit_keys == expected_units,
        "independentLandUnitKeys": land_unit_keys == expected_units,
        "mainLandLinksValid": main_land_links_valid,
        "uniqueIndicesValid": unique_indices_valid,
        "variantUnitCount": len(variant_units & expected_units),
        "missingVariantAssets": missing_variant_assets,
        "templateUnitCount": len(template_units),
        "abilityUnitCount": len(ability_units),
        "unitCapJunctionCount": len(cap_junction_units),
        "unitCapEffectDefinitionCount": len(expected_cap_effects & cap_definition_effects),
        "unitNameLocCount": len(expected_loc_keys & set(name_loc)),
        "legacyReferenceCount": legacy_reference_count,
        "externalUniqueKeyConflicts": external_conflicts,
        "sharedRomanceAndRecordsRows": shared_game_mode_rows,
    }


def _variant_asset_path(filename: str) -> str:
    normalized = filename.replace("\\", "/").strip("/")
    if not normalized:
        return ""
    if "/" not in normalized:
        normalized = f"variantmeshes/variantmeshdefinitions/{normalized}"
    if not normalized.endswith(".variantmeshdefinition"):
        normalized += ".variantmeshdefinition"
    return normalized


def _legacy_reference_count(**collections: object) -> int:
    field_map = {
        "main_units": ("unit", "land_unit"),
        "land_units": ("key",),
        "permissions": ("unit",),
        "military_groups": ("unit",),
        "cap_effects": ("effect_key",),
        "cap_junctions": ("unit_record_key", "effect"),
        "cap_effect_definitions": ("effect",),
        "land_unit_templates": ("land_unit",),
        "unit_abilities": ("land_unit",),
        "variants": ("variant_name",),
    }
    count = 0
    for collection_name, fields in field_map.items():
        rows = collections.get(collection_name) or []
        for row in rows:
            for field in fields:
                value = str(row.get(field) or "")
                if _contains_unmigrated_unit_key(value):
                    count += 1
    for key in collections.get("loc_keys") or set():
        if _contains_unmigrated_unit_key(str(key)):
            count += 1
    script = str(collections.get("player_only_script") or "")
    count += sum(1 for key in UNIT_KEY_MAP if f'"{key}"' in script)
    return count


def _contains_unmigrated_unit_key(value: str) -> bool:
    remaining = value
    for unique_key in UNIT_KEY_MAP.values():
        remaining = remaining.replace(unique_key, "")
    return any(legacy_key in remaining for legacy_key in UNIT_KEY_MAP)


def _external_unique_key_conflicts(
    current_pack: Path,
    unit_keys: set[str],
) -> list[str]:
    conflicts: list[str] = []
    current_resolved = current_pack.resolve()
    for pack_path in _active_mod_pack_paths():
        try:
            if (
                pack_path.resolve() == current_resolved
                or pack_path.name.lower() == current_pack.name.lower()
            ):
                continue
            index = read_pfh_index(pack_path)
            needles_utf8 = {key: key.encode("utf-8") for key in unit_keys}
            needles_utf16 = {key: key.encode("utf-16-le") for key in unit_keys}
            matched: set[str] = set()
            for entry in index.entries:
                normalized = entry.path.replace("\\", "/").lower()
                if not normalized.startswith(CONFLICT_DB_PREFIXES):
                    continue
                try:
                    payload = read_entry_bytes(pack_path, entry)
                except ValueError:
                    continue
                matched.update(
                    key
                    for key in unit_keys
                    if needles_utf8[key] in payload or needles_utf16[key] in payload
                )
            if matched:
                conflicts.append(
                    f"{pack_path.name}: {', '.join(sorted(matched))}"
                )
        except (OSError, ValueError):
            continue
    return conflicts


def _active_mod_pack_paths() -> list[Path]:
    if not MODIFIED_LOG.is_file():
        return []
    names: list[str] = []
    try:
        for line in MODIFIED_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Mod: "):
                name = line.removeprefix("Mod: ").strip()
                if name.lower().endswith(".pack"):
                    names.append(name)
    except OSError:
        return []

    paths: list[Path] = []
    for name in names:
        direct = GAME_DATA_DIR / name
        if direct.is_file():
            paths.append(direct)
            continue
        if WORKSHOP_CONTENT_DIR.is_dir():
            paths.extend(sorted(WORKSHOP_CONTENT_DIR.glob(f"*/{name}")))
    return paths


def _apply_balance_targets(
    main_units: list[dict[str, object]],
    land_units: list[dict[str, object]],
) -> int:
    changes = 0
    main_by_key = {str(row.get("unit") or ""): row for row in main_units}
    land_by_key = {str(row.get("key") or ""): row for row in land_units}

    missing_main = set(BALANCE_TARGETS) - set(main_by_key)
    missing_land = set(BALANCE_TARGETS) - set(land_by_key)
    if missing_main or missing_land:
        raise RuntimeError(
            "Balance target rows are missing: "
            f"main={sorted(missing_main)}, land={sorted(missing_land)}"
        )

    for unit_key, target in BALANCE_TARGETS.items():
        main_row = main_by_key[unit_key]
        land_row = land_by_key[unit_key]
        for field in ("recruitment_cost", "upkeep_cost"):
            value = target[field]
            if main_row.get(field) != value:
                main_row[field] = value
                changes += 1
        for field in ("melee_defence", "reload_time_reduction_percentage"):
            value = target[field]
            if land_row.get(field) != value:
                land_row[field] = value
                changes += 1
        if land_row.get("damage_mod_all") != ALL_DAMAGE_RESISTANCE_TARGET:
            land_row["damage_mod_all"] = ALL_DAMAGE_RESISTANCE_TARGET
            changes += 1
    return changes


def _balance_targets_valid(
    main_units: list[dict[str, object]],
    land_units: list[dict[str, object]],
) -> bool:
    main_by_key = {str(row.get("unit") or ""): row for row in main_units}
    land_by_key = {str(row.get("key") or ""): row for row in land_units}
    if not set(BALANCE_TARGETS) <= set(main_by_key):
        return False
    if not set(BALANCE_TARGETS) <= set(land_by_key):
        return False
    for unit_key, target in BALANCE_TARGETS.items():
        main_row = main_by_key[unit_key]
        land_row = land_by_key[unit_key]
        if any(
            main_row.get(field) != target[field]
            for field in ("recruitment_cost", "upkeep_cost")
        ):
            return False
        if any(
            land_row.get(field) != target[field]
            for field in ("melee_defence", "reload_time_reduction_percentage")
        ):
            return False
        if land_row.get("damage_mod_all") != ALL_DAMAGE_RESISTANCE_TARGET:
            return False
    return True


def _is_empty_requirement(row: dict[str, object] | None) -> bool:
    if row is None:
        return False
    text_fields = (
        "building1",
        "building2",
        "religion",
        "resource1",
        "resource2",
        "skill1",
        "skill2",
        "tech1",
        "tech2",
        "agent_subtype",
        "ceo",
    )
    return (
        all(not str(row.get(field) or "") for field in text_fields)
        and row.get("must_be_world_leader") is False
        and int(row.get("minimum_character_rank") or 0) == 0
    )


def _player_only_lua(unit_keys: list[str]) -> str:
    unit_lines = "\n".join(f'    "{unit_key}",' for unit_key in unit_keys)
    return f'''local hby_mj_women_units = {{
{unit_lines}
}}

local function hby_mj_set_player_only_for_faction(faction)
    if not faction or faction:is_null_interface() or faction:is_dead() then return end

    local modify_faction = cm:modify_faction(faction)
    if not modify_faction or modify_faction:is_null_interface() then return end

    for _, unit_key in ipairs(hby_mj_women_units) do
        if faction:is_human() then
            modify_faction:remove_event_restricted_unit_record(unit_key)
        else
            modify_faction:add_event_restricted_unit_record(unit_key)
        end
    end
end

local function hby_mj_set_all_factions_player_only()
    local factions = cm:query_model():world():faction_list()
    for index = 0, factions:num_items() - 1 do
        hby_mj_set_player_only_for_faction(factions:item_at(index))
    end
end

local function hby_mj_register_turn_listener()
    if not core or not core.add_listener then return end

    -- The Korea add-on registers its unit-cap listener from its own first-tick
    -- callback. Registering this listener here, after that callback has run,
    -- makes the player-only override the final writer for the same unit keys.
    core:remove_listener("hby_mj_women_units_player_only_v1")
    core:add_listener(
        "hby_mj_women_units_player_only_v1",
        "FactionTurnStart",
        true,
        function(context)
            local ok, err = pcall(function()
                hby_mj_set_player_only_for_faction(context:faction())
            end)
            if not ok then
                output("HBY women units player-only turn error: " .. tostring(err))
            end
        end,
        true
    )
end

if cm and cm.add_first_tick_callback then
    cm:add_first_tick_callback(function()
        local ok, err = pcall(hby_mj_set_all_factions_player_only)
        if not ok then
            output("HBY women units player-only first tick error: " .. tostring(err))
        end
        hby_mj_register_turn_listener()
    end)
end
'''


def _valid_player_only_script(script: str, unit_keys: set[str]) -> bool:
    first_tick = script.find("cm:add_first_tick_callback")
    late_registration = script.find("hby_mj_register_turn_listener()", first_tick)
    return (
        all(f'"{unit_key}"' in script for unit_key in unit_keys)
        and "faction:is_human()" in script
        and "add_event_restricted_unit_record(unit_key)" in script
        and "remove_event_restricted_unit_record(unit_key)" in script
        and '"FactionTurnStart"' in script
        and first_tick >= 0
        and late_registration > first_tick
    )


def _add_unit_card_aliases(session: object, main_units: list[dict[str, object]]) -> int:
    existing = {path.lower() for path in session.list_files()}
    source_paths: list[str] = []
    destination_paths: list[dict[str, str]] = []
    missing_sources: list[str] = []
    CARD_ALIAS_ROOT.mkdir(parents=True, exist_ok=True)

    for row in main_units:
        unit_key = str(row.get("unit") or "")
        card_path = str(row.get("unit_card") or "").replace("\\", "/").strip("/")
        if not unit_key or not card_path:
            continue
        for source, target in _unit_card_alias_pairs(unit_key, card_path):
            if target.lower() in existing:
                continue
            if source.lower() not in existing:
                missing_sources.append(source)
                continue
            payload = session.read_file_bytes(source)
            if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError(f"Unit card source is not a PNG: {source}")
            local_path = CARD_ALIAS_ROOT / (
                f"{zlib.crc32(target.encode('utf-8')) & 0xffffffff:08x}_"
                f"{Path(target).name}"
            )
            local_path.write_bytes(payload)
            source_paths.append(str(local_path))
            destination_paths.append({"File": target})
            existing.add(target.lower())

    if missing_sources:
        raise RuntimeError(
            "Unit card source variants are missing: " + ", ".join(missing_sources[:8])
        )
    if not source_paths:
        return 0
    response = session.client.send(
        {"AddPackedFiles": [session.pack_key, source_paths, destination_paths, None]}
    )
    data = response.get("data", {})
    if "Error" in data:
        raise RuntimeError(str(data["Error"]))
    return len(destination_paths)


def _expected_unit_card_aliases(main_units: list[dict[str, object]]) -> set[str]:
    expected: set[str] = set()
    for row in main_units:
        unit_key = str(row.get("unit") or "")
        card_path = str(row.get("unit_card") or "").replace("\\", "/").strip("/")
        if not unit_key or not card_path:
            continue
        expected.update(target for _, target in _unit_card_alias_pairs(unit_key, card_path))
    return expected


def _unit_card_alias_pairs(unit_key: str, card_path: str) -> list[tuple[str, str]]:
    source_base = card_path.removesuffix(".png")
    folder, _ = source_base.rsplit("/", 1)
    target_bases = {f"{folder}/{unit_key}"}

    # Some campaign recruitment panels ignore main_units.unit_card and rebuild
    # the vanilla DLC card path.  Female conversions commonly append one of
    # these suffixes, so also overwrite the corresponding vanilla path with the
    # female card.  In particular this covers the two fire cavalry cards whose
    # source names end in `_ladies`.
    for suffix in ("_ladies", "_lady", "_women"):
        if source_base.endswith(suffix):
            target_bases.add(source_base.removesuffix(suffix))
            break

    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for target_base in sorted(target_bases):
        for pair in _card_variant_pairs(source_base, target_base):
            if pair not in seen:
                seen.add(pair)
                pairs.append(pair)
    return pairs


def _card_variant_pairs(source_base: str, target_base: str) -> tuple[tuple[str, str], ...]:
    source_folder, source_name = source_base.rsplit("/", 1)
    target_folder, target_name = target_base.rsplit("/", 1)
    source_element = source_folder.rsplit("/", 1)[-1]
    target_element = target_folder.rsplit("/", 1)[-1]
    source_alternate_folder = source_folder.replace(
        f"/{source_element}", f"/{source_element}_alternate", 1
    )
    target_alternate_folder = target_folder.replace(
        f"/{target_element}", f"/{target_element}_alternate", 1
    )
    return (
        (f"{source_base}.png", f"{target_base}.png"),
        (f"{source_base}_bobblehead.png", f"{target_base}_bobblehead.png"),
        (
            f"{source_folder}/large/{source_name}.png",
            f"{target_folder}/large/{target_name}.png",
        ),
        (
            f"{source_folder}/large/{source_name}_bobblehead.png",
            f"{target_folder}/large/{target_name}_bobblehead.png",
        ),
        (
            f"{source_alternate_folder}/{source_name}.png",
            f"{target_alternate_folder}/{target_name}.png",
        ),
        (
            f"{source_alternate_folder}/{source_name}_bobblehead.png",
            f"{target_alternate_folder}/{target_name}_bobblehead.png",
        ),
        (
            f"{source_alternate_folder}/large/{source_name}.png",
            f"{target_alternate_folder}/large/{target_name}.png",
        ),
        (
            f"{source_alternate_folder}/large/{source_name}_bobblehead.png",
            f"{target_alternate_folder}/large/{target_name}_bobblehead.png",
        ),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


if __name__ == "__main__":
    raise SystemExit(main())
