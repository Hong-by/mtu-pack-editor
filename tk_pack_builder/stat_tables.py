from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .adapters import PackSession


TABLE_ALIASES = {
    "equipment_variants_weapons": [
        "ceos_to_equipment_variants_weapons",
        "db/ceos_to_equipment_variants_tables/_mtu_characters_ceo_weapons",
    ],
    "equipment_variants_armours": [
        "ceos_to_equipment_variants_armours",
        "db/ceos_to_equipment_variants_tables/_mtu_characters_ceo_armours",
    ],
    "melee_weapons": [
        "melee_weapons",
        "db/melee_weapons_tables/_mtu_characters_weapons",
    ],
    "missile_weapons": [
        "missile_weapons",
        "db/missile_weapons_tables/_mtu_characters_weapons",
    ],
    "projectiles": [
        "projectiles",
        "db/projectiles_tables/_mtu_characters_weapons",
    ],
    "unit_armour_types": [
        "unit_armour_types",
        "db/unit_armour_types_tables/_mtu_characters_skills_abilities",
    ],
    "land_units": [
        "land_units",
        "db/land_units_tables/_mtu_characters_custom_battles_land_units",
    ],
}

NUMERIC_COLUMNS = {
    "melee_weapon": {
        "damage",
        "ap_damage",
        "bonus_v_cavalry",
        "bonus_v_large",
        "bonus_v_infantry",
        "weapon_length",
        "building_damage",
        "splash_attack_max_attacks",
        "splash_attack_power_multiplier",
        "collision_attack_max_targets",
        "collision_attack_max_targets_cooldown",
        "melee_attack_interval",
    },
    "armour": {
        "armour_value",
    },
    "projectile": {
        "effective_range",
        "minimum_range",
        "max_elevation",
        "muzzle_velocity",
        "marksmanship_bonus",
        "spread",
        "damage",
        "ap_damage",
        "base_reload_time",
        "bonus_v_infantry",
        "bonus_v_cavalry",
        "bonus_v_large",
        "burst_size",
        "shots_per_volley",
    },
    "land_unit": {
        "charge_bonus",
        "morale",
        "primary_ammo",
    },
}


@dataclass(frozen=True)
class StatTarget:
    stat_table: str
    table_name: str
    row_key: str
    column: str
    value: int | float


def resolve_table_name(session: PackSession, alias: str) -> str:
    tables = set(session.list_tables())
    for candidate in TABLE_ALIASES[alias]:
        if candidate in tables:
            return candidate
    raise ValueError(f"Required table is missing: {alias}")


def resolve_stat_target(
    session: PackSession,
    equipment_key: str,
    stat_table: str,
    column: str,
    value: int | float,
    game_mode: str | None,
) -> StatTarget:
    if stat_table not in NUMERIC_COLUMNS:
        raise ValueError(f"Unsupported statTable: {stat_table}")
    if column not in NUMERIC_COLUMNS[stat_table]:
        raise ValueError(f"Column is not allowed for {stat_table}: {column}")

    if stat_table == "melee_weapon":
        variants_table = resolve_table_name(session, "equipment_variants_weapons")
        variants = session.read_table(variants_table)
        variant = _find_variant(variants, equipment_key, game_mode, "primary_melee_weapon")
        row_key = variant["primary_melee_weapon"]
        target_table = resolve_table_name(session, "melee_weapons")
        _require_row(session.read_table(target_table), row_key, column)
        return StatTarget(stat_table, target_table, row_key, column, value)

    if stat_table == "armour":
        variants_table = resolve_table_name(session, "equipment_variants_armours")
        variants = session.read_table(variants_table)
        variant = _find_variant(variants, equipment_key, game_mode, "armour")
        row_key = variant["armour"]
        target_table = resolve_table_name(session, "unit_armour_types")
        _require_row(session.read_table(target_table), row_key, column)
        return StatTarget(stat_table, target_table, row_key, column, value)

    if stat_table == "land_unit":
        row_key = equipment_key
        target_table = resolve_table_name(session, "land_units")
        _require_row(session.read_table(target_table), row_key, column)
        return StatTarget(stat_table, target_table, row_key, column, value)

    variants_table = resolve_table_name(session, "equipment_variants_weapons")
    variants = session.read_table(variants_table)
    variant = _find_variant(variants, equipment_key, game_mode, "primary_missile_weapon")
    missile_key = variant["primary_missile_weapon"]
    missile_table = resolve_table_name(session, "missile_weapons")
    missile = _require_row(session.read_table(missile_table), missile_key, "default_projectile", numeric=False)
    row_key = missile["default_projectile"]
    target_table = resolve_table_name(session, "projectiles")
    _require_row(session.read_table(target_table), row_key, column)
    return StatTarget(stat_table, target_table, row_key, column, value)


def _find_variant(
    rows: list[dict[str, Any]],
    equipment_key: str,
    game_mode: str | None,
    stat_key_field: str,
) -> dict[str, Any]:
    matches = [
        row for row in rows
        if row.get("ceos_key") == equipment_key and row.get(stat_key_field)
    ]
    if game_mode is not None:
        matches = [row for row in matches if row.get("game_mode") == game_mode]
    if not matches:
        suffix = f" for gameMode {game_mode}" if game_mode else ""
        raise ValueError(f"Equipment stat mapping not found: {equipment_key}{suffix}")
    if len(matches) > 1 and game_mode is None:
        raise ValueError(f"Equipment stat mapping is ambiguous; provide gameMode: {equipment_key}")
    return matches[0]


def _require_row(
    rows: list[dict[str, Any]],
    row_key: str,
    column: str,
    numeric: bool = True,
) -> dict[str, Any]:
    for row in rows:
        if row.get("key") == row_key:
            if column not in row:
                raise ValueError(f"Column is missing on stat row: {row_key}/{column}")
            if numeric and not isinstance(row[column], (int, float)):
                raise ValueError(f"Column is not numeric on stat row: {row_key}/{column}")
            return row
    raise ValueError(f"Stat row is missing: {row_key}")
