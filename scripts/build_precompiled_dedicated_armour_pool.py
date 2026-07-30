from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tk_pack_builder.ceo_ccd import CeoCcd
from tk_pack_builder.dedicated_armour_pool import (
    CCD_PACK_PATH,
    load_dedicated_armour_pools,
    verify_pool_asset,
)
from tk_pack_builder.pfh import find_entry, read_entry_bytes, read_pfh_index


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply the exact additive delta emitted by Assembly Kit/BOB to a "
            "known target CEO CCD and export a fingerprint-gated pool asset."
        )
    )
    parser.add_argument("--base-ccd", type=Path, required=True)
    parser.add_argument("--augmented-ccd", type=Path, required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--target-pack", type=Path)
    target.add_argument("--target-ccd", type=Path)
    parser.add_argument("--template-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pool-id", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument(
        "--fixed-source",
        action="store_true",
        help=(
            "Keep source CEO/initial/armour-type keys from the template. "
            "The default exports wildcard source fields so one compiled slot "
            "can reuse the selected source armour's DB model and stats."
        ),
    )
    args = parser.parse_args()

    base_bytes = args.base_ccd.read_bytes()
    augmented_bytes = args.augmented_ccd.read_bytes()
    target_bytes, target_description = _read_target(args.target_pack, args.target_ccd)
    template = json.loads(args.template_manifest.read_text(encoding="utf-8"))

    base = CeoCcd.from_bytes(base_bytes)
    augmented = CeoCcd.from_bytes(augmented_bytes)
    target_ccd = CeoCcd.from_bytes(target_bytes)
    before = Counter(target_ccd.all_strings())
    stats = target_ccd.apply_additive_delta(base=base, augmented=augmented)
    after = Counter(target_ccd.all_strings())

    lost = {
        value: count - after[value]
        for value, count in before.items()
        if after[value] < count
    }
    if lost:
        sample = ", ".join(f"{key} ({count})" for key, count in list(lost.items())[:5])
        raise RuntimeError(f"Target CEO strings were removed during merge: {sample}")

    slots = _pool_slots(template, fixed_source=args.fixed_source)
    _verify_slot_keys(augmented, target_ccd, slots)

    compiled_bytes = target_ccd.to_bytes()
    reopened = CeoCcd.from_bytes(compiled_bytes)
    if reopened.root != target_ccd.root:
        raise RuntimeError("Compiled CEO CCD failed semantic reopen verification.")
    if Counter(reopened.all_strings()) != after:
        raise RuntimeError("Compiled CEO CCD changed string references while reopening.")

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    ccd_name = f"{args.pool_id}.ccd"
    ccd_path = output_dir / ccd_name
    manifest_path = output_dir / f"{args.pool_id}.json"
    ccd_path.write_bytes(compiled_bytes)

    manifest: dict[str, Any] = {
        "schemaVersion": 2,
        "poolId": args.pool_id,
        "label": args.label,
        "mode": "precompiled",
        "baseCcdSha256": hashlib.sha256(target_bytes).hexdigest(),
        "compiledCcdSha256": hashlib.sha256(compiled_bytes).hexdigest(),
        "ccdFile": ccd_name,
        "target": target_description,
        "assemblyKitDelta": {
            "baseCcdSha256": hashlib.sha256(base_bytes).hexdigest(),
            "augmentedCcdSha256": hashlib.sha256(augmented_bytes).hexdigest(),
            "groupsAdded": stats.groups_added,
            "stringValuesAdded": stats.string_values_added,
            "arrayItemsAdded": stats.array_items_added,
        },
        "slots": slots,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    pool = next(
        pool
        for pool in load_dedicated_armour_pools([output_dir])
        if pool.pool_id == args.pool_id
    )
    verify_pool_asset(pool)
    print(
        json.dumps(
            {
                "ok": True,
                "manifest": str(manifest_path),
                "ccd": str(ccd_path),
                "target": target_description,
                "targetCcdSha256": manifest["baseCcdSha256"],
                "compiledCcdSha256": manifest["compiledCcdSha256"],
                "compiledSize": len(compiled_bytes),
                "slotCount": len(slots),
                "mergeStats": manifest["assemblyKitDelta"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _read_target(
    target_pack: Path | None,
    target_ccd: Path | None,
) -> tuple[bytes, dict[str, str]]:
    if target_pack is not None:
        pack_path = target_pack.expanduser().resolve()
        index = read_pfh_index(pack_path)
        data = read_entry_bytes(pack_path, find_entry(index, CCD_PACK_PATH))
        return data, {
            "kind": "pack",
            "name": pack_path.name,
            "packedPath": CCD_PACK_PATH,
        }
    assert target_ccd is not None
    ccd_path = target_ccd.expanduser().resolve()
    return ccd_path.read_bytes(), {
        "kind": "ccd",
        "name": ccd_path.name,
        "packedPath": CCD_PACK_PATH,
    }


def _pool_slots(template: dict[str, Any], *, fixed_source: bool) -> list[dict[str, str]]:
    raw_slots = template.get("slots")
    if not isinstance(raw_slots, list) or not raw_slots:
        raise ValueError("Template manifest has no dedicated-armour slots.")
    slots: list[dict[str, str]] = []
    required = (
        "slotId",
        "sourceCeoKey",
        "sourceInitialCeoKey",
        "sourceArmourTypeKey",
        "armourCeoKey",
        "initialCeoKey",
        "armourTypeKey",
    )
    for raw_slot in raw_slots:
        if not isinstance(raw_slot, dict):
            raise ValueError("Template manifest contains a malformed slot.")
        slot = {key: str(raw_slot.get(key) or "").strip() for key in required}
        missing = [key for key, value in slot.items() if not value]
        if missing:
            raise ValueError(
                "Template manifest slot is missing fields: " + ", ".join(missing)
            )
        if not fixed_source:
            slot["sourceCeoKey"] = "*"
            slot["sourceInitialCeoKey"] = "*"
            slot["sourceArmourTypeKey"] = "*"
        slots.append(slot)
    return slots


def _verify_slot_keys(
    augmented: CeoCcd,
    compiled: CeoCcd,
    slots: list[dict[str, str]],
) -> None:
    augmented_strings = Counter(augmented.all_strings())
    compiled_strings = Counter(compiled.all_strings())
    for slot in slots:
        for field in ("armourCeoKey", "initialCeoKey"):
            value = slot[field]
            expected = augmented_strings[value]
            if expected <= 0:
                raise RuntimeError(
                    f"BOB augmented CCD does not contain slot {field}: {value}"
                )
            if compiled_strings[value] < expected:
                raise RuntimeError(
                    f"Compiled target CCD is missing slot {field}: "
                    f"{value} ({compiled_strings[value]}/{expected})"
                )


if __name__ == "__main__":
    raise SystemExit(main())
