from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.adapters import adapter_for  # noqa: E402
from tk_pack_builder.web import _ensure_rpfm_server  # noqa: E402


DEFAULT_SOURCES = [
    ROOT / "work" / "packs" / "my_hero.pack",
    ROOT / "work" / "packs" / "refs" / "database.pack",
    ROOT / "work" / "packs" / "refs" / "data_mh.pack",
    ROOT / "work" / "packs" / "refs" / "data_ep.pack",
    ROOT / "work" / "packs" / "refs" / "data_dlc07.pack",
    ROOT / "work" / "packs" / "refs" / "data_dlc06.pack",
    ROOT / "work" / "packs" / "refs" / "data_bl.pack",
    ROOT / "work" / "packs" / "refs" / "data_yt_bl.pack",
    ROOT / "work" / "packs" / "refs" / "BFG_Originals.pack",
    ROOT / "work" / "packs" / "refs" / "BFG_for_MTU.pack",
    ROOT / "work" / "packs" / "refs" / "BFG_Nanman2.pack",
    ROOT / "work" / "packs" / "refs" / "BFG_Yellow_Turban.pack",
    ROOT / "work" / "legacy_template" / "8King_4P_1.7_up.pack",
]

REQUIRED_TABLE_FOLDERS = {
    "campaign_character_art_sets_tables",
    "campaign_character_arts_tables",
    "cai_retinues_to_aspects_tables",
    "cdir_events_incident_option_junctions_tables",
    "cdir_events_incident_payloads_tables",
    "ceo_initial_datas_tables",
    "ceos_to_equipment_variants_tables",
    "character_attribute_sets_tables",
    "character_attributes_tables",
    "character_generation_spawn_age_ranges_tables",
    "character_generation_template_game_mode_details_tables",
    "character_generation_templates_tables",
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
    "projectiles_tables",
    "retinue_slot_initial_units_tables",
    "retinues_tables",
    "special_ability_phase_attribute_effects_tables",
    "special_ability_phase_stat_effects_tables",
    "special_ability_phases_tables",
    "special_ability_to_invalid_usage_flags_tables",
    "special_ability_to_special_ability_phase_junctions_tables",
    "unit_abilities_tables",
    "unit_armour_types_tables",
    "unit_special_abilities_tables",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build v0.1.5 internal material snapshots.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "work" / "internal_materials")
    parser.add_argument("--source", action="append", type=Path, dest="sources")
    parser.add_argument("--include-large-assets", action="store_true")
    args = parser.parse_args()

    sources = [path.resolve() for path in (args.sources or DEFAULT_SOURCES) if path.is_file()]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    _ensure_rpfm_server()
    materials: dict[str, Any] = {
        "schemaVersion": 1,
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
            materials["loc"].setdefault(loc_path, {
                "sourcePath": str(source),
                "rows": loc_rows,
            })
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


if __name__ == "__main__":
    main()
