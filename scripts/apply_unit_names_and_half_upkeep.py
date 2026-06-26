from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from tk_pack_builder.adapters import _decode_rpfm_cell, _encode_rpfm_cell, _raise_rpfm_error, adapter_for


UNIT_NAMES = {
    "3k_ytr_unit_earth_virtuous_noblemen": "현월기",
    "ep_unit_water_qi_crossbowmen": "비노",
    "3k_ytr_unit_metal_arm_of_the_supreme_peace": "철화위",
    "3k_dlc04_unit_fire_tyrant_slayers": "홍련기",
    "3k_dlc04_unit_metal_chosen_of_the_eight_immortals": "검희",
    "ep_unit_wood_qi_guardsmen": "창랑",
    "3k_dlc07_unit_water_northern_mounted_archers": "북궁기",
    "3k_ytr_unit_water_archery_masters": "비연궁",
    "ep_unit_water_archers_of_jing": "형궁희",
    "3k_dlc04_unit_fire_righteous_vanguards": "화선기",
    "3k_dlc04_unit_wood_gallants_of_the_people": "월창",
    "3k_dlc04_unit_earth_messengers_of_heaven": "천월기",
    "3k_ytr_unit_metal_scholar_warriors": "문검랑",
    "3k_ytr_unit_metal_youxia": "유검희",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply final unit names and halve upkeep costs.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--loc-path", default="text/db/mj_women_unit_names.loc")
    args = parser.parse_args()

    if not args.in_place and args.output is None:
        raise SystemExit("Use --in-place or provide --output.")
    input_path = args.input.resolve()
    output_path = args.output.resolve() if args.output else None
    if output_path is not None and output_path == input_path:
        raise SystemExit("Use --in-place to modify the input pack.")

    session = adapter_for("rpfm").open_pack(input_path)
    try:
        loc_count = _write_loc(session, args.loc_path.replace("\\", "/"), _loc_rows(UNIT_NAMES))
        changed = _halve_upkeep(session)
        if args.in_place:
            session.save_pack()
            target = input_path
        else:
            assert output_path is not None
            output_path.parent.mkdir(parents=True, exist_ok=True)
            session.save_as_pack(output_path)
            target = output_path
    finally:
        session.close()

    print(f"Wrote {target}")
    print(f"Name loc rows: {loc_count}")
    print(f"Halved upkeep rows: {changed}")
    return 0


def _loc_rows(unit_names: dict[str, str]) -> dict[str, str]:
    rows: dict[str, str] = {}
    for unit_key, name in unit_names.items():
        rows[f"land_units_onscreen_name_{unit_key}"] = name
        rows[f"main_units_onscreen_name_{unit_key}"] = name
        rows[f"units_onscreen_name_{unit_key}"] = name
    return rows


def _write_loc(session: Any, path: str, rows: dict[str, str]) -> int:
    file_name = path.rsplit("/", 1)[-1].removesuffix(".loc")
    if path not in session.list_loc_files():
        created = session.client.send({"NewPackedFile": [session.pack_key, path, {"Loc": file_name}]})
        _raise_rpfm_error(created)

    decoded = session.client.send({"DecodePackedFile": [session.pack_key, path, "PackFile"]})
    _raise_rpfm_error(decoded)
    loc_db = decoded["data"]["LocRFileInfo"][0]
    table = loc_db["table"]
    fields = [field["name"] for field in table["definition"]["fields"]]
    existing = {}
    for raw_row in table["table_data"]:
        decoded_row = {
            field_name: _decode_rpfm_cell(value)
            for field_name, value in zip(fields, raw_row, strict=False)
        }
        if decoded_row.get("key"):
            existing[str(decoded_row["key"])] = str(decoded_row.get("text", ""))
    existing.update(rows)
    table["table_data"] = [
        [_encode_loc_cell(field_name, key, text) for field_name in fields]
        for key, text in sorted(existing.items())
    ]

    saved = session.client.send({"SavePackedFileFromView": [session.pack_key, path, {"Loc": loc_db}]})
    _raise_rpfm_error(saved)
    return len(rows)


def _encode_loc_cell(field_name: str, key: str, text: str) -> dict[str, object]:
    if field_name == "key":
        return {"StringU16": key}
    if field_name == "text":
        return {"StringU16": text}
    if field_name == "tooltip":
        return {"Boolean": True}
    return {"StringU16": ""}


def _halve_upkeep(session: Any) -> int:
    table_path = _main_units_table(session)
    response = session.client.send({"DecodePackedFile": [session.pack_key, table_path, "PackFile"]})
    _raise_rpfm_error(response)
    db = response["data"]["DBRFileInfo"][0]
    table = db["table"]
    fields = [field["name"] for field in table["definition"]["fields"]]
    try:
        upkeep_index = fields.index("upkeep_cost")
    except ValueError as error:
        raise ValueError(f"upkeep_cost column missing in {table_path}") from error

    changed = 0
    for raw_row in table["table_data"]:
        current = _decode_rpfm_cell(raw_row[upkeep_index])
        if isinstance(current, (int, float)):
            raw_row[upkeep_index] = _encode_rpfm_cell(raw_row[upkeep_index], int(current) // 2)
            changed += 1

    saved = session.client.send({"SavePackedFileFromView": [session.pack_key, table_path, {"DB": db}]})
    _raise_rpfm_error(saved)
    return changed


def _main_units_table(session: Any) -> str:
    matches = [table for table in session.list_tables() if table.startswith("db/main_units_tables/")]
    if len(matches) != 1:
        raise ValueError(f"Expected one main_units table, got {matches}")
    return matches[0]


if __name__ == "__main__":
    raise SystemExit(main())
