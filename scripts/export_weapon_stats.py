from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from tk_pack_builder.adapters import _decode_rpfm_cell, _raise_rpfm_error
from tk_pack_builder.game import THREE_KINGDOMS_GAME_KEY
from tk_pack_builder.rpfm_ws import RpfmWsClient


TABLE_MARKERS = ("melee_weapons_tables", "missile_weapons_tables", "projectiles_tables")


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize referenced unit weapon stats.")
    parser.add_argument("--unit-csv", required=True, type=Path)
    parser.add_argument("--refs", nargs="+", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    units = _read_units(args.unit_csv)
    found = _read_reference_weapon_rows([path.resolve() for path in args.refs if path.exists()])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_markdown(units, found), encoding="utf-8")
    print(args.output)
    return 0


def _read_units(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _weapon_keys(units: list[dict[str, str]]) -> set[str]:
    keys = set()
    for unit in units:
        for column in ("primary_melee_weapon", "primary_missile_weapon"):
            if unit.get(column):
                keys.add(unit[column])
    return keys


def _read_reference_weapon_rows(refs: list[Path]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    client = RpfmWsClient()
    client.connect()
    try:
        _raise_rpfm_error(client.send({"SetGameSelected": [THREE_KINGDOMS_GAME_KEY, False]}))
        for ref in refs:
            opened = client.send({"OpenPackFiles": [str(ref)]})
            _raise_rpfm_error(opened)
            pack_key = opened["data"]["StringContainerInfo"][0]
            tree = client.send({"GetPackFileDataForTreeView": pack_key})
            _raise_rpfm_error(tree)
            infos = tree["data"]["ContainerInfoVecRFileInfo"][1]
            table_paths = [
                info["path"]
                for info in infos
                if info.get("path", "").startswith("db/")
                and any(marker in info.get("path", "") for marker in TABLE_MARKERS)
            ]
            for table_path in table_paths:
                decoded = client.send({"DecodePackedFile": [pack_key, table_path, "PackFile"]})
                data = decoded.get("data", {})
                if isinstance(data, dict) and "Error" in data:
                    continue
                if "DBRFileInfo" not in data:
                    continue
                db = data["DBRFileInfo"][0]
                table = db["table"]
                fields = [field["name"] for field in table["definition"]["fields"]]
                for raw_row in table["table_data"]:
                    row = {
                        field_name: _decode_rpfm_cell(value)
                        for field_name, value in zip(fields, raw_row, strict=False)
                    }
                    key = str(row.get("key", ""))
                    if key and key not in found:
                        found[key] = {"source": ref.name, "table": table_path, "row": row}
    finally:
        client.close()
    return found


def _markdown(units: list[dict[str, str]], found: dict[str, dict[str, Any]]) -> str:
    lines = [
        "# 무기 스탯 요약",
        "",
        "| # | 이름 | 근접무기 | 피해/AP | 대기병/대대형/대보병 | 길이 | 원거리무기 | 탄 피해/AP | 사거리 | 재장전 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for index, unit in enumerate(units, 1):
        melee = found.get(unit.get("primary_melee_weapon", ""))
        missile = found.get(unit.get("primary_missile_weapon", ""))
        melee_row = melee["row"] if melee else {}
        missile_row = missile["row"] if missile else {}
        projectile_row = {}
        projectile_key = missile_row.get("default_projectile")
        if projectile_key and projectile_key in found:
            projectile_row = found[projectile_key]["row"]
        lines.append(
            "| "
            + " | ".join(
                str(value)
                for value in (
                    index,
                    unit.get("korean_name", ""),
                    unit.get("primary_melee_weapon", ""),
                    _damage(melee_row),
                    _bonuses(melee_row),
                    melee_row.get("weapon_length", ""),
                    unit.get("primary_missile_weapon", ""),
                    _damage(projectile_row),
                    projectile_row.get("effective_range", ""),
                    projectile_row.get("base_reload_time", ""),
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _damage(row: dict[str, Any]) -> str:
    if not row:
        return ""
    return f"{row.get('damage', '')}/{row.get('ap_damage', '')}"


def _bonuses(row: dict[str, Any]) -> str:
    if not row:
        return ""
    return f"{row.get('bonus_v_cavalry', '')}/{row.get('bonus_v_large', '')}/{row.get('bonus_v_infantry', '')}"


if __name__ == "__main__":
    raise SystemExit(main())
