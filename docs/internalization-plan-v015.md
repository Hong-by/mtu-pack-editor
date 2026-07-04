# v0.1.5 Internalization Plan

## Baseline

- Stable tag: `v0.1.5`
- Main input pack: `work/packs/my_hero.pack`
- Current writer: `tk_pack_builder/delta_builder.py`
- Current web defaults: `web/index.html`
- Current release copier: `scripts/build_windows_exe.ps1`

The v0.1.5 writer works because it opens real packs and reuses their RPFM-decoded DB schemas, row templates, loc templates, image files, event payload templates, and Lua/event structure. Internalization must preserve that output shape before removing pack references.

## Current Reference Roles

| Source | Current role | Internalization target |
| --- | --- | --- |
| `my_hero.pack` | MTU character rows, loc, image/model files, working generation structure | Material DB rows, loc bank, asset index, selected assets |
| `database.pack` | Vanilla DB schemas and dependency rows | Schema bank and vanilla row bank |
| `data_*.pack` | Small DLC DB/resource references | Only rows/assets that are actually referenced |
| `data.pack` | Resource-only pack, no DB/loc | Asset cache only, no schema target |
| `BFG_*.pack` | Character image resources | Asset cache and image mapping only |
| `AW*`, `LSHZ*` | Character image/resources | Removed from default path; later treat as optional asset packs |
| `work/legacy_template/8King_4P_1.7_up.pack` | Incident/payload/option event templates | Golden event template rows |

## Writer Dependencies

The current writer needs these material categories:

- Table schemas/type templates for every emitted DB table.
- Source rows for character templates and game-mode details.
- Art set and art rows for portrait/unitcard wiring.
- Age range rows.
- Initial CEO rows.
- Attribute set and attribute rows.
- Skill node set, skill node, links, level effects, effects, unit ability rows.
- Retinue, retinue slot, aspect, land unit, and land-unit ability rows.
- Equipment variant and weapon/armour stat rows.
- Incident, payload, and option rows for campaign-start join events.
- Loc table template and generated name/event loc rows.
- Image assets under `ui/characters/...`.
- Lua campaign spawn script shape.

## Implementation Strategy

1. Build a material extractor that opens baseline packs and writes a JSON snapshot under `work/internal_materials`.
2. Store schemas and source rows together, preserving original table paths and source pack names.
3. Store loc text and loc template metadata separately.
4. Store an asset index with source pack, packed path, and extracted file path if available.
5. Add a read-only internal material session that implements the pack-session methods used by `delta_builder.py`.
6. Keep the v0.1.5 writer intact at first; swap only its data source after golden comparison passes.
7. Compare generated packs against a v0.1.5 golden output before game testing.

## First Execution Scope

The first internalization pass does not replace runtime generation. It creates auditable material snapshots:

- `work/internal_materials/materials.v015.json`
- `work/internal_materials/internalization_report.v015.json`

After the report is stable, the next pass can add `InternalMaterialSession` and golden comparison.
