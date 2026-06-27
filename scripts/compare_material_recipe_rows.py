from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder import delta_builder as delta  # noqa: E402
from tk_pack_builder.adapters import adapter_for  # noqa: E402
from tk_pack_builder.internal_materials import MaterialPackSession  # noqa: E402
from tk_pack_builder.recipe import load_recipe  # noqa: E402
from tk_pack_builder.web import _ensure_rpfm_server  # noqa: E402


DEFAULT_REFERENCE_PACKS = [
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
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare v0.1.5 pack row collection with internal materials.")
    parser.add_argument("--recipe", type=Path, default=ROOT / "examples" / "recipe.character-clone.json")
    parser.add_argument("--input-pack", type=Path, default=ROOT / "work" / "packs" / "my_hero.pack")
    parser.add_argument("--materials", type=Path, default=ROOT / "work" / "internal_materials" / "materials.v015.json")
    parser.add_argument("--output", type=Path, default=ROOT / "work" / "internal_materials" / "recipe_row_compare.v015.json")
    args = parser.parse_args()

    recipe = load_recipe(args.recipe)
    references = [path for path in DEFAULT_REFERENCE_PACKS if path.is_file()]

    _ensure_rpfm_server()
    pack_session = adapter_for("rpfm").open_pack(args.input_pack.resolve())
    try:
        pack_preview = collect_preview(pack_session, recipe, references)
    finally:
        pack_session.close()

    material_session = MaterialPackSession.open(args.materials.resolve())
    material_preview = collect_preview(material_session, recipe, [])

    diff = compare_previews(pack_preview, material_preview)
    payload = {
        "ok": not diff["missingTables"] and not diff["extraTables"] and not diff["rowCountMismatches"],
        "recipe": str(args.recipe),
        "inputPack": str(args.input_pack),
        "materials": str(args.materials),
        "diff": diff,
        "pack": summarize_preview(pack_preview),
        "materialsPreview": summarize_preview(material_preview),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def collect_preview(session: Any, recipe: Any, reference_paths: list[Path]) -> dict[str, Any]:
    source_dbs: dict[str, dict[str, Any]] = {}
    rows_by_table: dict[str, list[dict[str, Any]]] = {}
    loc_rows: dict[str, str] = {}
    opened_pack_keys = {str(session.pack_path.resolve()): session.pack_key}

    counts = {
        "stats": delta._collect_stat_patch_rows(session, recipe, source_dbs, rows_by_table),
        "landUnits": delta._collect_land_unit_clone_rows(session, recipe, source_dbs, rows_by_table),
        "attributeSets": delta._collect_attribute_set_clone_rows(session, recipe.attribute_set_clones, source_dbs, rows_by_table, reference_paths, opened_pack_keys),
        "skillSets": delta._collect_skill_set_clone_rows(session, recipe.skill_set_clones, source_dbs, rows_by_table, reference_paths, opened_pack_keys),
        "ageRanges": delta._collect_age_range_clone_rows(session, recipe.age_range_clones, source_dbs, rows_by_table, reference_paths, opened_pack_keys),
        "characterPatches": delta._collect_character_patch_rows(session, recipe.character_patches, source_dbs, rows_by_table),
        "characterClones": delta._collect_character_clone_rows(session, recipe.character_clones, source_dbs, rows_by_table, loc_rows, reference_paths, opened_pack_keys),
        "dependencies": delta._collect_character_dependency_rows(session, recipe.character_clones, source_dbs, rows_by_table, reference_paths, opened_pack_keys),
    }
    return {
        "counts": counts,
        "rowsByTable": {
            table: sorted(row_identity(row) for row in rows)
            for table, rows in rows_by_table.items()
        },
        "locKeys": sorted(loc_rows),
        "sourceDbTables": sorted(source_dbs),
    }


def compare_previews(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    expected_tables = set(expected["rowsByTable"])
    actual_tables = set(actual["rowsByTable"])
    shared = sorted(expected_tables & actual_tables)
    row_count_mismatches = []
    row_key_mismatches = []
    for table in shared:
        expected_rows = expected["rowsByTable"][table]
        actual_rows = actual["rowsByTable"][table]
        if len(expected_rows) != len(actual_rows):
            row_count_mismatches.append({"table": table, "expected": len(expected_rows), "actual": len(actual_rows)})
        missing = sorted(set(expected_rows) - set(actual_rows))
        extra = sorted(set(actual_rows) - set(expected_rows))
        if missing or extra:
            row_key_mismatches.append({"table": table, "missing": missing[:50], "extra": extra[:50]})
    return {
        "missingTables": sorted(expected_tables - actual_tables),
        "extraTables": sorted(actual_tables - expected_tables),
        "rowCountMismatches": row_count_mismatches,
        "rowKeyMismatches": row_key_mismatches,
        "missingLocKeys": sorted(set(expected["locKeys"]) - set(actual["locKeys"])),
        "extraLocKeys": sorted(set(actual["locKeys"]) - set(expected["locKeys"])),
    }


def summarize_preview(preview: dict[str, Any]) -> dict[str, Any]:
    return {
        "counts": preview["counts"],
        "tableCount": len(preview["rowsByTable"]),
        "rowCount": sum(len(rows) for rows in preview["rowsByTable"].values()),
        "locKeyCount": len(preview["locKeys"]),
    }


def row_identity(row: dict[str, Any]) -> str:
    for fields in (
        ("key",),
        ("id",),
        ("character_generation_template", "game_mode"),
        ("art_set_id", "age", "is_female", "has_come_of_age"),
        ("set_name", "attribute_type"),
        ("parent_key", "child_key", "link_type"),
        ("retinue", "slot_index", "campaign"),
        ("land_unit", "ability"),
    ):
        if all(field in row for field in fields):
            return "::".join(str(row.get(field)) for field in fields)
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


if __name__ == "__main__":
    main()
