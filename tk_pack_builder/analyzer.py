from __future__ import annotations

from dataclasses import dataclass

from .adapters import PackSession
from .game import THREE_KINGDOMS_GAME_KEY
from .stat_tables import TABLE_ALIASES


REQUIRED_TABLES = [
    "equipment_variants_weapons",
    "equipment_variants_armours",
    "melee_weapons",
    "missile_weapons",
    "projectiles",
    "unit_armour_types",
]


@dataclass(frozen=True)
class PackAnalysis:
    pack_name: str
    game_key: str | None
    db_tables: list[str]
    loc_files: list[str]
    asset_files: list[str]
    missing_required_tables: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "packName": self.pack_name,
            "gameKey": self.game_key,
            "dbTables": self.db_tables,
            "locFiles": self.loc_files,
            "assetFiles": self.asset_files,
            "missingRequiredTables": self.missing_required_tables,
        }


def analyze_pack(session: PackSession) -> PackAnalysis:
    tables = session.list_tables()
    metadata = session.metadata()
    return PackAnalysis(
        pack_name=session.pack_path.name,
        game_key=metadata.get("gameKey", THREE_KINGDOMS_GAME_KEY),
        db_tables=tables,
        loc_files=session.list_loc_files(),
        asset_files=session.list_files(),
        missing_required_tables=[
            name for name in REQUIRED_TABLES
            if not any(alias in tables for alias in TABLE_ALIASES[name])
        ],
    )
