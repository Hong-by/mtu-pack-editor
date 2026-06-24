from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.rpfm_ws import RpfmWsClient


SOURCE_PACK = Path("/Users/hong/Downloads/my_hero.pack")
OUTPUT_PACK = ROOT / "work" / "delta_spike.pack"
SOURCE_TABLE = "db/character_generation_templates_tables/_mtu_characters"
NEW_ROW_KEY = "hby_delta_spike_template"


def main() -> int:
    client = RpfmWsClient()
    try:
        client.connect()
        _raise(client.send({"SetGameSelected": ["three_kingdoms", False]}))
        source_opened = client.send({"OpenPackFiles": [str(SOURCE_PACK)]})
        _raise(source_opened)
        source_key = source_opened["data"]["StringContainerInfo"][0]

        decoded = client.send({"DecodePackedFile": [source_key, SOURCE_TABLE, "PackFile"]})
        _raise(decoded)
        source_db = decoded["data"]["DBRFileInfo"][0]
        delta_db = _single_row_db(source_db)
        table = delta_db["table"]
        table_name = table["table_name"]
        version = table["definition"]["version"]

        new_pack = client.send("NewPack")
        _raise(new_pack)
        target_key = new_pack["data"]["String"]
        _raise(client.send({"SetPackFileType": [target_key, "Mod"]}))
        _raise(client.send({"NewPackedFile": [target_key, SOURCE_TABLE, {"DB": [SOURCE_TABLE, table_name, version]}]}))
        _raise(client.send({"SavePackedFileFromView": [target_key, SOURCE_TABLE, {"DB": delta_db}]}))
        _raise(client.send({"SavePackAs": [target_key, str(OUTPUT_PACK)]}))

        print(json.dumps({
            "ok": True,
            "output": str(OUTPUT_PACK),
            "size": OUTPUT_PACK.stat().st_size,
            "table": SOURCE_TABLE,
            "rowKey": NEW_ROW_KEY,
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    finally:
        client.close()


def _single_row_db(source_db: dict[str, Any]) -> dict[str, Any]:
    db = copy.deepcopy(source_db)
    table = db["table"]
    fields = [field["name"] for field in table["definition"]["fields"]]
    source_row = copy.deepcopy(table["table_data"][0])
    key_index = fields.index("key")
    source_row[key_index] = _with_same_cell_type(source_row[key_index], NEW_ROW_KEY)
    table["table_data"] = [source_row]
    return db


def _with_same_cell_type(cell: Any, value: Any) -> Any:
    if not isinstance(cell, dict) or len(cell) != 1:
        return value
    kind = next(iter(cell.keys()))
    return {kind: value}


def _raise(response: dict[str, Any]) -> None:
    data = response.get("data")
    if isinstance(data, dict) and "Error" in data:
        raise RuntimeError(data["Error"])


if __name__ == "__main__":
    raise SystemExit(main())
