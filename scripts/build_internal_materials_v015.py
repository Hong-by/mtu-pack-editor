from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.adapters import adapter_for  # noqa: E402
from tk_pack_builder.web import _ensure_rpfm_server, default_game_local_pack_paths  # noqa: E402

MERGED_KOREAN_LOC_PATH = "text/mtu_pack_editor/merged_korean.loc"


def _workshop_roots() -> list[Path]:
    roots = [
        Path(os.environ["TK_PACK_EDITOR_WORKSHOP_DIR"])
        for _ in [0]
        if os.environ.get("TK_PACK_EDITOR_WORKSHOP_DIR")
    ]
    roots.extend([
        Path("E:/SteamLibrary/steamapps/workshop/content/779340"),
        Path("C:/Program Files (x86)/Steam/steamapps/workshop/content/779340"),
    ])
    return roots


def _workshop_pack_candidates(content_id: str, file_name: str) -> list[Path]:
    return [root / content_id / file_name for root in _workshop_roots()]


from tk_pack_builder.source_policy import PROFILE, MATERIAL_DIRECTORY, supported_source, require_clean_materials, EXCLUDED_TEMPLATE_KEYS

DEFAULT_SOURCES = [ROOT / "work" / "packs" / "my_hero.pack"] + [
    ROOT / "work" / "packs" / "refs" / name
    for name in ("database.pack", "data_mh.pack", "data_ep.pack", "data_dlc07.pack",
                 "data_dlc06.pack", "data_bl.pack", "data_yt_bl.pack", "data.pack")
] + _workshop_pack_candidates("1813995786", "[mod]MTU_original_v_0_0_2_korean.pack") + default_game_local_pack_paths()


REQUIRED_TABLE_FOLDERS = {
    "agent_uniforms_tables",
    "campaign_character_art_sets_tables",
    "campaign_character_arts_tables",
    "cai_retinues_to_aspects_tables",
    "cdir_events_incident_option_junctions_tables",
    "cdir_events_incident_payloads_tables",
    "ceo_initial_datas_tables",
    "ceos_to_equipment_variants_tables",
    "character_attribute_sets_tables",
    "character_attributes_tables",
    "effect_bonus_value_ids_unit_sets_tables",
    "effect_bonus_value_unit_ability_junctions_tables",
    "frontend_character_ceos_tables",
    "character_generation_spawn_age_ranges_tables",
    "character_generation_template_game_mode_details_tables",
    "character_generation_templates_tables",
    "character_skills_tables",
    "character_skill_level_to_effects_junctions_tables",
    "character_skill_node_links_tables",
    "character_skill_node_sets_tables",
    "character_skill_nodes_tables",
    "effects_tables",
    "incidents_tables",
    "land_units_tables",
    "land_units_to_unit_abilites_junctions_tables",
    "melee_weapons_tables",
    "missile_weapons_tables",
    "names_tables",
    "projectile_bombardments_tables",
    "projectile_displays_tables",
    "projectile_impacts_tables",
    "projectiles_tables",
    "retinue_slot_initial_units_tables",
    "retinues_tables",
    "special_ability_phase_attribute_effects_tables",
    "special_ability_phase_displays_tables",
    "special_ability_phase_stat_effects_tables",
    "special_ability_phases_tables",
    "special_ability_to_auto_deactivate_flags_tables",
    "special_ability_to_invalid_target_flags_tables",
    "special_ability_to_invalid_usage_flags_tables",
    "special_ability_to_special_ability_phase_junctions_tables",
    "unit_abilities_tables",
    "unit_armour_types_tables",
    "unit_special_abilities_tables",
    "variants_tables",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build v0.1.5 internal material snapshots.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "work" / "internal_materials" / MATERIAL_DIRECTORY)
    parser.add_argument("--source", action="append", type=Path, dest="sources")
    parser.add_argument("--include-large-assets", action="store_true")
    args = parser.parse_args()

    sources = [path.resolve() for path in (args.sources or DEFAULT_SOURCES) if path.is_file()]
    rejected = [str(path) for path in sources if not supported_source(path)]
    if rejected:
        raise ValueError(f"Unsupported material sources: {rejected}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    _ensure_rpfm_server()
    materials: dict[str, Any] = {
        "schemaVersion": 1,
        "sourceProfile": PROFILE,
        "baseline": "v0.1.5",
        "createdAt": time.time(),
        "sources": [str(path) for path in sources],
        "tables": {},
        "loc": {},
        "assets": {},
    }
    report: dict[str, Any] = {
        "baseline": "v0.1.5",
        "createdAt": materials["createdAt"],
        "sources": [],
        "missingSources": [str(path) for path in (args.sources or DEFAULT_SOURCES) if not path.is_file()],
    }

    for source in sources:
        source_report = inspect_source(source, materials, args.include_large_assets)
        report["sources"].append(source_report)

    finalize_loc_materials(materials)

    require_clean_materials(materials)

    material_path = args.output_dir / "materials.v015.json"
    report_path = args.output_dir / "internalization_report.v015.json"
    material_path.write_text(json.dumps(materials, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "materials": str(material_path),
        "report": str(report_path),
        "sourceCount": len(sources),
        "tableCount": len(materials["tables"]),
        "locFileCount": len(materials["loc"]),
        "assetCount": len(materials["assets"]),
    }, ensure_ascii=False, indent=2))


def inspect_source(source: Path, materials: dict[str, Any], include_large_assets: bool) -> dict[str, Any]:
    _ensure_rpfm_server()
    session = adapter_for("rpfm").open_pack(source)
    try:
        tables = session.list_tables()
        loc_files = session.list_loc_files()
        files = session.list_files()
        selected_tables = [
            path for path in tables
            if table_folder(path) in REQUIRED_TABLE_FOLDERS
        ]
        decoded = 0
        failed_tables: list[str] = []
        for table_path in selected_tables:
            try:
                rows = session.read_table(table_path)
                source_db = session.decoded_db_by_path[session._resolve_table_path(table_path)]
                if table_folder(table_path) == 'character_generation_templates_tables':
                    from tk_pack_builder.delta_builder import _db_with_rows
                    rows = [row for row in rows if row.get('key') not in EXCLUDED_TEMPLATE_KEYS]
                    source_db = _db_with_rows(source_db, rows)
            except Exception:
                failed_tables.append(table_path)
                continue
            materials["tables"].setdefault(table_path, {
                "sourcePath": str(source),
                "tablePath": table_path,
                "db": source_db,
                "rows": rows,
            })
            decoded += 1

        decoded_locs = 0
        for loc_path in loc_files:
            try:
                loc_rows = session.read_loc(loc_path)
            except Exception:
                continue
            add_loc_source(materials, loc_path, source, loc_rows)
            decoded_locs += 1

        asset_candidates = [
            path for path in files
            if path.startswith("ui/characters/") or path.startswith("script/")
        ]
        if include_large_assets:
            for asset_path in asset_candidates:
                materials["assets"].setdefault(asset_path, {"sourcePath": str(source)})

        return {
            "path": str(source),
            "sizeBytes": source.stat().st_size,
            "dbTableCount": len(tables),
            "selectedTableCount": len(selected_tables),
            "decodedTableCount": decoded,
            "failedTables": failed_tables[:20],
            "locFileCount": len(loc_files),
            "decodedLocFileCount": decoded_locs,
            "fileCount": len(files),
            "assetCandidateCount": len(asset_candidates),
            "topFileFolders": Counter(path.split("/", 1)[0] for path in files).most_common(12),
        }
    finally:
        session.close()


def table_folder(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    return parts[1] if len(parts) > 2 and parts[0] in {"db", "ceo_db"} else ""


def add_loc_source(materials: dict[str, Any], loc_path: str, source: Path, loc_rows: dict[str, str]) -> None:
    loc = materials.setdefault("loc", {})
    source_text = str(source)
    storage_path = loc_path
    if storage_path in loc and loc[storage_path].get("sourcePath") != source_text:
        storage_path = f"{loc_path}#source={source.stem}"
        index = 2
        while storage_path in loc:
            storage_path = f"{loc_path}#source={source.stem}_{index}"
            index += 1
    loc[storage_path] = {
        "sourcePath": source_text,
        "locPath": loc_path,
        "rows": {str(key): str(value) for key, value in loc_rows.items()},
    }


def finalize_loc_materials(materials: dict[str, Any]) -> None:
    merged: dict[str, str] = {}
    priorities: dict[str, tuple[int, str, str]] = {}
    source_paths: list[str] = []
    for storage_path, entry in sorted(materials.get("loc", {}).items()):
        if not isinstance(entry, dict):
            continue
        rows = entry.get("rows")
        if not isinstance(rows, dict):
            continue
        loc_path = str(entry.get("locPath") or storage_path).split("#source=", 1)[0]
        source_path = str(entry.get("sourcePath") or "")
        if source_path and source_path not in source_paths:
            source_paths.append(source_path)
        priority = _loc_source_priority(source_path, loc_path)
        for key, value in rows.items():
            key_text = str(key)
            rank = (priority, source_path, loc_path)
            if key_text not in merged or rank >= priorities[key_text]:
                merged[key_text] = str(value)
                priorities[key_text] = rank
    materials["loc"] = {
        MERGED_KOREAN_LOC_PATH: {
            "sourcePath": ";".join(source_paths),
            "locPath": MERGED_KOREAN_LOC_PATH,
            "rows": dict(sorted(merged.items())),
        }
    }


def _loc_source_priority(source_path: str, loc_path: str) -> int:
    source = source_path.replace("\\", "/").lower()
    loc = loc_path.replace("\\", "/").lower()
    if "hby" in source or "hby" in loc:
        return 100
    if "korea_addon" in source or "korea_addon" in loc or "190expande_korea" in source:
        return 95
    if "190_expanded_kr" in source or "localised_kr" in source or "korean" in source or "(kor)" in source:
        return 90
    if "local_kr.pack" in source or loc.startswith("text/localisation"):
        return 80
    if "mtu" in source or "mtu" in loc:
        return 70
    if "local_en.pack" in source:
        return 10
    if "local_" in source:
        return 5
    return 50


if __name__ == "__main__":
    main()
