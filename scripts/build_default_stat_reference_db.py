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
    _ensure_rpfm_server,
    _read_character_alias_rows,
    _resolve_stat_table,
)


DEFAULT_SOURCE_PACK = ROOT / "work" / "packs" / "refs" / "database.pack"
DEFAULT_OUTPUT = ROOT / "work" / "internal_dbs" / "default_stat_reference.json"

STAT_ALIASES = (
    "ceo_initial_datas",
    "equipment_variants_weapons",
    "equipment_variants_armours",
    "melee_weapons",
    "missile_weapons",
    "projectiles",
    "unit_armour_types",
    "land_units",
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract vanilla/DLC equipment and land unit stat rows into an internal JSON DB."
    )
    parser.add_argument("--source-pack", type=Path, default=DEFAULT_SOURCE_PACK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source_pack = args.source_pack.expanduser().resolve()
    if not source_pack.is_file():
        raise SystemExit(f"Source pack not found: {source_pack}")

    _ensure_rpfm_server()
    session = adapter_for("rpfm").open_pack(source_pack)
    try:
        tables = _read_stat_tables(session)
    finally:
        close = getattr(session, "close", None)
        if close:
            close()

    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "createdAt": time.time(),
        "sourcePack": str(source_pack),
        "tables": tables,
        "counts": {key: len(value) for key, value in tables.items()},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))
    print(f"Wrote {args.output}")
    return 0


def _read_stat_tables(session: Any) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for alias in STAT_ALIASES:
        try:
            if alias in CHARACTER_TABLE_ALIASES:
                tables[alias] = _read_character_alias_rows(session, alias, "pack")
            else:
                table_name = _resolve_stat_table(session, alias, "pack")
                tables[alias] = [
                    {**row, "_sourceTableName": table_name}
                    for row in session.read_table(table_name, "pack")
                ]
        except (KeyError, ValueError):
            tables[alias] = []
    return tables


if __name__ == "__main__":
    raise SystemExit(main())
