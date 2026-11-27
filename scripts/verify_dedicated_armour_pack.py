from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tk_pack_builder.adapters import adapter_for
from tk_pack_builder import ceo_ccd as ceo_ccd_module
from tk_pack_builder.ceo_ccd import CeoCcd, initial_ceo_active_ceos
from tk_pack_builder.pfh import find_entry, read_entry_bytes, read_pfh_index
from tk_pack_builder.web_runtime import _ensure_rpfm_server


DEFAULT_PACK = ROOT / "output" / "dedicated_armour_e2e.pack"
DEFAULT_CEO_KEY = "hby_mtu_ancillary_armour_dedicated_001"
DEFAULT_INITIAL_CEO_KEY = "hby_mtu_ceo_initial_data_character_dedicated_001"
DEFAULT_ARMOUR_KEY = "hby_mtu_armour_dedicated_001"
DEFAULT_TEMPLATE_KEY = "hby_e2e_template_ma_yunlu_dedicated_armour"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reopen a generated pack and verify a dedicated-armour clone end to end."
    )
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--base-pack", type=Path)
    parser.add_argument("--ceo-key", default=DEFAULT_CEO_KEY)
    parser.add_argument("--initial-ceo-key", default=DEFAULT_INITIAL_CEO_KEY)
    parser.add_argument("--armour-key", default=DEFAULT_ARMOUR_KEY)
    parser.add_argument("--template-key", default=DEFAULT_TEMPLATE_KEY)
    parser.add_argument("--armour-value", type=int, default=88)
    parser.add_argument("--expected-art-set")
    parser.add_argument("--armour-title")
    parser.add_argument("--source-initial-ceo-key")
    parser.add_argument("--source-armour-ceo-key")
    parser.add_argument(
        "--runtime-initial-ceo-key",
        help=(
            "Initial CEO key referenced by the generated template. "
            "Defaults to the dedicated initial key."
        ),
    )
    args = parser.parse_args()

    report = verify_pack(
        pack_path=args.pack.expanduser().resolve(),
        base_pack=args.base_pack.expanduser().resolve() if args.base_pack else None,
        ceo_key=args.ceo_key,
        initial_ceo_key=args.initial_ceo_key,
        armour_key=args.armour_key,
        template_key=args.template_key,
        armour_value=args.armour_value,
        expected_art_set=args.expected_art_set,
        armour_title=args.armour_title,
        source_initial_ceo_key=args.source_initial_ceo_key,
        source_armour_ceo_key=args.source_armour_ceo_key,
        runtime_initial_ceo_key=args.runtime_initial_ceo_key,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def verify_pack(
    *,
    pack_path: Path,
    base_pack: Path | None,
    ceo_key: str,
    initial_ceo_key: str,
    armour_key: str,
    template_key: str,
    armour_value: int,
    expected_art_set: str | None,
    armour_title: str | None = None,
    source_initial_ceo_key: str | None = None,
    source_armour_ceo_key: str | None = None,
    runtime_initial_ceo_key: str | None = None,
) -> dict[str, Any]:
    if not pack_path.is_file():
        raise FileNotFoundError(pack_path)

    index = read_pfh_index(pack_path)
    if index.pack_type != "Mod":
        raise RuntimeError(f"Expected a Mod pack, got {index.pack_type}: {pack_path}")
    ccd_entry = find_entry(index, "campaigns/ceo_data.ccd")
    output_ccd = read_entry_bytes(pack_path, ccd_entry)
    output_document = CeoCcd.from_bytes(output_ccd)
    output_strings = Counter(output_document.all_strings())
    ceo_definition_strings = _keyed_record_group_strings(
        output_document,
        "CEO_TABLE_POPULATE",
        ceo_key,
    )
    ceo_effect_strings = _keyed_record_group_strings(
        output_document,
        "EFFECTS_LIST_TABLE_POPULATE",
        ceo_key,
    )
    spawner_key = ceo_key.replace("_ancillary_", "_ceo_spawner_", 1)
    spawner_strings = _keyed_record_group_strings(
        output_document,
        "SPAWNER_TABLE_POPULATE",
        spawner_key,
    )

    if output_strings[ceo_key] < 1:
        raise RuntimeError(f"Dedicated armour CEO key is missing from CCD: {ceo_key}")
    if output_strings[initial_ceo_key] < 1:
        raise RuntimeError(f"Dedicated initial CEO key is missing from CCD: {initial_ceo_key}")
    if "unique" in ceo_definition_strings:
        raise RuntimeError("Generated armour CEO still uses unique rarity.")
    if "3k_dummy_effect_ceo_subcategory_armour_unique" in ceo_effect_strings:
        raise RuntimeError("Generated armour CEO still uses the unique armour subcategory.")
    if "3k_dummy_effect_ceo_subcategory_armour_metal" not in ceo_effect_strings:
        raise RuntimeError("Generated armour CEO is missing the normal metal armour subcategory.")
    if ceo_key not in spawner_strings:
        raise RuntimeError("Generated armour CEO is missing its normal armour spawner.")

    initial_active_ceos = initial_ceo_active_ceos(
        output_document,
        initial_ceo_key,
    )
    if source_initial_ceo_key or source_armour_ceo_key:
        if not source_initial_ceo_key or not source_armour_ceo_key:
            raise RuntimeError(
                "Both source initial CEO and source armour CEO keys are required."
            )
        source_active_ceos = initial_ceo_active_ceos(
            output_document,
            source_initial_ceo_key,
        )
        expected_active_ceos = [
            ceo_key if key == source_armour_ceo_key else key
            for key in source_active_ceos
        ]
        if initial_active_ceos != expected_active_ceos:
            raise RuntimeError(
                "Dedicated initial CEO did not preserve the complete source CEO set."
            )

    preserved_string_count = None
    if base_pack is not None:
        base_index = read_pfh_index(base_pack)
        base_entry = find_entry(base_index, "campaigns/ceo_data.ccd")
        base_document = CeoCcd.from_bytes(read_entry_bytes(base_pack, base_entry))
        base_strings = Counter(base_document.all_strings())
        lost = {
            key: count - output_strings[key]
            for key, count in base_strings.items()
            if output_strings[key] < count
        }
        if lost:
            examples = list(lost.items())[:10]
            raise RuntimeError(f"Base CCD strings were lost: {examples}")
        preserved_string_count = sum(base_strings.values())

    _ensure_rpfm_server()
    session = adapter_for("rpfm").open_pack(pack_path)
    try:
        initial = _find_row(
            _read_all_table_rows(session, "ceo_initial_datas"),
            "key",
            initial_ceo_key,
        )
        variant = _find_row(
            _read_all_table_rows(session, "ceos_to_equipment_variants"),
            "ceos_key",
            ceo_key,
        )
        armour = _find_row(
            _read_all_table_rows(session, "unit_armour_types"),
            "key",
            armour_key,
        )
        template = _find_row(session.read_table("character_generation_templates"), "key", template_key)
        detail_rows = [
            row
            for row in session.read_table("character_generation_template_game_mode_details")
            if str(row.get("template") or row.get("character_generation_template") or "") == template_key
        ]
        if not detail_rows:
            raise RuntimeError(f"Template detail rows are missing: {template_key}")
        expected_runtime_initial = runtime_initial_ceo_key or initial_ceo_key
        wrong_initial = [
            row.get("initial_ceos")
            for row in detail_rows
            if row.get("initial_ceos") != expected_runtime_initial
        ]
        if wrong_initial:
            raise RuntimeError(
                "Template detail rows do not use the expected runtime initial "
                f"CEO {expected_runtime_initial}: {wrong_initial}"
            )

        actual_armour_value = int(armour.get("armour_value") or 0)
        if variant.get("armour") != armour_key:
            raise RuntimeError(
                f"Equipment variant points at {variant.get('armour')!r}, expected {armour_key!r}"
            )
        if actual_armour_value != armour_value:
            raise RuntimeError(
                f"Armour value is {actual_armour_value}, expected {armour_value}"
            )
        art_set = str(template.get("art_set_override") or "")
        if expected_art_set and art_set != expected_art_set:
            raise RuntimeError(f"Art set is {art_set!r}, expected {expected_art_set!r}")
        loc_rows = {
            key: value
            for loc_path in session.list_loc_files()
            for key, value in session.read_loc(loc_path).items()
        }
        title_key = f"ceo_nodes_title_{ceo_key}"
        description_key = f"ceo_nodes_description_{ceo_key}"
        if armour_title is not None and loc_rows.get(title_key) != armour_title:
            raise RuntimeError(
                f"Armour title is {loc_rows.get(title_key)!r}, expected {armour_title!r}"
            )
        if not loc_rows.get(description_key):
            raise RuntimeError(
                f"Dedicated armour description localisation is missing: {description_key}"
            )

        return {
            "ok": True,
            "pack": str(pack_path),
            "packType": index.pack_type,
            "packSize": pack_path.stat().st_size,
            "fileCount": index.files_count,
            "ccdSize": len(output_ccd),
            "baseCcdStringCountPreserved": preserved_string_count,
            "dedicatedArmour": {
                "ceoKey": ceo_key,
                "ceoOccurrences": output_strings[ceo_key],
                "initialCeoKey": initial.get("key"),
                "initialCeoOccurrences": output_strings[initial_ceo_key],
                "initialActiveCeos": initial_active_ceos,
                "armourKey": variant.get("armour"),
                "armourValue": actual_armour_value,
                "title": loc_rows.get(title_key),
                "description": loc_rows.get(description_key),
                "rarity": next(
                    (
                        value
                        for value in ceo_definition_strings
                        if value in {"common", "refined", "exceptional", "unique"}
                    ),
                    "",
                ),
                "regularSubcategory": (
                    "3k_dummy_effect_ceo_subcategory_armour_metal"
                    in ceo_effect_strings
                ),
                "spawnerKey": spawner_key,
            },
            "character": {
                "templateKey": template_key,
                "detailRows": len(detail_rows),
                "runtimeInitialCeoKey": expected_runtime_initial,
                "artSet": art_set,
            },
        }
    finally:
        session.close()


def _find_row(rows: list[dict[str, Any]], field: str, value: str) -> dict[str, Any]:
    for row in rows:
        if str(row.get(field) or "") == value:
            return row
    raise RuntimeError(f"Expected row not found: {field}={value}")


def _read_all_table_rows(session: Any, table_name: str) -> list[dict[str, Any]]:
    marker = f"db/{table_name}_tables/"
    paths = [path for path in session.list_tables() if marker in path.lower()]
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(session.read_table(path))
    if not rows:
        raise RuntimeError(f"Expected DB table not found: {table_name}")
    return rows


def _keyed_record_group_strings(
    ccd: CeoCcd,
    record_name: str,
    key: str,
) -> list[str]:
    records = ceo_ccd_module._top_level_record_map(ccd.root)
    record = records[record_name][0]
    group = next(
        (
            group
            for group in record.groups
            if ceo_ccd_module._group_key(group) == key
        ),
        None,
    )
    if group is None:
        raise RuntimeError(f"CCD record {record_name} is missing key: {key}")
    return [
        value
        for node in group
        for nested in node.walk()
        for value in nested.strings()
    ]


if __name__ == "__main__":
    raise SystemExit(main())
