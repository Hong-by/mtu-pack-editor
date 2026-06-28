from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .adapters import PackSession


TABLE_ALIASES = {
    "equipment_variants_weapons": [
        "ceos_to_equipment_variants_weapons",
        "db/ceos_to_equipment_variants_tables/_mtu_characters_ceo_weapons",
        "db/ceos_to_equipment_variants_tables/data__",
    ],
    "equipment_variants_armours": [
        "ceos_to_equipment_variants_armours",
        "db/ceos_to_equipment_variants_tables/_mtu_characters_ceo_armours",
        "db/ceos_to_equipment_variants_tables/data__",
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
        "db/land_units_tables/data__",
    ],
    "main_units": [
        "main_units",
        "db/main_units_tables/_mtu_characters_custom_battles_main_units",
        "db/main_units_tables/data__",
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

STRING_COLUMNS = {
    "armour": {
        "audio_type",
    },
}

ALLOWED_COLUMNS = {
    stat_table: set(columns)
    for stat_table, columns in NUMERIC_COLUMNS.items()
}
for stat_table, columns in STRING_COLUMNS.items():
    ALLOWED_COLUMNS.setdefault(stat_table, set()).update(columns)


@dataclass(frozen=True)
class StatTarget:
    stat_table: str
    table_name: str
    row_key: str
    column: str
    value: Any


def resolve_table_name(session: PackSession, alias: str) -> str:
    tables = set(session.list_tables())
    for candidate in TABLE_ALIASES[alias]:
        if candidate in tables:
            return candidate
    raise ValueError(f"Required table is missing: {alias}")


def _matching_table_names(session: PackSession, alias: str) -> list[str]:
    table_list = session.list_tables()
    tables = set(table_list)
    matches: list[str] = []
    for candidate in TABLE_ALIASES[alias]:
        if candidate in tables and candidate not in matches:
            matches.append(candidate)
    folder = (
        "/ceos_to_equipment_variants_tables/"
        if alias in {"equipment_variants_weapons", "equipment_variants_armours"}
        else f"/{alias}_tables/"
    )
    for path in table_list:
        if folder in path and path not in matches:
            matches.append(path)
    if not matches:
        raise ValueError(f"Required table is missing: {alias}")
    return matches


def _read_candidate_rows(session: PackSession, alias: str) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for table_name in _matching_table_names(session, alias):
        try:
            for row in session.read_table(table_name):
                rows.append((table_name, row))
        except Exception:
            continue
    if not rows:
        raise ValueError(f"Required table is missing: {alias}")
    return rows


def _rows_only(source: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    return [row for _, row in source]


def _require_row_with_table(
    rows: list[tuple[str, dict[str, Any]]],
    row_key: str,
    column: str,
    numeric: bool = True,
) -> tuple[str, dict[str, Any]]:
    for table_name, row in rows:
        if row.get("key") == row_key:
            if column not in row:
                raise ValueError(f"Column is missing on stat row: {row_key}/{column}")
            if numeric and not isinstance(row[column], (int, float)):
                raise ValueError(f"Column is not numeric on stat row: {row_key}/{column}")
            return table_name, row
    raise ValueError(f"Stat row is missing: {row_key}")


def resolve_stat_target(
    session: PackSession,
    equipment_key: str,
    stat_table: str,
    column: str,
    value: Any,
    game_mode: str | None,
) -> StatTarget:
    if stat_table not in ALLOWED_COLUMNS:
        raise ValueError(f"Unsupported statTable: {stat_table}")
    if column not in ALLOWED_COLUMNS[stat_table]:
        raise ValueError(f"Column is not allowed for {stat_table}: {column}")
    numeric = column in NUMERIC_COLUMNS.get(stat_table, set())

    if stat_table == "melee_weapon":
        variants = _rows_only(_read_candidate_rows(session, "equipment_variants_weapons"))
        variant = _find_variant(variants, equipment_key, game_mode, "primary_melee_weapon")
        row_key = variant["primary_melee_weapon"]
        target_table, _ = _require_row_with_table(_read_candidate_rows(session, "melee_weapons"), row_key, column)
        return StatTarget(stat_table, target_table, row_key, column, value)

    if stat_table == "armour":
        variants = _rows_only(_read_candidate_rows(session, "equipment_variants_armours"))
        variant = _find_variant_any(variants, _equipment_key_spellings(equipment_key), game_mode, "armour")
        row_key = variant["armour"]
        target_table, _ = _require_row_with_table(_read_candidate_rows(session, "unit_armour_types"), row_key, column, numeric=numeric)
        return StatTarget(stat_table, target_table, row_key, column, value)

    if stat_table == "land_unit":
        row_key = equipment_key
        target_table, _ = _require_row_with_table(_read_candidate_rows(session, "land_units"), row_key, column)
        return StatTarget(stat_table, target_table, row_key, column, value)

    variants = _rows_only(_read_candidate_rows(session, "equipment_variants_weapons"))
    variant = _find_variant(variants, equipment_key, game_mode, "primary_missile_weapon")
    missile_key = variant["primary_missile_weapon"]
    _, missile = _require_row_with_table(_read_candidate_rows(session, "missile_weapons"), missile_key, "default_projectile", numeric=False)
    row_key = missile["default_projectile"]
    target_table, _ = _require_row_with_table(_read_candidate_rows(session, "projectiles"), row_key, column)
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


def _find_variant_any(
    rows: list[dict[str, Any]],
    equipment_keys: list[str],
    game_mode: str | None,
    stat_key_field: str,
) -> dict[str, Any]:
    last_error: ValueError | None = None
    for equipment_key in equipment_keys:
        try:
            return _find_variant(rows, equipment_key, game_mode, stat_key_field)
        except ValueError as error:
            last_error = error
    raise last_error or ValueError(f"Equipment stat mapping not found: {equipment_keys[0] if equipment_keys else ''}")


def _equipment_key_spellings(equipment_key: str) -> list[str]:
    candidates = [equipment_key]
    if "_ancillary_" in equipment_key:
        candidates.append(equipment_key.replace("_ancillary_", "_ancilliary_"))
    if "_ancilliary_" in equipment_key:
        candidates.append(equipment_key.replace("_ancilliary_", "_ancillary_"))
    return list(dict.fromkeys(candidates))


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
