from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


class AssemblyKitCeoError(ValueError):
    """Raised when an Assembly Kit CEO dependency cannot be resolved safely."""


@dataclass(frozen=True)
class DedicatedArmourCeoRequest:
    source_ceo_key: str
    source_initial_ceo_key: str
    new_ceo_key: str
    new_initial_ceo_key: str
    new_armour_type_key: str
    new_equipment_stage_key: str
    armour_value: int


@dataclass(frozen=True)
class DedicatedArmourCeoPlan:
    request: DedicatedArmourCeoRequest
    source_armour_type_key: str
    source_equipment_stage_key: str
    tables: dict[str, list[dict[str, str]]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": {
                "source_ceo_key": self.request.source_ceo_key,
                "source_initial_ceo_key": self.request.source_initial_ceo_key,
                "new_ceo_key": self.request.new_ceo_key,
                "new_initial_ceo_key": self.request.new_initial_ceo_key,
                "new_armour_type_key": self.request.new_armour_type_key,
                "new_equipment_stage_key": self.request.new_equipment_stage_key,
                "armour_value": self.request.armour_value,
            },
            "source_armour_type_key": self.source_armour_type_key,
            "source_equipment_stage_key": self.source_equipment_stage_key,
            "tables": self.tables,
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


_CEO_KEY_REPLACEMENTS: dict[str, tuple[str, ...]] = {
    "ceos": ("key",),
    "ceos_to_equipment_variants": ("ceos_key",),
    "ceo_effect_lists": ("key",),
    "ceo_effect_list_to_effects": ("effect_list",),
    "ceo_group_ceos": ("ceo",),
    "ceo_nodes": ("key", "ceo_effect_list"),
    "ceo_thresholds": ("key", "ceo"),
    "ceo_threshold_nodes": ("ceo_node", "ceo_threshold"),
}

_INITIAL_STAGE_TABLES: tuple[str, ...] = (
    "ceo_initial_data_equipments",
    "ceo_initial_data_active_ceos",
    "ceo_initial_data_active_spawners",
    "ceo_initial_data_triggers",
    "ceo_initial_data_scripted_permissions",
)


def build_dedicated_armour_ceo_plan(
    assembly_kit_raw_db: Path,
    request: DedicatedArmourCeoRequest,
) -> DedicatedArmourCeoPlan:
    """Build a DaVE-ready row plan for a cloned, character-dedicated armour CEO.

    The plan intentionally contains rows only. DaVE owns record UUIDs and BOB
    owns the final ``campaigns/ceo_data.ccd`` compilation.
    """

    db_dir = Path(assembly_kit_raw_db)
    _validate_request(request)

    tables: dict[str, list[dict[str, str]]] = {}

    source_ceo = _one(
        _records(db_dir, "ceos"),
        lambda row: row.get("key") == request.source_ceo_key,
        f"CEO {request.source_ceo_key}",
    )
    tables["ceos"] = [_replace_values(source_ceo, {"key": request.new_ceo_key})]

    source_variants = [
        row
        for row in _records(db_dir, "ceos_to_equipment_variants")
        if row.get("ceos_key") == request.source_ceo_key
    ]
    if not source_variants:
        raise AssemblyKitCeoError(
            f"No ceos_to_equipment_variants row for {request.source_ceo_key}"
        )

    source_armour_keys = _unique_nonempty(row.get("armour") for row in source_variants)
    if len(source_armour_keys) != 1:
        raise AssemblyKitCeoError(
            "Dedicated armour generation requires exactly one source armour type; "
            f"found {source_armour_keys!r} for {request.source_ceo_key}"
        )
    source_armour_type_key = source_armour_keys[0]

    source_armour_type = _one(
        _records(db_dir, "unit_armour_types"),
        lambda row: row.get("key") == source_armour_type_key,
        f"unit armour type {source_armour_type_key}",
    )
    # DaVE validates foreign keys as each table is saved. Materialise the new
    # armour type before the equipment-variant row that references it.
    tables["unit_armour_types"] = [
        _replace_values(
            source_armour_type,
            {
                "key": request.new_armour_type_key,
                "armour_value": str(request.armour_value),
            },
        )
    ]
    tables["ceos_to_equipment_variants"] = [
        _replace_values(
            row,
            {
                "ceos_key": request.new_ceo_key,
                "armour": request.new_armour_type_key,
            },
        )
        for row in source_variants
    ]

    for table_name, columns in _CEO_KEY_REPLACEMENTS.items():
        if table_name in {"ceos", "ceos_to_equipment_variants"}:
            continue
        source_rows = [
            row
            for row in _records(db_dir, table_name)
            if any(row.get(column) == request.source_ceo_key for column in columns)
        ]
        if not source_rows:
            continue
        cloned_rows = []
        for row_index, row in enumerate(source_rows):
            replacements = {
                column: request.new_ceo_key
                for column in columns
                if row.get(column) == request.source_ceo_key
            }
            cloned = _replace_values(row, replacements)
            cloned_rows.append(
                _replace_auto_id(
                    cloned,
                    f"{request.new_ceo_key}:{table_name}:{row_index}",
                )
            )
        tables[table_name] = cloned_rows

    source_initial = _one(
        _records(db_dir, "ceo_initial_datas"),
        lambda row: row.get("key") == request.source_initial_ceo_key,
        f"initial CEO {request.source_initial_ceo_key}",
    )
    tables["ceo_initial_datas"] = [
        _replace_values(source_initial, {"key": request.new_initial_ceo_key})
    ]

    source_to_stages = [
        row
        for row in _records(db_dir, "ceo_initial_data_to_stages")
        if row.get("ceo_initial_data") == request.source_initial_ceo_key
    ]
    if not source_to_stages:
        raise AssemblyKitCeoError(
            f"No initial stages for {request.source_initial_ceo_key}"
        )

    source_equipment_stage_key = _resolve_equipment_stage(
        db_dir,
        source_to_stages,
        request.source_ceo_key,
    )

    cloned_to_stages: list[dict[str, str]] = []
    for row_index, row in enumerate(source_to_stages):
        replacements = {"ceo_initial_data": request.new_initial_ceo_key}
        if row.get("initial_data_stage") == source_equipment_stage_key:
            replacements["initial_data_stage"] = request.new_equipment_stage_key
        cloned = _replace_values(row, replacements)
        cloned_to_stages.append(
            _replace_auto_id(
                cloned,
                f"{request.new_initial_ceo_key}:to_stage:{row_index}",
            )
        )
    source_stage = _one(
        _records(db_dir, "ceo_initial_data_stages"),
        lambda row: row.get("key") == source_equipment_stage_key,
        f"initial equipment stage {source_equipment_stage_key}",
    )
    tables["ceo_initial_data_stages"] = [
        _replace_values(source_stage, {"key": request.new_equipment_stage_key})
    ]
    # DaVE validates references during each table save. Materialise the new
    # stage before the rows that point to it so incremental imports are valid.
    tables["ceo_initial_data_to_stages"] = cloned_to_stages

    for table_name in _INITIAL_STAGE_TABLES:
        source_rows = [
            row
            for row in _records(db_dir, table_name)
            if row.get("initial_data_stage") == source_equipment_stage_key
        ]
        if not source_rows:
            continue
        cloned_rows = []
        for row_index, row in enumerate(source_rows):
            replacements = {"initial_data_stage": request.new_equipment_stage_key}
            if row.get("equipped_ceo") == request.source_ceo_key:
                replacements["equipped_ceo"] = request.new_ceo_key
            if row.get("active_ceo") == request.source_ceo_key:
                replacements["active_ceo"] = request.new_ceo_key
            cloned = _replace_values(row, replacements)
            cloned_rows.append(
                _replace_auto_id(
                    cloned,
                    f"{request.new_equipment_stage_key}:{table_name}:{row_index}",
                )
            )
        tables[table_name] = cloned_rows

    _validate_plan(
        tables,
        request,
        source_armour_type_key,
        source_equipment_stage_key,
    )
    return DedicatedArmourCeoPlan(
        request=request,
        source_armour_type_key=source_armour_type_key,
        source_equipment_stage_key=source_equipment_stage_key,
        tables=tables,
    )


def _records(db_dir: Path, table_name: str) -> list[dict[str, str]]:
    path = db_dir / f"{table_name}.xml"
    if not path.is_file():
        raise AssemblyKitCeoError(f"Assembly Kit table is missing: {path}")
    root = ET.parse(path).getroot()
    rows: list[dict[str, str]] = []
    for element in root.findall(table_name):
        rows.append({child.tag: child.text or "" for child in element})
    return rows


def _one(
    rows: Iterable[dict[str, str]],
    predicate: Any,
    description: str,
) -> dict[str, str]:
    matches = [row for row in rows if predicate(row)]
    if len(matches) != 1:
        raise AssemblyKitCeoError(
            f"Expected exactly one {description} row; found {len(matches)}"
        )
    return matches[0]


def _replace_values(
    row: dict[str, str],
    replacements: dict[str, str],
) -> dict[str, str]:
    cloned = dict(row)
    cloned.update(replacements)
    return cloned


def _replace_auto_id(row: dict[str, str], seed: str) -> dict[str, str]:
    if "auto_id" not in row:
        return row
    cloned = dict(row)
    cloned["auto_id"] = str(_stable_positive_int(seed))
    return cloned


def _stable_positive_int(seed: str) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF or 1


def _unique_nonempty(values: Iterable[str | None]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _resolve_equipment_stage(
    db_dir: Path,
    source_to_stages: list[dict[str, str]],
    source_ceo_key: str,
) -> str:
    linked_stages = {
        row.get("initial_data_stage", "")
        for row in source_to_stages
        if row.get("initial_data_stage")
    }
    matching_stages = _unique_nonempty(
        row.get("initial_data_stage")
        for row in _records(db_dir, "ceo_initial_data_equipments")
        if row.get("equipped_ceo") == source_ceo_key
        and row.get("initial_data_stage") in linked_stages
    )
    if len(matching_stages) != 1:
        raise AssemblyKitCeoError(
            "Expected exactly one initial equipment stage that equips "
            f"{source_ceo_key}; found {matching_stages!r}"
        )
    return matching_stages[0]


def _validate_request(request: DedicatedArmourCeoRequest) -> None:
    key_values = {
        "source_ceo_key": request.source_ceo_key,
        "source_initial_ceo_key": request.source_initial_ceo_key,
        "new_ceo_key": request.new_ceo_key,
        "new_initial_ceo_key": request.new_initial_ceo_key,
        "new_armour_type_key": request.new_armour_type_key,
        "new_equipment_stage_key": request.new_equipment_stage_key,
    }
    missing = [name for name, value in key_values.items() if not str(value).strip()]
    if missing:
        raise AssemblyKitCeoError(f"Blank dedicated armour key(s): {missing}")
    new_values = [
        request.new_ceo_key,
        request.new_initial_ceo_key,
        request.new_armour_type_key,
        request.new_equipment_stage_key,
    ]
    if len(set(new_values)) != len(new_values):
        raise AssemblyKitCeoError("Generated CEO, armour, initial data, and stage keys must differ")
    if not 0 <= int(request.armour_value) <= 500:
        raise AssemblyKitCeoError("armour_value must be between 0 and 500")


def _validate_plan(
    tables: dict[str, list[dict[str, str]]],
    request: DedicatedArmourCeoRequest,
    source_armour_type_key: str,
    source_equipment_stage_key: str,
) -> None:
    required = {
        "ceos",
        "ceos_to_equipment_variants",
        "unit_armour_types",
        "ceo_initial_datas",
        "ceo_initial_data_stages",
        "ceo_initial_data_to_stages",
        "ceo_initial_data_equipments",
    }
    missing = sorted(table for table in required if not tables.get(table))
    if missing:
        raise AssemblyKitCeoError(f"Incomplete dedicated armour plan: {missing}")

    serialized = json.dumps(tables, ensure_ascii=False)
    if source_armour_type_key == request.new_armour_type_key:
        raise AssemblyKitCeoError("Dedicated armour type key still aliases the source")
    if source_equipment_stage_key == request.new_equipment_stage_key:
        raise AssemblyKitCeoError("Dedicated equipment stage key still aliases the source")
    if request.new_ceo_key not in serialized:
        raise AssemblyKitCeoError("Dedicated CEO key was not materialized")

    equipped_rows = tables["ceo_initial_data_equipments"]
    equipped_armours = [
        row.get("equipped_ceo")
        for row in equipped_rows
        if row.get("category") == "3k_main_ceo_category_ancillary_armour"
    ]
    if equipped_armours != [request.new_ceo_key]:
        raise AssemblyKitCeoError(
            "Dedicated initial stage must equip exactly the new armour CEO; "
            f"found {equipped_armours!r}"
        )
