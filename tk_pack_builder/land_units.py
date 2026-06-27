from __future__ import annotations

from typing import Any

from .adapters import PackSession
from .recipe import LandUnitClone
from .stat_tables import resolve_table_name


ALLOWED_LAND_UNIT_OVERRIDES = {
    "charge_bonus",
    "morale",
    "primary_ammo",
    "armour",
}


def validate_land_unit_clone(session: PackSession, clone: LandUnitClone) -> None:
    table_name = resolve_table_name(session, "land_units")
    rows = session.read_table(table_name)
    source = _find_row(rows, "key", clone.source_key)
    if source is None:
        raise ValueError(f"Source land unit not found: {clone.source_key}")
    if _find_row(rows, "key", clone.new_key) is not None:
        raise ValueError(f"New land unit already exists: {clone.new_key}")

    unknown_columns = set(clone.overrides) - ALLOWED_LAND_UNIT_OVERRIDES
    if unknown_columns:
        raise ValueError(
            f"Unsupported land unit override column: {', '.join(sorted(unknown_columns))}"
        )
    for column, value in clone.overrides.items():
        if column not in source:
            raise ValueError(f"Column is missing on land unit row: {clone.source_key}/{column}")
        if column == "armour":
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Land unit armour override must be a non-empty string: {clone.new_key}/{column}")
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise ValueError(f"Land unit override must be a non-negative number: {clone.new_key}/{column}")


def apply_land_unit_clones(session: PackSession, clones: list[LandUnitClone]) -> int:
    if not clones:
        return 0

    table_name = resolve_table_name(session, "land_units")
    rows = session.read_table(table_name)
    created = 0
    for clone in clones:
        validate_land_unit_clone(session, clone)
        source = _find_required(rows, "key", clone.source_key)
        rows.append({**source, "key": clone.new_key, **clone.overrides})
        created += 1

    session.replace_table(table_name, rows)
    return created


def _find_row(rows: list[dict[str, Any]], key_field: str, key: str | None) -> dict[str, Any] | None:
    if key is None:
        return None
    for row in rows:
        if row.get(key_field) == key:
            return row
    return None


def _find_required(rows: list[dict[str, Any]], key_field: str, key: str) -> dict[str, Any]:
    row = _find_row(rows, key_field, key)
    if row is None:
        raise ValueError(f"Row not found: {key_field}={key}")
    return row
