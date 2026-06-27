from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .character_clone import CHARACTER_TABLE_ALIASES
from .game import THREE_KINGDOMS_GAME_KEY
from .stat_tables import TABLE_ALIASES


MATERIAL_TABLE_ALIASES = {
    **CHARACTER_TABLE_ALIASES,
    **TABLE_ALIASES,
    "names": [
        "db/names_tables/data__",
    ],
    "character_attribute_sets": [
        "db/character_attribute_sets_tables/data__",
        "db/character_attribute_sets_tables/data",
    ],
    "character_attributes": [
        "db/character_attributes_tables/data__",
        "db/character_attributes_tables/data",
    ],
    "incidents": [
        "db/incidents_tables/event",
        "db/incidents_tables/data__",
    ],
    "cdir_events_incident_payloads": [
        "db/cdir_events_incident_payloads_tables/event",
        "db/cdir_events_incident_payloads_tables/data__",
    ],
    "cdir_events_incident_option_junctions": [
        "db/cdir_events_incident_option_junctions_tables/event",
        "db/cdir_events_incident_option_junctions_tables/data__",
    ],
    "retinues": [
        "db/retinues_tables/data__",
        "db/retinues_tables/unit",
    ],
    "retinue_slot_initial_units": [
        "db/retinue_slot_initial_units_tables/data__",
        "db/retinue_slot_initial_units_tables/unit",
    ],
    "cai_retinues_to_aspects": [
        "db/cai_retinues_to_aspects_tables/data__",
    ],
}


@dataclass
class MaterialPackSession:
    pack_path: Path
    payload: dict[str, Any]
    pack_key: str = "__internal_materials__"
    decoded_db_by_path: dict[str, dict[str, Any]] = field(default_factory=dict)
    metadata_updates: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def open(cls, path: Path) -> "MaterialPackSession":
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return cls(path.resolve(), payload)

    def list_tables(self, source: str = "pack") -> list[str]:
        if source == "vanilla":
            return []
        if source != "pack":
            raise ValueError(f"Unsupported table source: {source}")
        return sorted(self.payload.get("tables", {}).keys())

    def read_table(self, table_name: str, source: str = "pack") -> list[dict[str, Any]]:
        if source == "vanilla":
            return []
        if source != "pack":
            raise ValueError(f"Unsupported table source: {source}")
        path = self._resolve_table_path(table_name, source)
        entry = self.payload.get("tables", {}).get(path)
        if not isinstance(entry, dict):
            raise ValueError(f"Material table not found: {table_name}")
        db = entry.get("db")
        if isinstance(db, dict):
            self.decoded_db_by_path[path] = copy.deepcopy(db)
        rows = entry.get("rows", [])
        if not isinstance(rows, list):
            raise ValueError(f"Material table rows are invalid: {path}")
        return copy.deepcopy(rows)

    def replace_table(self, table_name: str, rows: list[dict[str, Any]]) -> None:
        raise NotImplementedError("MaterialPackSession is read-only.")

    def list_loc_files(self) -> list[str]:
        return sorted(self.payload.get("loc", {}).keys())

    def read_loc(self, loc_path: str) -> dict[str, str]:
        entry = self.payload.get("loc", {}).get(loc_path, {})
        if not isinstance(entry, dict):
            return {}
        rows = entry.get("rows", {})
        if not isinstance(rows, dict):
            return {}
        return {str(key): str(value) for key, value in copy.deepcopy(rows).items()}

    def upsert_loc_rows(self, loc_path: str, rows: dict[str, str]) -> None:
        raise NotImplementedError("MaterialPackSession is read-only.")

    def list_files(self) -> list[str]:
        return sorted(self.payload.get("assets", {}).keys())

    def read_file_bytes(self, packed_path: str) -> bytes:
        raise ValueError(f"Material asset bytes are not embedded: {packed_path}")

    def metadata(self) -> dict[str, Any]:
        return {
            "gameKey": THREE_KINGDOMS_GAME_KEY,
            "adapter": "internal-materials",
            "baseline": self.payload.get("baseline"),
            "materialPath": str(self.pack_path),
            **copy.deepcopy(self.metadata_updates),
        }

    def set_metadata(self, key: str, value: Any) -> None:
        self.metadata_updates[key] = value

    def save_as_pack(self, output_path: Path) -> None:
        raise NotImplementedError("MaterialPackSession is read-only.")

    def save_pack(self) -> None:
        raise NotImplementedError("MaterialPackSession is read-only.")

    def close(self) -> None:
        return None

    def _resolve_table_path(self, table_name: str, source: str = "pack") -> str:
        if source == "vanilla":
            raise ValueError(f"Vanilla table source is not available in materials: {table_name}")
        tables = self.payload.get("tables", {})
        if table_name.startswith(("db/", "ceo_db/")):
            if table_name in tables:
                return table_name
            raise ValueError(f"Material table not found: {table_name}")

        for candidate in MATERIAL_TABLE_ALIASES.get(table_name, []):
            if candidate in tables:
                return candidate

        matches = [
            path for path in self.list_tables(source)
            if f"/{table_name}_tables/" in path or path.split("/")[-1] == table_name
        ]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ValueError(f"Material table not found: {table_name}")
        raise ValueError(f"Material table name is ambiguous: {table_name}: {matches[:5]}")
