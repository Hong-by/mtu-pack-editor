from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.rpfm_ws import RpfmWsClient


PACK_PATH = Path("/Users/hong/Downloads/my_hero.pack")
OUTPUT_PATH = ROOT / "work" / "rpfm_stat_smoke.pack"
TABLE_PATH = "db/melee_weapons_tables/_mtu_characters_weapons"
ROW_KEY = "3k_mtu_general_2h175_comet_spear_unique"
COLUMN = "damage"
NEW_VALUE = 26


def main() -> int:
    client = RpfmWsClient(timeout=180)
    events: list[dict[str, Any]] = []
    try:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        if OUTPUT_PATH.exists():
            OUTPUT_PATH.unlink()

        client.connect()
        _expect_ok(client.send({"SetGameSelected": ["three_kingdoms", False]}))

        opened = client.send({"OpenPackFiles": [str(PACK_PATH)]})
        _expect_ok(opened)
        pack_key = opened["data"]["StringContainerInfo"][0]
        events.append({"opened": pack_key})

        decoded = client.send({"DecodePackedFile": [pack_key, TABLE_PATH, "PackFile"]})
        _expect_ok(decoded)
        db = decoded["data"]["DBRFileInfo"][0]
        before = _patch_db(db, ROW_KEY, COLUMN, NEW_VALUE)
        events.append({"patched": {"row": ROW_KEY, "column": COLUMN, "before": before, "after": NEW_VALUE}})

        saved_file = client.send({"SavePackedFileFromView": [pack_key, TABLE_PATH, {"DB": db}]})
        _expect_ok(saved_file)
        events.append({"savePackedFile": saved_file["data"]})

        saved_pack = client.send({"SavePackAs": [pack_key, str(OUTPUT_PATH)]})
        _expect_ok(saved_pack)
        events.append({"savePackAs": str(OUTPUT_PATH)})

        reopened = client.send({"OpenPackFiles": [str(OUTPUT_PATH)]})
        _expect_ok(reopened)
        output_pack_key = reopened["data"]["StringContainerInfo"][0]
        verify_decoded = client.send({"DecodePackedFile": [output_pack_key, TABLE_PATH, "PackFile"]})
        _expect_ok(verify_decoded)
        verify_db = verify_decoded["data"]["DBRFileInfo"][0]
        verified = _read_value(verify_db, ROW_KEY, COLUMN)
        events.append({"verified": verified})

        ok = verified == NEW_VALUE
        print(json.dumps({"ok": ok, "output": str(OUTPUT_PATH), "events": events}, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "events": events}, ensure_ascii=False, indent=2))
        return 1
    finally:
        client.close()


def _expect_ok(response: dict[str, Any]) -> None:
    data = response.get("data")
    if isinstance(data, dict) and "Error" in data:
        raise RuntimeError(data["Error"])


def _patch_db(db: dict[str, Any], row_key: str, column: str, value: int | float) -> Any:
    table = db["table"]
    fields = [field["name"] for field in table["definition"]["fields"]]
    key_index = fields.index("key")
    column_index = fields.index(column)
    for row in table["table_data"]:
        if _cell_value(row[key_index]) == row_key:
            before = _cell_value(row[column_index])
            row[column_index] = _replace_cell_value(row[column_index], value)
            return before
    raise RuntimeError(f"Row not found: {row_key}")


def _read_value(db: dict[str, Any], row_key: str, column: str) -> Any:
    table = db["table"]
    fields = [field["name"] for field in table["definition"]["fields"]]
    key_index = fields.index("key")
    column_index = fields.index(column)
    for row in table["table_data"]:
        if _cell_value(row[key_index]) == row_key:
            return _cell_value(row[column_index])
    raise RuntimeError(f"Row not found: {row_key}")


def _cell_value(cell: Any) -> Any:
    if isinstance(cell, dict) and len(cell) == 1:
        return next(iter(cell.values()))
    return cell


def _replace_cell_value(cell: Any, value: int | float) -> Any:
    if isinstance(cell, dict) and len(cell) == 1:
        kind = next(iter(cell.keys()))
        return {kind: value}
    return value


if __name__ == "__main__":
    raise SystemExit(main())
