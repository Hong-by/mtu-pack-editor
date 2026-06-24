from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.rpfm_ws import RpfmWsClient


PACK_PATH = "/Users/hong/Downloads/my_hero.pack"
TARGET_TABLE = "db/ceos_to_equipment_variants_tables/_mtu_characters_ceo_weapons"


def main() -> int:
    client = RpfmWsClient()
    events = []
    try:
        events.append({"connect": client.connect()})
        events.append({"setGame": client.send({"SetGameSelected": ["three_kingdoms", False]})})
        opened = client.send({"OpenPackFiles": [PACK_PATH]})
        events.append({"openPack": opened})
        pack_key = opened["data"]["StringContainerInfo"][0]
        tree = client.send({"GetPackFileDataForTreeView": pack_key})
        files = tree["data"]["ContainerInfoVecRFileInfo"][1]
        events.append({"treeCount": len(files)})
        decoded = client.send({"DecodePackedFile": [pack_key, TARGET_TABLE, "PackFile"]})
        decoded_data = decoded.get("data", {})
        events.append({"decode": decoded_data})
        print(json.dumps({"ok": True, "events": events}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "events": events}, ensure_ascii=False, indent=2))
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
