from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tk_pack_builder.ceo_ccd import CeoCcd


DEFAULT_ASSEMBLY_KIT = Path(
    r"E:\SteamLibrary\steamapps\common\Total War THREE KINGDOMS\assembly_kit"
)
DEFAULT_OUTPUT_DIR = ROOT / "work" / "dedicated_armour_bob_pool"
DEFAULT_BASE_CCD = (
    ROOT / "work" / "dedicated_armour_poc" / "vanilla_base.ceo_data.ccd"
)
POC_KEYS = {
    "armourCeoKey": "hby_poc_ancillary_armour_mulu_dedicated_001",
    "initialCeoKey": "hby_poc_ceo_initial_data_character_mulu_dedicated_001",
    "armourTypeKey": "hby_poc_armour_mulu_dedicated_001",
    "equipmentStageKey": "hby_poc_initial_data_stage_mulu_dedicated_001",
}
NEUTRAL_INITIAL_STAGES = {
    POC_KEYS["equipmentStageKey"],
    "3k_main_initial_data_character_ancillaries_global",
    "3k_main_ceo_initial_data_stage_character_traits_shared_global_permissions",
    "3k_main_ceo_initial_data_stage_character_protagonist",
    "3k_main_ceo_initial_data_stage_character_wealth_medium",
    "3k_main_ceo_initial_data_stage_character_potential_legendary",
    "3k_dlc04_ceo_initial_data_character_give_political_support_random",
}
GENERIC_ARMOUR_GROUP = "3k_main_ceo_group_ancillary_armour_character_all"
UNIQUE_ARMOUR_SUBCATEGORY_EFFECT = "3k_dummy_effect_ceo_subcategory_armour_unique"
GENERIC_ARMOUR_ICON = (
    "armours/3k_main_ancillary_armour_medium_armour_earth_and_metal_refined.png"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile a fixed dedicated-armour CEO slot pool with the official "
            "Assembly Kit BOB campaign processor. All touched Assembly Kit "
            "files are restored byte-for-byte before the command exits."
        )
    )
    parser.add_argument("--assembly-kit", type=Path, default=DEFAULT_ASSEMBLY_KIT)
    parser.add_argument("--base-ccd", type=Path, default=DEFAULT_BASE_CCD)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--slot-count", type=int, default=32)
    parser.add_argument("--armour-value", type=int, default=45)
    args = parser.parse_args()
    if not 1 <= args.slot_count <= 128:
        raise ValueError("slot-count must be between 1 and 128.")
    if not 0 <= args.armour_value <= 500:
        raise ValueError("armour-value must be between 0 and 500.")

    assembly_kit = args.assembly_kit.expanduser().resolve()
    raw_db = assembly_kit / "raw_data" / "db"
    working_ccd = assembly_kit / "working_data" / "campaigns" / "ceo_data.ccd"
    bob_dir = assembly_kit / "binaries"
    bob_exe = bob_dir / "bob.modder.x64.exe"
    bob_config = bob_dir / "BOB" / "default_configuration.xml"
    base_ccd_path = args.base_ccd.expanduser().resolve()
    required = [raw_db, working_ccd, bob_exe, base_ccd_path]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Dedicated-armour BOB input is missing:\n"
            + "\n".join(str(path) for path in missing)
        )

    xml_paths = sorted(raw_db.glob("ceo*.xml"))
    armour_xml = raw_db / "unit_armour_types.xml"
    if armour_xml.is_file():
        xml_paths.append(armour_xml)
    source_rows = _find_poc_rows(xml_paths)
    if not source_rows:
        raise RuntimeError(
            "The verified one-slot hby_poc rows are missing from Assembly Kit XML."
        )

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    augmented_path = output_dir / f"vanilla-dedicated-armour-{args.slot_count:03d}.ccd"
    manifest_path = output_dir / f"dedicated-armour-slots-{args.slot_count:03d}.json"
    base = CeoCcd.from_path(base_ccd_path)

    with _restored_files([*source_rows, working_ccd, bob_config]):
        for xml_path in source_rows:
            _replace_poc_with_slots(
                xml_path,
                slot_count=args.slot_count,
                armour_value=args.armour_value,
            )
        bob_config.parent.mkdir(parents=True, exist_ok=True)
        bob_config.write_text(_bob_configuration(), encoding="utf-8")
        completed = subprocess.run(
            [str(bob_exe)],
            cwd=bob_dir,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=300,
            check=False,
        )
        log_text = completed.stdout.decode("utf-8", errors="replace")
        (output_dir / "bob.log").write_text(log_text, encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(
                f"BOB failed with exit code {completed.returncode}:\n{log_text[-4000:]}"
            )
        augmented_bytes = working_ccd.read_bytes()
        augmented = CeoCcd.from_bytes(augmented_bytes)
        _verify_compiled_slots(augmented, args.slot_count)
        _verify_neutral_delta(base, augmented)
        probe = base.clone()
        stats = probe.apply_additive_delta(base=base, augmented=augmented)
        if CeoCcd.from_bytes(probe.to_bytes()).root != probe.root:
            raise RuntimeError("BOB additive delta failed semantic reopen verification.")
        augmented_path.write_bytes(augmented_bytes)

    manifest = {
        "schemaVersion": 2,
        "poolId": f"dedicated-armour-slots-{args.slot_count:03d}",
        "label": f"Precompiled dedicated armour slots ({args.slot_count})",
        "mode": "precompiled-template",
        "assemblyKitBaseCcdSha256": hashlib.sha256(base_ccd_path.read_bytes()).hexdigest(),
        "assemblyKitAugmentedCcdSha256": hashlib.sha256(
            augmented_path.read_bytes()
        ).hexdigest(),
        "augmentedCcdFile": augmented_path.name,
        "mergeStats": {
            "groupsAdded": stats.groups_added,
            "stringValuesAdded": stats.string_values_added,
            "arrayItemsAdded": stats.array_items_added,
        },
        "slots": [_slot_manifest(index) for index in range(1, args.slot_count + 1)],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": True,
                "augmentedCcd": str(augmented_path),
                "manifest": str(manifest_path),
                "slotCount": args.slot_count,
                "mergeStats": manifest["mergeStats"],
                "assemblyKitRestored": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _find_poc_rows(xml_paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for path in xml_paths:
        root = ET.parse(path).getroot()
        if any(
            POC_KEYS["armourCeoKey"] in ET.tostring(row, encoding="unicode")
            or POC_KEYS["initialCeoKey"] in ET.tostring(row, encoding="unicode")
            or POC_KEYS["equipmentStageKey"] in ET.tostring(row, encoding="unicode")
            or POC_KEYS["armourTypeKey"] in ET.tostring(row, encoding="unicode")
            for row in root
        ):
            found.append(path)
    return found


def _replace_poc_with_slots(
    path: Path,
    *,
    slot_count: int,
    armour_value: int,
) -> None:
    tree = ET.parse(path)
    root = tree.getroot()
    all_source_rows = [
        copy.deepcopy(row)
        for row in root
        if _contains_poc_key(row)
    ]
    if not all_source_rows:
        return
    for row in list(root):
        if _contains_poc_key(row):
            root.remove(row)
    source_rows = [
        row
        for row in all_source_rows
        if _keep_neutral_production_row(path.name, row)
    ]

    timestamp = str(int(time.time() * 1000))
    for slot_index in range(1, slot_count + 1):
        replacements = {
            POC_KEYS["armourCeoKey"]: _slot_keys(slot_index)["armourCeoKey"],
            POC_KEYS["initialCeoKey"]: _slot_keys(slot_index)["initialCeoKey"],
            POC_KEYS["armourTypeKey"]: _slot_keys(slot_index)["armourTypeKey"],
            POC_KEYS["equipmentStageKey"]: _slot_keys(slot_index)[
                "equipmentStageKey"
            ],
        }
        for row_index, source in enumerate(source_rows):
            row = copy.deepcopy(source)
            _replace_element_strings(row, replacements)
            row.set("record_uuid", "{" + str(uuid.uuid4()) + "}")
            row.set("record_timestamp", timestamp)
            auto_id = row.find("auto_id")
            if auto_id is not None:
                value = str(
                    _stable_positive_int(
                        f"{path.stem}:{slot_index}:{row_index}:{ET.tostring(row, encoding='unicode')}"
                    )
                )
                auto_id.text = value
                row.set("record_key", value)
            if path.name == "unit_armour_types.xml":
                armour = row.find("armour_value")
                if armour is not None:
                    armour.text = str(armour_value)
            if path.name == "ceo_nodes.xml":
                title = row.find("title")
                description = row.find("description")
                icon_path = row.find("icon_path")
                if title is not None:
                    title.text = "전용 갑옷"
                if description is not None:
                    description.text = "신규 장수를 위해 제작된 전용 갑옷입니다."
                if icon_path is not None:
                    icon_path.text = GENERIC_ARMOUR_ICON
            root.append(row)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _keep_neutral_production_row(path_name: str, row: ET.Element) -> bool:
    if path_name == "ceo_effect_list_to_effects.xml":
        return _element_text(row, "effect") == UNIQUE_ARMOUR_SUBCATEGORY_EFFECT
    if path_name == "ceo_group_ceos.xml":
        return _element_text(row, "ceo_group") == GENERIC_ARMOUR_GROUP
    if path_name == "ceo_initial_data_active_ceos.xml":
        return _element_text(row, "active_ceo") == POC_KEYS["armourCeoKey"]
    if path_name == "ceo_initial_data_equipments.xml":
        return _element_text(row, "equipped_ceo") == POC_KEYS["armourCeoKey"]
    if path_name == "ceo_initial_data_scripted_permissions.xml":
        return False
    if path_name == "ceo_initial_data_to_stages.xml":
        return _element_text(row, "initial_data_stage") in NEUTRAL_INITIAL_STAGES
    return True


def _element_text(row: ET.Element, name: str) -> str:
    element = row.find(name)
    return str(element.text or "") if element is not None else ""


def _contains_poc_key(element: ET.Element) -> bool:
    serialized = ET.tostring(element, encoding="unicode")
    return any(value in serialized for value in POC_KEYS.values())


def _replace_element_strings(
    element: ET.Element,
    replacements: dict[str, str],
) -> None:
    for key, value in list(element.attrib.items()):
        element.set(key, _replace_text(value, replacements))
    if element.text:
        element.text = _replace_text(element.text, replacements)
    for child in element:
        _replace_element_strings(child, replacements)


def _replace_text(value: str, replacements: dict[str, str]) -> str:
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value


def _slot_keys(index: int) -> dict[str, str]:
    suffix = f"{index:03d}"
    return {
        "armourCeoKey": f"hby_mtu_ancillary_armour_dedicated_{suffix}",
        "initialCeoKey": f"hby_mtu_ceo_initial_data_character_dedicated_{suffix}",
        "armourTypeKey": f"hby_mtu_armour_dedicated_{suffix}",
        "equipmentStageKey": f"hby_mtu_initial_data_stage_dedicated_{suffix}",
    }


def _slot_manifest(index: int) -> dict[str, str]:
    keys = _slot_keys(index)
    return {
        "slotId": f"slot-{index:03d}",
        "sourceCeoKey": "*",
        "sourceInitialCeoKey": "*",
        "sourceArmourTypeKey": "*",
        "armourCeoKey": keys["armourCeoKey"],
        "initialCeoKey": keys["initialCeoKey"],
        "armourTypeKey": keys["armourTypeKey"],
    }


def _verify_compiled_slots(ccd: CeoCcd, slot_count: int) -> None:
    strings = list(ccd.all_strings())
    for index in range(1, slot_count + 1):
        keys = _slot_keys(index)
        for key_name in ("armourCeoKey", "initialCeoKey"):
            if keys[key_name] not in strings:
                raise RuntimeError(
                    f"BOB output is missing {key_name}: {keys[key_name]}"
                )
    for value in POC_KEYS.values():
        if value in strings:
            raise RuntimeError(f"BOB output still contains experimental POC key: {value}")


def _verify_neutral_delta(base: CeoCcd, augmented: CeoCcd) -> None:
    before = Counter(base.all_strings())
    after = Counter(augmented.all_strings())
    forbidden_fragments = (
        "mulu",
        "elephant",
        "attribute_cunning",
        "campaign_movement",
    )
    leaked = {
        value: after[value] - before[value]
        for value in after
        if after[value] > before[value]
        and any(fragment in value.lower() for fragment in forbidden_fragments)
    }
    if leaked:
        sample = ", ".join(
            f"{value} (+{count})"
            for value, count in sorted(leaked.items())[:10]
        )
        raise RuntimeError(
            "Neutral dedicated-armour pool leaked source-character data: "
            + sample
        )


def _stable_positive_int(seed: str) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF or 1


@contextmanager
def _restored_files(paths: list[Path]):
    snapshots = {
        path: path.read_bytes() if path.is_file() else None
        for path in paths
    }
    try:
        yield
    finally:
        for path, data in snapshots.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        mismatches = [
            str(path)
            for path, data in snapshots.items()
            if data is not None and path.read_bytes() != data
        ]
        if mismatches:
            raise RuntimeError(
                "Assembly Kit restoration verification failed:\n"
                + "\n".join(mismatches)
            )


def _bob_configuration() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<bob_configuration>
  <processors><processor>Campaign</processor></processors>
  <directories/>
  <global_rules/>
  <retail>0</retail>
  <silent>1</silent>
  <show_errors>1</show_errors>
  <get_latest>0</get_latest>
  <connect_db>0</connect_db>
  <merge_for_checkin_mode>2</merge_for_checkin_mode>
  <selected_files>
    <entry>&lt;working&gt;/campaigns/ceo_data.ccd</entry>
  </selected_files>
</bob_configuration>
"""


if __name__ == "__main__":
    raise SystemExit(main())
