from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from tk_pack_builder.adapters import _raise_rpfm_error, adapter_for


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
    parser = argparse.ArgumentParser(description="Add Korean unit name loc rows to a pack.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--loc-path", default="text/db/mj_women_unit_names.loc")
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if input_path == output_path:
        raise SystemExit("Refusing to overwrite the input pack. Choose a different --output path.")

    session = adapter_for("rpfm").open_pack(input_path)
    try:
        rows = _loc_rows(UNIT_NAMES)
        _write_loc(session, args.loc_path.replace("\\", "/"), rows)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        session.save_as_pack(output_path)
    finally:
        session.close()

    print(f"Wrote {output_path}")
    print(f"Added {len(rows)} loc row(s) to {args.loc_path}")
    return 0


def _loc_rows(unit_names: dict[str, str]) -> dict[str, str]:
    rows: dict[str, str] = {}
    for unit_key, name in unit_names.items():
        rows[f"land_units_onscreen_name_{unit_key}"] = name
        rows[f"main_units_onscreen_name_{unit_key}"] = name
        rows[f"units_onscreen_name_{unit_key}"] = name
    return rows


def _write_loc(session: Any, path: str, rows: dict[str, str]) -> None:
    file_name = path.rsplit("/", 1)[-1].removesuffix(".loc")
    created = session.client.send({"NewPackedFile": [session.pack_key, path, {"Loc": file_name}]})
    _raise_rpfm_error(created)

    decoded = session.client.send({"DecodePackedFile": [session.pack_key, path, "PackFile"]})
    _raise_rpfm_error(decoded)
    loc_db = decoded["data"]["LocRFileInfo"][0]
    table = loc_db["table"]
    fields = [field["name"] for field in table["definition"]["fields"]]
    table["table_data"] = [
        [_encode_loc_cell(field_name, key, text) for field_name in fields]
        for key, text in sorted(rows.items())
    ]

    saved = session.client.send({"SavePackedFileFromView": [session.pack_key, path, {"Loc": loc_db}]})
    _raise_rpfm_error(saved)


def _encode_loc_cell(field_name: str, key: str, text: str) -> dict[str, object]:
    if field_name == "key":
        return {"StringU16": key}
    if field_name == "text":
        return {"StringU16": text}
    if field_name == "tooltip":
        return {"Boolean": True}
    return {"StringU16": ""}


if __name__ == "__main__":
    raise SystemExit(main())
