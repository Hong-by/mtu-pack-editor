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
from tk_pack_builder.delta_builder import _db_with_rows, _new_delta_pack  # noqa: E402
from tk_pack_builder.web import _ensure_rpfm_server  # noqa: E402


DEFAULT_MATERIALS = ROOT / "work" / "internal_materials" / "materials.v015.json"
DEFAULT_WRITER_TEMPLATE = ROOT / "work" / "packs" / "my_hero.pack"
DEFAULT_OUTPUT = ROOT / "work" / "packs" / "refs" / "mtu_reference_core.pack"

REFERENCE_TABLE_FOLDERS = {
    "campaign_character_art_sets_tables",
    "campaign_character_arts_tables",
    "cai_retinues_to_aspects_tables",
    "cdir_events_incident_option_junctions_tables",
    "cdir_events_incident_payloads_tables",
    "ceo_initial_datas_tables",
    "ceos_tables",
    "ceo_nodes_tables",
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
    "unit_armour_types_tables",
}

LOC_KEY_PREFIXES = (
    "names_",
    "incidents_",
    "ceo_",
    "ceos_",
    "effects_",
    "hby_",
    "mtu_",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a compact reference-only pack from internal material rows.")
    parser.add_argument("--materials", type=Path, default=DEFAULT_MATERIALS)
    parser.add_argument("--writer-template", type=Path, default=DEFAULT_WRITER_TEMPLATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=ROOT / "work" / "internal_materials" / "reference_core_report.json")
    args = parser.parse_args()

    materials_path = args.materials.resolve()
    output_path = args.output.resolve()
    writer_template = args.writer_template.resolve()
    if not materials_path.is_file():
        raise SystemExit(f"Materials file not found: {materials_path}")
    if not writer_template.is_file():
        raise SystemExit(f"Writer template pack not found: {writer_template}")

    materials = json.loads(materials_path.read_text(encoding="utf-8"))
    tables = select_tables(materials)
    loc_files = select_loc_files(materials)

    _ensure_rpfm_server()
    session = adapter_for("rpfm").open_pack(writer_template)
    try:
        target_key = _new_delta_pack(session)
        written_tables = write_tables(session, target_key, tables)
        written_locs = write_locs(session, target_key, loc_files)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()
        _raise(session.client.send({"SavePackAs": [target_key, str(output_path)]}))
    finally:
        session.close()

    report = {
        "ok": True,
        "createdAt": time.time(),
        "materials": str(materials_path),
        "writerTemplate": str(writer_template),
        "output": str(output_path),
        "outputSizeBytes": output_path.stat().st_size,
        "tableCount": len(written_tables),
        "rowCount": sum(item["rows"] for item in written_tables),
        "locFileCount": len(written_locs),
        "locRowCount": sum(item["rows"] for item in written_locs),
        "tables": written_tables,
        "locFiles": written_locs,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def select_tables(materials: dict[str, Any]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for table_path, entry in sorted(materials.get("tables", {}).items()):
        if table_folder(table_path) not in REFERENCE_TABLE_FOLDERS:
            continue
        rows = entry.get("rows") or []
        db = entry.get("db")
        if not isinstance(rows, list) or not isinstance(db, dict) or not rows:
            continue
        selected[table_path] = {"db": db, "rows": rows}
    return selected


def select_loc_files(materials: dict[str, Any]) -> dict[str, dict[str, str]]:
    selected: dict[str, dict[str, str]] = {}
    for loc_path, entry in sorted(materials.get("loc", {}).items()):
        rows = entry.get("rows") if isinstance(entry, dict) else {}
        if not isinstance(rows, dict):
            continue
        filtered = {
            str(key): str(value)
            for key, value in rows.items()
            if loc_key_wanted(str(key))
        }
        if filtered:
            selected[loc_path] = filtered
    return selected


def loc_key_wanted(key: str) -> bool:
    lower = key.lower()
    return lower.startswith(LOC_KEY_PREFIXES) or "hby" in lower or "mtu" in lower


def write_tables(session: Any, target_key: str, tables: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    written = []
    for table_path, entry in tables.items():
        db = _db_with_rows(entry["db"], clean_rows(entry["rows"]))
        table = db["table"]
        _raise(session.client.send({
            "NewPackedFile": [
                target_key,
                table_path,
                {"DB": [table_path, table["table_name"], table["definition"]["version"]]},
            ]
        }))
        _raise(session.client.send({
            "SavePackedFileFromView": [target_key, table_path, {"DB": db}]
        }))
        written.append({"path": table_path, "rows": len(entry["rows"])})
    return written


def write_locs(session: Any, target_key: str, loc_files: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    written = []
    for loc_path, rows in loc_files.items():
        loc_db = loc_db_from_rows(rows)
        file_name = loc_path.rsplit("/", 1)[-1].removesuffix(".loc")
        _raise(session.client.send({
            "NewPackedFile": [target_key, loc_path, {"Loc": file_name}]
        }))
        _raise(session.client.send({
            "SavePackedFileFromView": [target_key, loc_path, {"Loc": loc_db}]
        }))
        written.append({"path": loc_path, "rows": len(rows)})
    return written


def loc_db_from_rows(rows: dict[str, str]) -> dict[str, Any]:
    table_data = [
        [
            {"data": key, "data_type": "StringU8"},
            {"data": value, "data_type": "StringU8"},
            {"data": True, "data_type": "Boolean"},
        ]
        for key, value in sorted(rows.items())
    ]
    return {
        "table": {
            "definition": {
                "version": 1,
                "fields": [
                    {"name": "key", "field_type": "StringU8", "is_key": True},
                    {"name": "text", "field_type": "StringU8", "is_key": False},
                    {"name": "tooltip", "field_type": "Boolean", "is_key": False},
                ],
            },
            "table_data": table_data,
        }
    }


def clean_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in row.items()
            if not str(key).startswith("_")
        }
        for row in rows
    ]


def table_folder(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    return parts[1] if len(parts) > 2 and parts[0] in {"db", "ceo_db"} else ""


def _raise(response: dict[str, Any]) -> None:
    if response.get("error"):
        raise RuntimeError(str(response["error"]))
    if isinstance(response.get("data"), dict) and response["data"].get("error"):
        raise RuntimeError(str(response["data"]["error"]))


if __name__ == "__main__":
    main()
