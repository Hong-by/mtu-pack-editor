from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.rpfm_ws import RpfmWsClient


def main() -> int:
    client = RpfmWsClient()
    events = []
    try:
        events.append({"connect": client.connect()})
        events.append({"schemasPath": client.send("SchemasPath")})
        events.append({"setGame": client.send({"SetGameSelected": ["three_kingdoms", False]})})
        events.append({"isSchemaLoadedBefore": client.send("IsSchemaLoaded")})
        events.append({"checkSchemaUpdates": client.send("CheckSchemaUpdates")})
        events.append({"updateSchemas": client.send("UpdateSchemas")})
        events.append({"setGameAfterUpdate": client.send({"SetGameSelected": ["three_kingdoms", False]})})
        events.append({"isSchemaLoadedAfter": client.send("IsSchemaLoaded")})
        print(json.dumps({"ok": True, "events": events}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "events": events}, ensure_ascii=False, indent=2))
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
