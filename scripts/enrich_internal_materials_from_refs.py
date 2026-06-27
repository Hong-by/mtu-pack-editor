from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_internal_materials_v015 import REQUIRED_TABLE_FOLDERS, table_folder  # noqa: E402
from tk_pack_builder.adapters import adapter_for  # noqa: E402
from tk_pack_builder.web import _ensure_rpfm_server  # noqa: E402


DEFAULT_SOURCES = [
    ROOT / "work" / "packs" / "my_hero.pack",
    ROOT / "work" / "packs" / "refs" / "database.pack",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge missing internal material rows from reference packs.")
    parser.add_argument("--materials", type=Path, default=ROOT / "work" / "internal_materials" / "materials.v015.json")
    parser.add_argument("--source", action="append", type=Path, dest="sources")
    parser.add_argument("--report", type=Path, default=ROOT / "work" / "internal_materials" / "material_enrichment_report.v015.json")
    args = parser.parse_args()

    material_path = args.materials.resolve()
    materials = json.loads(material_path.read_text(encoding="utf-8"))
    sources = [path.resolve() for path in (args.sources or DEFAULT_SOURCES) if path.is_file()]

    report: dict[str, Any] = {
        "createdAt": time.time(),
        "materials": str(material_path),
        "sources": [],
        "addedTables": 0,
        "addedRows": 0,
        "mergedTables": 0,
        "addedLocRows": 0,
    }

    _ensure_rpfm_server()
    for source in sources:
        source_report = merge_source(materials, source)
        report["sources"].append(source_report)
        report["addedTables"] += source_report["addedTables"]
        report["addedRows"] += source_report["addedRows"]
        report["mergedTables"] += source_report["mergedTables"]
        report["addedLocRows"] += source_report["addedLocRows"]

    backup_path = material_path.with_suffix(f".backup-{time.strftime('%Y%m%d%H%M%S')}.json")
    shutil.copy2(material_path, backup_path)
    material_path.write_text(json.dumps(materials, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**report, "backup": str(backup_path)}, ensure_ascii=False, indent=2))


def merge_source(materials: dict[str, Any], source: Path) -> dict[str, Any]:
    _ensure_rpfm_server()
    session = adapter_for("rpfm").open_pack(source)
    source_report = {
        "path": str(source),
        "addedTables": 0,
        "addedRows": 0,
        "mergedTables": 0,
        "addedLocRows": 0,
        "failedTables": [],
    }
    try:
        for table_path in session.list_tables():
            if table_folder(table_path) not in REQUIRED_TABLE_FOLDERS:
                continue
            try:
                rows = session.read_table(table_path)
                source_db = copy.deepcopy(session.decoded_db_by_path[session._resolve_table_path(table_path)])
            except Exception as exc:
                source_report["failedTables"].append({"table": table_path, "error": str(exc)})
                continue
            entry = materials.setdefault("tables", {}).get(table_path)
            if entry is None:
                materials["tables"][table_path] = {
                    "sourcePath": str(source),
                    "tablePath": table_path,
                    "db": source_db,
                    "rows": rows,
                }
                source_report["addedTables"] += 1
                source_report["addedRows"] += len(rows)
                continue
            added = merge_rows(entry.setdefault("rows", []), rows, table_path)
            if added:
                source_report["mergedTables"] += 1
                source_report["addedRows"] += added

        for loc_path in session.list_loc_files():
            try:
                loc_rows = session.read_loc(loc_path)
            except Exception:
                continue
            entry = materials.setdefault("loc", {}).setdefault(loc_path, {"sourcePath": str(source), "rows": {}})
            before = len(entry.setdefault("rows", {}))
            for key, value in loc_rows.items():
                entry["rows"].setdefault(key, value)
            source_report["addedLocRows"] += len(entry["rows"]) - before
    finally:
        session.close()
    return source_report


def merge_rows(target_rows: list[dict[str, Any]], source_rows: list[dict[str, Any]], table_path: str) -> int:
    key_func = row_key_func(table_path)
    existing = {key_func(row) for row in target_rows if key_func(row) is not None}
    added = 0
    for row in source_rows:
        key = key_func(row)
        if key is None or key in existing:
            continue
        target_rows.append(row)
        existing.add(key)
        added += 1
    return added


def row_key_func(table_path: str) -> Any:
    folder = table_folder(table_path)
    if folder == "campaign_character_art_sets_tables":
        return lambda row: row.get("art_set_id")
    if folder == "campaign_character_arts_tables":
        return lambda row: (row.get("art_set_id"), row.get("age"), row.get("level"), row.get("season"), row.get("id"))
    if folder == "character_generation_template_game_mode_details_tables":
        return lambda row: (row.get("character_generation_template"), row.get("game_mode"))
    if folder == "names_tables":
        return lambda row: row.get("id") or (row.get("names_group"), row.get("type"), row.get("gender"))
    if folder == "character_attribute_sets_tables":
        return lambda row: row.get("set_name") or row.get("key")
    if folder == "character_attributes_tables":
        return lambda row: (row.get("set_name"), row.get("attribute_type"), row.get("key"))
    if folder == "ceos_to_equipment_variants_tables":
        return lambda row: (
            row.get("ceos_key"),
            row.get("game_mode"),
            row.get("primary_melee_weapon"),
            row.get("primary_missile_weapon"),
            row.get("armour"),
            row.get("mount"),
        )
    if folder == "retinue_slot_initial_units_tables":
        return lambda row: (row.get("retinue"), row.get("slot_index"), row.get("campaign"))
    if folder == "cai_retinues_to_aspects_tables":
        return lambda row: (row.get("retinue"), row.get("aspect"))
    if folder == "land_units_to_unit_abilites_junctions_tables":
        return lambda row: (row.get("land_unit"), row.get("ability"))
    if folder == "character_skill_level_to_effects_junctions_tables":
        return lambda row: (
            row.get("character_skill_key"),
            row.get("effect_key") or row.get("effect"),
            row.get("effect_scope"),
            row.get("level"),
        )
    if folder == "character_skill_node_links_tables":
        return lambda row: (row.get("parent_key"), row.get("child_key"), row.get("character_skill_node_set_key"))
    if folder == "effects_tables":
        return lambda row: row.get("key") or row.get("effect")
    return lambda row: row.get("key") or row.get("effect") or tuple(sorted(row.items()))


if __name__ == "__main__":
    main()
