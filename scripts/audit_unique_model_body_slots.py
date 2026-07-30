from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.internal_materials import MaterialPackSession  # noqa: E402
from tk_pack_builder.pfh import read_entry_bytes, read_pfh_index  # noqa: E402


MTU_TEMPLATES = "db/character_generation_templates_tables/_mtu_characters"
MTU_ARTS = "db/campaign_character_arts_tables/_mtu_characters"
MTU_UNIFORMS = "db/agent_uniforms_tables/_mtu_characters"
MTU_VARIANTS = "db/variants_tables/_mtu_characters_variants"
VMD_ROOT = "variantmeshes/variantmeshdefinitions/"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit MTU character uniforms whose body injection slot can be frozen."
    )
    parser.add_argument(
        "--materials",
        type=Path,
        default=ROOT / "work" / "internal_materials" / "materials.v015.json",
    )
    parser.add_argument(
        "--pack",
        type=Path,
        default=ROOT / "work" / "packs" / "my_hero.pack",
    )
    parser.add_argument(
        "--eligible-only",
        action="store_true",
        help="Print only rows whose baked geometry can render without set_body injection.",
    )
    args = parser.parse_args()

    session = MaterialPackSession.open(args.materials.resolve())
    templates = session.read_table(MTU_TEMPLATES)
    arts = session.read_table(MTU_ARTS)
    uniforms = session.read_table(MTU_UNIFORMS)
    variants = session.read_table(MTU_VARIANTS)

    art_uniforms: dict[str, set[str]] = {}
    for row in arts:
        art_set_id = str(row.get("art_set_id") or "")
        uniform = str(row.get("uniform") or "")
        if art_set_id and uniform:
            art_uniforms.setdefault(art_set_id, set()).add(uniform)
    uniform_rows = {str(row.get("uniform_name") or ""): row for row in uniforms}
    variant_rows = {str(row.get("variant_name") or ""): row for row in variants}

    pack_path = args.pack.resolve()
    pack_index = read_pfh_index(pack_path)
    vmd_entries = {
        _definition_key(entry.path): entry
        for entry in pack_index.entries
        if entry.path.lower().startswith(VMD_ROOT)
        and entry.path.lower().endswith(".variantmeshdefinition")
    }

    rows: list[dict[str, Any]] = []
    for template in templates:
        template_key = str(template.get("key") or "")
        art_set_id = str(template.get("art_set_override") or "")
        for uniform_name in sorted(art_uniforms.get(art_set_id, ())):
            uniform = uniform_rows.get(uniform_name, {})
            variant_name = str(uniform.get("filename") or "")
            variant = variant_rows.get(variant_name, {})
            definition = str(variant.get("variant_filename") or "")
            definition_key = _definition_key(definition)
            entry = vmd_entries.get(definition_key)
            text = ""
            if entry is not None:
                text = read_entry_bytes(pack_path, entry).decode("utf-8", errors="replace")
            set_body_slots = len(re.findall(r'<SLOT\s+name=["\']set_body["\']', text, re.I))
            explicit_body_models = len(re.findall(
                r'<SLOT\s+name=["\']body["\'][^>]*>\s*<VARIANT_MESH\s+model=',
                text,
                re.I,
            ))
            model_count = len(re.findall(
                r"<VARIANT_MESH\b[^>]*\bmodel\s*=",
                text,
                re.I,
            ))
            has_head = bool(re.search(
                r'<SLOT\s+name=["\']head["\'][^>]*>\s*<VARIANT_MESH\b[^>]*\bmodel\s*=',
                text,
                re.I,
            ))
            has_torso = bool(re.search(
                r'<SLOT\s+name=["\'](?:chest_armour|tunic_top|tunic_bottom|collar)["\'][^>]*>'
                r'\s*<VARIANT_MESH\b[^>]*\bmodel\s*=',
                text,
                re.I,
            ))
            already_independent = set_body_slots == 0 and model_count > 0
            removable_injection = (
                set_body_slots == 1
                and (
                    explicit_body_models > 0
                    or (has_head and has_torso)
                )
            )
            eligible = bool(
                entry is not None
                and (already_independent or removable_injection)
            )
            rows.append({
                "template": template_key,
                "isMale": bool(template.get("is_male")),
                "subtype": str(template.get("subtype") or ""),
                "artSet": art_set_id,
                "uniform": uniform_name,
                "variant": variant_name,
                "definition": definition_key,
                "vmdFound": entry is not None,
                "setBodySlots": set_body_slots,
                "explicitBodyModels": explicit_body_models,
                "modelCount": model_count,
                "freezeMode": (
                    "already-independent"
                    if already_independent
                    else "remove-set-body"
                    if removable_injection
                    else ""
                ),
                "eligible": eligible,
            })

    output_rows = [row for row in rows if row["eligible"]] if args.eligible_only else rows
    print(json.dumps({
        "eligibleCount": sum(1 for row in rows if row["eligible"]),
        "maleEligibleCount": sum(1 for row in rows if row["eligible"] and row["isMale"]),
        "femaleEligibleCount": sum(1 for row in rows if row["eligible"] and not row["isMale"]),
        "rows": output_rows,
    }, ensure_ascii=False, indent=2))


def _definition_key(value: Any) -> str:
    path = str(value or "").replace("\\", "/").lower()
    name = path.rsplit("/", 1)[-1]
    suffix = ".variantmeshdefinition"
    return name[:-len(suffix)] if name.endswith(suffix) else name


if __name__ == "__main__":
    main()
