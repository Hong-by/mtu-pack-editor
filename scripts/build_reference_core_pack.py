from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.adapters import adapter_for  # noqa: E402
from tk_pack_builder.delta_builder import _db_with_rows, _loc_db_with_rows, _new_delta_pack  # noqa: E402
from tk_pack_builder.web import _ensure_rpfm_server  # noqa: E402
from scripts.build_internal_materials_v015 import MERGED_KOREAN_LOC_PATH, _loc_source_priority  # noqa: E402


DEFAULT_MATERIALS = ROOT / "work" / "internal_materials" / "materials.v015.json"
DEFAULT_WRITER_TEMPLATE = ROOT / "work" / "packs" / "my_hero.pack"
DEFAULT_OUTPUT = ROOT / "work" / "packs" / "refs" / "mtu_reference_core.pack"

REFERENCE_TABLE_FOLDERS = {
    "campaign_character_art_sets_tables",
    "campaign_character_arts_tables",
    "ceo_initial_datas_tables",
    "ceos_tables",
    "ceo_nodes_tables",
    "ceos_to_equipment_variants_tables",
    "character_attribute_sets_tables",
    "character_attributes_tables",
    "frontend_character_ceos_tables",
    "character_generation_spawn_age_ranges_tables",
    "character_generation_template_game_mode_details_tables",
    "character_generation_templates_tables",
    "character_skill_level_to_effects_junctions_tables",
    "character_skill_node_links_tables",
    "character_skill_node_sets_tables",
    "character_skill_nodes_tables",
    "effects_tables",
    "land_units_tables",
    "melee_weapons_tables",
    "missile_weapons_tables",
    "projectiles_tables",
    "unit_armour_types_tables",
}

TR_REFERENCE_RE = re.compile(r"\{\{tr:([^}]+)\}\}")

REFERENCE_LOC_GLOBAL_PREFIXES = (
    "names_name_",
    "names_alt_name_",
    "ceo_nodes_title_",
    "ceo_nodes_description_",
    "character_skills_localised_name_",
    "character_skills_localised_description_",
    "character_skill_level_details_localised_name_",
    "character_skill_level_details_localised_description_",
    "frontend_characters_optional_name_override_",
    "frontend_faction_leader_unique_characters_localised_description_",
    "land_units_onscreen_name_",
    "land_units_concealed_name_",
    "unit_abilities_onscreen_name_",
    "ancillaries_onscreen_name_",
    "ancillaries_description_",
    "incidents_localised_title_",
    "incidents_localised_description_",
)

REFERENCE_LOC_VALUE_PREFIXES = (
    "",
    "names_name_",
    "names_alt_name_",
    "ceo_nodes_title_",
    "ceo_nodes_description_",
    "character_skills_localised_name_",
    "character_skills_localised_description_",
    "character_skill_level_details_localised_name_0",
    "character_skill_level_details_localised_name_1",
    "character_skill_level_details_localised_description_0",
    "character_skill_level_details_localised_description_1",
    "frontend_characters_optional_name_override_",
    "frontend_faction_leader_unique_characters_localised_description_",
    "land_units_onscreen_name_",
    "land_units_concealed_name_",
    "unit_abilities_onscreen_name_",
    "ancillaries_onscreen_name_",
    "ancillaries_description_",
    "incidents_localised_title_",
    "incidents_localised_description_",
)

KOREA_REFERENCE_TABLE_MARKERS = (
    "ironic_addon_korea",
    "ironic_korea",
    "korean_unique",
    "korean_unque",
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
    loc_files = select_loc_files(materials, tables)

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
        if table_folder(table_path) not in REFERENCE_TABLE_FOLDERS and not is_korea_reference_table(table_path):
            continue
        rows = entry.get("rows") or []
        db = entry.get("db")
        if not isinstance(rows, list) or not isinstance(db, dict) or not rows:
            continue
        if not can_write_table(db, rows):
            continue
        selected[table_path] = {"db": db, "rows": rows}
    return selected


def is_korea_reference_table(table_path: str) -> bool:
    lower = table_path.lower()
    return any(marker in lower for marker in KOREA_REFERENCE_TABLE_MARKERS)


def can_write_table(db: dict[str, Any], rows: list[dict[str, Any]]) -> bool:
    try:
        _db_with_rows(db, clean_rows(rows))
    except Exception:
        return False
    return True


def select_loc_files(
    materials: dict[str, Any],
    tables: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, str]]:
    all_rows: dict[str, str] = {}
    priorities: dict[str, tuple[int, str, str]] = {}
    for loc_path, entry in sorted(materials.get("loc", {}).items()):
        rows = entry.get("rows") if isinstance(entry, dict) else {}
        if not isinstance(rows, dict):
            continue
        original_loc_path = str(entry.get("locPath") or loc_path).split("#source=", 1)[0]
        source_path = str(entry.get("sourcePath") or "")
        priority = _loc_source_priority(source_path, original_loc_path)
        for key, value in rows.items():
            key_text = str(key)
            rank = (priority, source_path, original_loc_path)
            if key_text not in all_rows or rank >= priorities[key_text]:
                all_rows[key_text] = str(value)
                priorities[key_text] = rank

    if not all_rows:
        return {}
    selected_keys = collect_reference_loc_keys(tables or select_tables(materials), all_rows)
    selected_rows = {
        key: all_rows[key]
        for key in sorted(selected_keys)
        if key in all_rows
    }
    return {MERGED_KOREAN_LOC_PATH: selected_rows} if selected_rows else {}


def collect_reference_loc_keys(
    tables: dict[str, dict[str, Any]],
    all_rows: dict[str, str],
) -> set[str]:
    keys: set[str] = {
        key
        for key in all_rows
        if key.startswith(REFERENCE_LOC_GLOBAL_PREFIXES)
    }
    for table_path, entry in tables.items():
        rows = entry.get("rows") or []
        for row in rows:
            if isinstance(row, dict):
                keys.update(_loc_keys_for_row(row, table_path, all_rows))
    keys.update(_referenced_loc_keys(all_rows, keys))
    return {key for key in keys if key in all_rows}


def _loc_keys_for_row(row: dict[str, Any], table_path: str, all_rows: dict[str, str]) -> set[str]:
    keys: set[str] = set()
    folder = table_folder(table_path)
    for field, raw_value in row.items():
        if str(field).startswith("_"):
            continue
        for token in _loc_tokens(raw_value):
            keys.update(_loc_keys_for_token(token, all_rows))
            if field == "initial_ceos":
                keys.update(_title_loc_keys_for_initial_ceo(token, row, all_rows))
            if field == "character_generation_template":
                keys.update(_frontend_character_loc_keys(token, all_rows))
            if folder == "names_tables":
                keys.update(_name_loc_keys(token, all_rows))
    return keys


def _loc_tokens(value: Any) -> list[str]:
    if value is None or isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [str(value)]
    text = str(value).strip()
    return [text] if text else []


def _loc_keys_for_token(token: str, all_rows: dict[str, str]) -> set[str]:
    keys: set[str] = set()
    for prefix in REFERENCE_LOC_VALUE_PREFIXES:
        candidate = f"{prefix}{token}"
        if candidate in all_rows:
            keys.add(candidate)
        for suffix in ("_alt_1", "_alt_2"):
            alt_candidate = f"{prefix}{token}{suffix}"
            if alt_candidate in all_rows:
                keys.add(alt_candidate)
    return keys


def _name_loc_keys(token: str, all_rows: dict[str, str]) -> set[str]:
    return {
        key
        for key in (f"names_name_{token}", f"names_alt_name_{token}")
        if key in all_rows
    }


def _frontend_character_loc_keys(token: str, all_rows: dict[str, str]) -> set[str]:
    return {
        key
        for key in (
            f"frontend_characters_optional_name_override_{token}",
            f"frontend_faction_leader_unique_characters_localised_description_{token}",
        )
        if key in all_rows
    }


def _title_loc_keys_for_initial_ceo(
    initial_ceo_key: str,
    row: dict[str, Any],
    all_rows: dict[str, str],
) -> set[str]:
    token = _character_token_from_initial_ceo(initial_ceo_key)
    template_key = str(row.get("character_generation_template") or "")
    keys: set[str] = set()
    for candidate in _title_candidate_keys(token, initial_ceo_key, template_key):
        for loc_key in (f"ceo_nodes_title_{candidate}", f"ceo_nodes_description_{candidate}"):
            if loc_key in all_rows:
                keys.add(loc_key)
    return keys


def _character_token_from_initial_ceo(initial_key: str) -> str:
    token = initial_key
    for marker in (
        "ceo_initial_data_character_historical_",
        "ceo_initial_data_character_romance_",
        "ceo_initial_data_character_",
        "initial_data_character_historical_",
        "initial_data_character_romance_",
        "initial_data_character_",
    ):
        if marker in token:
            token = token.split(marker, 1)[1]
            break
    return token.removeprefix("lady_")


def _title_candidate_keys(token: str, source_key: str = "", template_key: str = "") -> list[str]:
    if not token:
        return []
    normalized = token.removeprefix("lady_")
    tokens = [normalized]
    if token != normalized:
        tokens.append(token)
    candidates: list[str] = []
    for prefix in _title_prefix_candidates(source_key, template_key):
        for item in tokens:
            candidates.append(f"{prefix}_ceo_node_career_historical_{item}_01")
    return candidates


def _title_prefix_candidates(source_key: str, template_key: str = "") -> tuple[str, ...]:
    preferred: list[str] = []
    text = str(source_key or "")
    template_text = str(template_key or "")
    for prefix in ("3k_dlc05", "3k_dlc04", "3k_dlc06", "3k_dlc07", "3k_ytr", "ep", "3k_main"):
        if text.startswith(f"{prefix}_") or f"_{prefix}_" in text:
            preferred.append(prefix)
    if template_text.startswith(("3k_mod_template_", "ironic_template_")):
        preferred = preferred or ["3k_main"]
    if "3k_mtu" not in preferred:
        preferred.append("3k_mtu")
    for prefix in ("3k_mtu", "3k_dlc05", "3k_dlc04", "3k_dlc06", "3k_dlc07", "3k_ytr", "ep", "3k_main"):
        if prefix not in preferred:
            preferred.append(prefix)
    return tuple(preferred)


def _referenced_loc_keys(all_rows: dict[str, str], initial_keys: set[str]) -> set[str]:
    found: set[str] = set()
    pending = list(initial_keys)
    while pending:
        key = pending.pop()
        value = all_rows.get(key, "")
        for match in TR_REFERENCE_RE.finditer(value):
            ref_key = match.group(1)
            if ref_key in all_rows and ref_key not in found and ref_key not in initial_keys:
                found.add(ref_key)
                pending.append(ref_key)
    return found


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
        loc_db = _loc_db_with_rows(session, rows)
        file_name = loc_path.rsplit("/", 1)[-1].removesuffix(".loc")
        _raise(session.client.send({
            "NewPackedFile": [target_key, loc_path, {"Loc": file_name}]
        }))
        _raise(session.client.send({
            "SavePackedFileFromView": [target_key, loc_path, {"Loc": loc_db}]
        }))
        written.append({"path": loc_path, "rows": len(rows)})
    return written


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
