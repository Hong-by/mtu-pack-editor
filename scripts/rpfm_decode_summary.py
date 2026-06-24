from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.rpfm_ws import RpfmWsClient


PACK_PATH = "/Users/hong/Downloads/my_hero.pack"
TARGETS = [
    "db/ceos_to_equipment_variants_tables/_mtu_characters_ceo_weapons",
    "db/ceos_to_equipment_variants_tables/_mtu_characters_ceo_armours",
    "db/effect_bonus_value_ids_unit_sets_tables/_mtu_characters_effects",
    "db/effect_bonus_value_unit_ability_junctions_tables/_mtu_characters_skills_effects",
    "db/effects_tables/_mtu_characters_skills_effects",
    "db/character_skill_level_to_effects_junctions_tables/_mtu_characters_skills",
    "db/special_ability_phase_stat_effects_tables/_mtu_characters_skills_abilities",
    "db/special_ability_phase_attribute_effects_tables/_mtu_characters_skills_abilities",
    "campaigns/ceo_data.ccd",
]


def main() -> int:
    client = RpfmWsClient()
    summaries = []
    try:
        client.connect()
        client.send({"SetGameSelected": ["three_kingdoms", False]})
        opened = client.send({"OpenPackFiles": [PACK_PATH]})
        pack_key = opened["data"]["StringContainerInfo"][0]
        for target in TARGETS:
            decoded = client.send({"DecodePackedFile": [pack_key, target, "PackFile"]})
            summaries.append(_summarize(target, decoded.get("data", {})))
        print(json.dumps({"ok": True, "summaries": summaries}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "summaries": summaries}, ensure_ascii=False, indent=2))
        return 1
    finally:
        client.close()


def _summarize(target: str, data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"path": target, "kind": "RawResponse", "data": data}
    if "Error" in data:
        return {"path": target, "error": data["Error"]}
    if "DBRFileInfo" in data:
        db = data["DBRFileInfo"][0]
        table = db["table"]
        fields = table["definition"]["fields"]
        rows = table["table_data"]
        return {
            "path": target,
            "kind": "DB",
            "tableName": table["table_name"],
            "version": table["definition"]["version"],
            "fieldNames": [field["name"] for field in fields],
            "rowCount": len(rows),
            "sampleRows": rows[:3],
        }
    return {
        "path": target,
        "kind": "Other",
        "keys": list(data.keys()),
        "preview": _shorten(data),
    }


def _shorten(value: Any) -> Any:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) > 4000:
        return text[:4000] + "...<truncated>"
    return value


if __name__ == "__main__":
    raise SystemExit(main())
