from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.adapters import adapter_for  # noqa: E402
from tk_pack_builder.web import _ensure_rpfm_server  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two Total War pack structures for golden verification.")
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    _ensure_rpfm_server()
    expected = inspect_pack(args.expected.resolve())
    _ensure_rpfm_server()
    actual = inspect_pack(args.actual.resolve())
    diff = compare(expected, actual)
    payload = {
        "ok": not diff["missingTables"] and not diff["extraTables"] and not diff["rowCountMismatches"],
        "expected": expected["path"],
        "actual": actual["path"],
        "diff": diff,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def inspect_pack(path: Path) -> dict[str, Any]:
    session = adapter_for("rpfm").open_pack(path)
    try:
        tables = {}
        for table_path in session.list_tables():
            try:
                rows = session.read_table(table_path)
            except Exception:
                rows = []
            tables[table_path] = {
                "rowCount": len(rows),
                "rowKeys": sorted(row_key(row) for row in rows),
            }
        return {
            "path": str(path),
            "tables": tables,
            "locFiles": sorted(session.list_loc_files()),
            "files": sorted(session.list_files()),
        }
    finally:
        session.close()


def compare(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    expected_tables = set(expected["tables"])
    actual_tables = set(actual["tables"])
    shared_tables = sorted(expected_tables & actual_tables)
    row_count_mismatches = []
    row_key_mismatches = []
    for table in shared_tables:
        expected_info = expected["tables"][table]
        actual_info = actual["tables"][table]
        if expected_info["rowCount"] != actual_info["rowCount"]:
            row_count_mismatches.append({
                "table": table,
                "expected": expected_info["rowCount"],
                "actual": actual_info["rowCount"],
            })
        missing_keys = sorted(set(expected_info["rowKeys"]) - set(actual_info["rowKeys"]))
        extra_keys = sorted(set(actual_info["rowKeys"]) - set(expected_info["rowKeys"]))
        if missing_keys or extra_keys:
            row_key_mismatches.append({
                "table": table,
                "missingKeys": missing_keys[:50],
                "extraKeys": extra_keys[:50],
            })
    return {
        "missingTables": sorted(expected_tables - actual_tables),
        "extraTables": sorted(actual_tables - expected_tables),
        "rowCountMismatches": row_count_mismatches,
        "rowKeyMismatches": row_key_mismatches,
        "missingLocFiles": sorted(set(expected["locFiles"]) - set(actual["locFiles"])),
        "extraLocFiles": sorted(set(actual["locFiles"]) - set(expected["locFiles"])),
        "missingFiles": sorted(set(expected["files"]) - set(actual["files"]))[:200],
        "extraFiles": sorted(set(actual["files"]) - set(expected["files"]))[:200],
    }


def row_key(row: dict[str, Any]) -> str:
    for field in (
        "key",
        "id",
        "character_generation_template",
        "art_set_id",
        "set_name",
        "ceos_key",
        "land_unit",
        "retinue",
    ):
        if field in row:
            if field == "character_generation_template":
                return f"{row.get(field)}::{row.get('game_mode', '')}"
            return str(row.get(field))
    return json.dumps(row, sort_keys=True, ensure_ascii=False)


if __name__ == "__main__":
    main()
