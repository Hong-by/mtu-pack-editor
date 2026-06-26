from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.adapters import adapter_for  # noqa: E402
from tk_pack_builder.character_clone import CHARACTER_TABLE_ALIASES  # noqa: E402
from tk_pack_builder.web import (  # noqa: E402
    SKILL_TABLE_ALIASES,
    _read_character_alias_rows,
    _ensure_rpfm_server,
    _read_all_loc_text,
    _resolve_skill_table,
    _resolve_stat_table,
    summarize_character_tables,
)


DEFAULT_SOURCE_PACK = Path(
    r"E:\SteamLibrary\steamapps\workshop\content\779340\3415534775\!!190expande_korea_addon.pack"
)
DEFAULT_KR_PACK = Path(
    r"E:\SteamLibrary\steamapps\workshop\content\779340\3242244024\!!190_expanded_kr.pack"
)
DEFAULT_CHARACTER_PACK = Path(
    r"E:\SteamLibrary\steamapps\workshop\content\779340\2875547086\!!190_expanded_with_characters.pack"
)
DEFAULT_REFERENCE_PACKS = [
    ROOT / "work" / "packs" / "refs" / "database.pack",
]
DEFAULT_OUTPUT = ROOT / "work" / "internal_dbs" / "korea_characters.json"

EQUIPMENT_REFERENCE_ALIASES = (
    "ceo_initial_datas",
    "equipment_variants_weapons",
    "equipment_variants_armours",
    "melee_weapons",
    "missile_weapons",
    "projectiles",
    "unit_armour_types",
)

KOREAN_PLUS_EXTRA_TABLES = {
    "character_generation_templates": [
        "db/character_generation_templates_tables/!!ironic_addon_korea_leader_fix",
    ],
    "character_generation_template_game_mode_details": [
        "db/character_generation_template_game_mode_details_tables/!!ironic_addon_korea_leader_fix",
        "db/character_generation_template_game_mode_details_tables/!!ironic_korea_characters",
    ],
    "character_skill_node_sets": [
        "db/character_skill_node_sets_tables/!!ironic_addon_korea_unque_character_skillset",
        "db/character_skill_node_sets_tables/korean_unque_character_skillset_ep_skillset_change",
    ],
    "character_skill_nodes": [
        "db/character_skill_nodes_tables/!!ironic_addon_korea_unque_character_skillset",
        "db/character_skill_nodes_tables/korean_unque_character_skillset_ep_skillset_change",
    ],
    "character_skill_node_links": [
        "db/character_skill_node_links_tables/!!ironic_addon_korea_unque_character_skillset",
        "db/character_skill_node_links_tables/korean_unque_character_skillset_ep_skillset_change",
    ],
    "retinues": [
        "db/retinues_tables/!!ironic_addon_korea",
    ],
    "retinue_slot_initial_units": [
        "db/retinue_slot_initial_units_tables/!!ironic_addon_korea",
    ],
    "main_units": [
        "db/main_units_tables/!!rew_iro_korean_units_rosters",
    ],
}

HISTORICAL_CHARACTER_TABLES = {
    "db/character_generation_templates_tables/!!ironic_addon_korea",
    "db/character_generation_templates_tables/!!ironic_addon_korea_leader_fix",
}

EXCLUDED_TEMPLATE_MARKERS = (
    "_dummy_",
    "_scripted_",
    "_generic_",
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract 190 Expanded Korea character rows into the app's internal DB JSON."
    )
    parser.add_argument("--source-pack", type=Path, default=DEFAULT_SOURCE_PACK)
    parser.add_argument("--kr-pack", type=Path, default=DEFAULT_KR_PACK)
    parser.add_argument("--character-pack", type=Path, default=DEFAULT_CHARACTER_PACK)
    parser.add_argument(
        "--reference-pack",
        dest="reference_packs",
        action="append",
        type=Path,
        default=None,
        help="Additional dependency pack to merge for vanilla/DLC equipment stats.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source_pack = args.source_pack.expanduser().resolve()
    if not source_pack.is_file():
        raise SystemExit(f"Source pack not found: {source_pack}")
    kr_pack = args.kr_pack.expanduser().resolve() if args.kr_pack else None
    character_pack = args.character_pack.expanduser().resolve() if args.character_pack else None
    reference_packs = [
        path.expanduser().resolve()
        for path in (args.reference_packs if args.reference_packs is not None else DEFAULT_REFERENCE_PACKS)
        if path
    ]

    _ensure_rpfm_server()
    session = adapter_for("rpfm").open_pack(source_pack)
    try:
        tables = _read_character_tables_allow_missing(session, "pack")
        _merge_extra_tables(session, tables)
        if character_pack and character_pack.is_file():
            character_session = adapter_for("rpfm").open_pack(character_pack)
            try:
                _merge_character_dependency_tables(character_session, tables)
            finally:
                close_character = getattr(character_session, "close", None)
                if close_character:
                    close_character()
        for reference_pack in reference_packs:
            if not reference_pack.is_file():
                continue
            reference_session = adapter_for("rpfm").open_pack(reference_pack)
            try:
                _merge_equipment_reference_tables(reference_session, tables, str(reference_pack))
            finally:
                close_reference = getattr(reference_session, "close", None)
                if close_reference:
                    close_reference()
        _filter_korean_plus_characters(tables)
        loc_text = _read_all_loc_text(session)
        asset_files = session.list_files()
        kr_loc_text: dict[str, str] = {}
        if kr_pack and kr_pack.is_file():
            kr_session = adapter_for("rpfm").open_pack(kr_pack)
            try:
                kr_loc_text = _read_all_loc_text(kr_session)
            finally:
                close_kr = getattr(kr_session, "close", None)
                if close_kr:
                    close_kr()
            loc_text.update(kr_loc_text)
        summary = summarize_character_tables(tables, loc_text, asset_files, {})
        for character in summary.get("characters", []):
            if not character.get("imageOnly") and not character.get("virtualImageOnly"):
                character["regionTag"] = "korea"
                character["koreaFactionTag"] = _korea_faction_tag(str(character.get("key", "")))
                character["templateFamily"] = _template_family(str(character.get("key", "")))
                corrected_label = _corrected_leader_label(str(character.get("key", "")))
                if corrected_label:
                    character["displayName"] = corrected_label
                    character["label"] = corrected_label
    finally:
        close = getattr(session, "close", None)
        if close:
            close()

    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "createdAt": time.time(),
        "sourcePack": str(source_pack),
        "krPack": str(kr_pack) if kr_pack and kr_pack.is_file() else None,
        "characterPack": str(character_pack) if character_pack and character_pack.is_file() else None,
        "referencePacks": [str(path) for path in reference_packs if path.is_file()],
        "tables": tables,
        "locText": loc_text,
        "assetFiles": asset_files,
        "summary": summary,
        "counts": {
            "tables": {key: len(value) for key, value in tables.items()},
            "locText": len(loc_text),
            "krLocText": len(kr_loc_text),
            "assetFiles": len(asset_files),
            "summaryCharacters": len(summary.get("characters", [])),
            "koreaTaggedCharacters": sum(
                1 for row in summary.get("characters", []) if row.get("regionTag") == "korea"
            ),
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))
    print(f"Wrote {args.output}")
    return 0


def _merge_extra_tables(session: Any, tables: dict[str, list[dict[str, Any]]]) -> None:
    available = set(session.list_tables("pack"))
    for alias, table_paths in KOREAN_PLUS_EXTRA_TABLES.items():
        target = tables.setdefault(alias, [])
        for table_path in table_paths:
            if table_path not in available:
                continue
            for row in session.read_table(table_path, "pack"):
                target.append({**row, "_sourceTableName": table_path})


def _merge_character_dependency_tables(session: Any, tables: dict[str, list[dict[str, Any]]]) -> None:
    available = set(session.list_tables("pack"))
    for alias, prefixes in {
        "land_units": ("db/land_units_tables/",),
        "main_units": ("db/main_units_tables/",),
    }.items():
        target = tables.setdefault(alias, [])
        existing = {
            str(row.get("key") or row.get("land_unit") or row.get("unit") or "")
            for row in target
        }
        for table_path in sorted(path for path in available if path.startswith(prefixes)):
            for row in session.read_table(table_path, "pack"):
                row_key = str(row.get("key") or row.get("land_unit") or row.get("unit") or "")
                if not row_key or row_key in existing:
                    continue
                if not row_key.startswith(("rew_iro_korean_", "3k_mod_", "3k_main_general_", "3k_main_hero_")):
                    continue
                target.append({**row, "_sourceTableName": table_path})
                existing.add(row_key)


def _merge_equipment_reference_tables(
    session: Any,
    tables: dict[str, list[dict[str, Any]]],
    reference_path: str,
) -> None:
    for alias in EQUIPMENT_REFERENCE_ALIASES:
        try:
            rows = _read_dependency_rows(session, alias)
        except ValueError:
            continue
        _append_missing_dependency_rows(tables.setdefault(alias, []), rows, alias, reference_path)


def _read_dependency_rows(session: Any, alias: str) -> list[dict[str, Any]]:
    if alias in CHARACTER_TABLE_ALIASES:
        return _read_character_alias_rows(session, alias, "pack")
    table_name = _resolve_stat_table(session, alias, "pack")
    return [
        {**row, "_sourceTableName": table_name}
        for row in session.read_table(table_name, "pack")
    ]


def _append_missing_dependency_rows(
    target: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    alias: str,
    reference_path: str,
) -> None:
    key_fields = _dependency_key_fields(alias)
    existing = {
        tuple(row.get(field) for field in key_fields)
        for row in target
        if any(row.get(field) not in {None, ""} for field in key_fields)
    }
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        if not any(value not in {None, ""} for value in key):
            continue
        if key in existing:
            continue
        target.append({**row, "_referenceSourcePath": reference_path})
        existing.add(key)


def _dependency_key_fields(alias: str) -> tuple[str, ...]:
    if alias in {"equipment_variants_weapons", "equipment_variants_armours"}:
        return ("ceos_key", "game_mode")
    return ("key",)


def _read_character_tables_allow_missing(session: Any, source: str) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for alias in CHARACTER_TABLE_ALIASES:
        try:
            tables[alias] = _read_character_alias_rows(session, alias, source)
        except ValueError:
            tables[alias] = []
    for alias in (
        "equipment_variants_weapons",
        "equipment_variants_armours",
        "melee_weapons",
        "missile_weapons",
        "projectiles",
        "unit_armour_types",
        "land_units",
    ):
        try:
            table_name = _resolve_stat_table(session, alias, source)
            tables[alias] = session.read_table(table_name, source)
        except ValueError:
            tables[alias] = []
    for alias in SKILL_TABLE_ALIASES:
        try:
            table_name = _resolve_skill_table(session, alias, source)
            tables[alias] = session.read_table(table_name, source)
        except ValueError:
            tables[alias] = []
    return tables


def _filter_korean_plus_characters(tables: dict[str, list[dict[str, Any]]]) -> None:
    templates = [
        row for row in tables.get("character_generation_templates", [])
        if _is_included_korean_template(str(row.get("key", "")))
    ]
    template_keys = {str(row.get("key", "")) for row in templates}
    tables["character_generation_templates"] = templates
    tables["character_generation_template_game_mode_details"] = [
        row for row in tables.get("character_generation_template_game_mode_details", [])
        if str(row.get("character_generation_template", "")) in template_keys
    ]


def _is_included_korean_template(key: str) -> bool:
    lower = key.lower()
    if any(marker in lower for marker in EXCLUDED_TEMPLATE_MARKERS):
        return False
    if not lower.startswith(("3k_mod_template_historical_", "ironic_template_historical_")):
        return False
    return True


def _korea_faction_tag(key: str) -> str | None:
    lower = key.lower()
    if any(marker in lower for marker in (
        "_chogo_",
        "_buyeo_",
        "_gilseon_",
        "_jin_",
        "_woo_du_",
        "_go_su_",
        "_yu_gi_",
        "_gon_no_",
    )):
        return "baekje"
    if any(marker in lower for marker in (
        "_beolhyu_",
        "_seok_",
        "_mulgyeja_",
        "_lady_seok_",
        "_lady_sulye_",
        "_gu_suhye_",
        "_kim_gudo_",
        "_kim_michu_",
        "_kim_malgu_",
        "_yieum_",
        "_heung_sun_",
        "_seol_bu_",
        "_chung_hwon_",
        "_yeon_jin_",
        "_guk_ryang_",
        "_sul_myeong_",
        "_hwon_gyeon_",
        "_yun_jong_",
        "_gang_hwon_",
    )):
        return "silla"
    if any(marker in lower for marker in (
        "_kim_suro_",
        "_kim_geodeung_",
        "_heo_hwangok_",
        "_tam_hari_",
    )):
        return "gaya"
    if any(marker in lower for marker in (
        "_munseong_",
        "_go_seongbang_",
        "_go_ik_",
    )):
        return "tamna"
    if any(marker in lower for marker in (
        "_gogukcheon_",
        "_go_",
        "_an_ryo_",
        "_eul_paso_",
        "_mil_u_",
        "_queen_woo_",
        "_woo_so_",
        "_myeongrim_",
        "_jwagaryeo_",
        "_eobiryu_",
        "_hunyeo_",
        "_yu_okgu_",
        "_yu_yu_",
        "_deuk_rae_",
    )):
        return "goguryeo"
    return None


def _corrected_leader_label(key: str) -> str | None:
    lower = key.lower()
    labels = {
        "gogukcheon": "고남무",
        "chogo": "부여초고",
        "beolhyu": "석벌휴",
        "kim_suro": "김수로",
        "munseong": "고문성",
    }
    for marker, label in labels.items():
        if marker in lower:
            return label
    return None


def _template_family(key: str) -> str:
    return "compat" if key.startswith("ironic_template_") else "primary"


if __name__ == "__main__":
    raise SystemExit(main())
