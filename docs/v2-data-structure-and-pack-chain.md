# v2 Data Structure And Pack Chain

Last updated: 2026-06-28

This document records the working v2.0.0 data model and pack generation chain. The important rule is that the app is a recipe composer over existing Three Kingdoms/MTU pack rows. It should copy or patch verified source rows, then write only the delta rows and required assets into the output patch pack.

## Runtime Sources

The default release path is pack-based.

- Input pack: `work/packs/my_hero.pack`
- Output pack: user selected patch pack, usually `output/my_hero_patch.pack`
- RPFM runtime: `work/rpfm-dist/rpfm_server.exe`
- RPFM schema store: `work/rpfm-schema-store/schema_3k.ron`
- Core image assets: `work/assets`
- Internal materials: `work/internal_materials/materials.v015.json`

Internal materials are present in the release, but the normal save path should use the input pack by default. Internal materials remain a controlled path, because table priority and row coverage must match the RPFM pack path before it can be the only default.

## Build Flow

The web UI sends a recipe to `/api/build`.

Default flow:

1. `web.py` opens the input pack with `RpfmAdapter`.
2. `recipe_from_dict()` converts UI payload to typed recipe objects.
3. `build_pack()` calls `build_delta_pack()`.
4. `build_delta_pack()` collects changed DB rows, loc rows, scripts, and image assets.
5. A new delta pack is created through RPFM.
6. DB tables, loc files, Lua scripts, and UI image files are written.
7. RPFM saves the final patch pack.

Internal-material flow:

1. `MaterialPackSession` reads rows from `materials.v015.json`.
2. A real RPFM writer session still opens the input pack so the final output can be saved as a real `.pack`.
3. `build_delta_pack_from_materials()` bridges the material reader and RPFM writer.

## Recipe Objects

Defined in `tk_pack_builder/recipe.py`.

- `CharacterPatch`: modifies an existing character template key.
- `CharacterClone`: creates a new character template from an existing source template.
- `StatPatch`: patches a numeric/string stat on a resolved source row.
- `LandUnitClone`: clones a land unit and optionally the retinue chain.
- `ArmourTypeClone`: clones an armour type row when a dedicated armour row is required.
- `SkillSetClone`: clones a skill node set and replaces selected node skills.
- `AttributeSetClone`: clones five element attribute rows and changes stat values.
- `AgeRangeClone`: clones a spawn age range row.

## Existing Character Patch Chain

Existing character modification keeps the original character template key.

Primary tables:

- `db/character_generation_templates_tables/_mtu_characters`
- `db/character_generation_template_game_mode_details_tables/_mtu_characters`
- `db/campaign_character_art_sets_tables/_mtu_characters`
- `db/campaign_character_arts_tables/_mtu_characters`
- `db/character_generation_spawn_age_ranges_tables/_mtu_characters`
- `db/ceo_initial_datas_tables/_mtu_characters_ceo`
- `db/names_tables/_mtu_characters_names`

Patch rules:

- The selected UI character key must be the real `character_generation_templates.key`.
- Template-level values are written back to the same template key.
- Historical and romance details are patched independently through `character_generation_template_game_mode_details`.
- Display name changes create or update `names` rows and loc rows.
- Image/model changes patch the rows connected to the existing `art_set_override`.
- Existing character image replacement retargets image files into the folder that the existing art row already references.

The patch path must not create a second character template for a normal existing-character edit.

## New Character Clone Chain

New character generation creates a new template key from a source template.

Required source chain:

```text
character_generation_templates.key
  -> art_set_override
  -> campaign_character_art_sets.art_set_id
  -> campaign_character_arts.art_set_id

character_generation_templates.key
  -> character_generation_template_game_mode_details.character_generation_template
  -> historical/romance detail rows

character_generation_templates.spawn_age_range
  -> character_generation_spawn_age_ranges.key

detail.initial_ceos
  -> ceo_initial_datas.key
```

Output chain:

```text
new character_generation_templates.key
  -> new or selected art_set_override
  -> copied campaign_character_art_sets row
  -> copied campaign_character_arts rows with updated portrait/card/uniform

new character_generation_templates.key
  -> copied historical detail row
  -> copied romance detail row
```

Rules:

- New template key must be unique.
- Historical and romance rows must both be written when the source has both.
- If a new art set is created, art set rows and art rows must be copied together.
- Gender is derived from the selected/source art set when available and written to the new template.
- Spawn event is controlled by the UI setting. Do not auto-force campaign-start spawn when the user selected another mode.

## Image And Art Set Chain

Images are UI files under:

```text
ui/characters/<image-folder>/
  composites/
    large_panel/
    small_panel/
  stills/
    halfbody_large/
    halfbody_small/
    unitcards/
```

Important fields:

- `campaign_character_arts.portrait`
- `campaign_character_arts.card`
- `campaign_character_arts.uniform`
- `campaign_character_arts.art_set_id`

Current behavior:

- Existing character edit: keep the existing art set identity, patch art row values, and copy selected image files into the referenced target folder.
- New character clone: create/copy the art set chain and point the new template to that art set.
- The file path must not accidentally create duplicated nested character folders, such as `ui/characters/a/a/...`.

The `id` in `campaign_character_arts` is part of the art row key space. When cloning art rows, new ids are generated from the new art set plus the original row shape.

## Equipment And Unit Stat Chain

The combat tab does not create arbitrary equipment. It uses existing rows as materials and patches only supported values.

Supported stat patch columns are defined in `tk_pack_builder/stat_tables.py`.

Armour:

- Equipment CEO is resolved through `ceos_to_equipment_variants_tables`.
- Armour row is resolved through `unit_armour_types`.
- Supported armour edits:
  - `armour_value`
  - `audio_type`

Land unit:

- Source land unit is resolved through `land_units`.
- The source row is cloned to a new key when the character needs a dedicated retinue profile.
- Supported land unit edits:
  - `charge_bonus`
  - `morale`
  - `primary_ammo`

Retinue chain:

```text
character_generation_template_game_mode_details.retinue
  -> retinues.key
  -> retinue_slot_initial_units.retinue
  -> main_units.land_unit
  -> land_units.key
```

When a land unit is cloned for a character, the detail row must point to the new retinue/land unit chain consistently. If only `land_units` is cloned but `retinues` or `retinue_slot_initial_units` still point to the old chain, the game may ignore the new stats.

## Attribute And Skill Chains

Attribute sets:

```text
character_generation_template_game_mode_details.attribute_set
  -> character_attribute_sets
  -> character_attributes
```

The five element stats are represented by rows in `character_attributes`. A new or patched attribute set must copy the set row and the corresponding attribute rows.

Skill sets:

```text
character_generation_template_game_mode_details.skill_set_override
  -> character_skill_node_sets
  -> character_skill_nodes
  -> character_skill_node_links
  -> character_skill_level_to_effects_junctions
  -> effects
```

Skill tree edits clone the skill set and replace selected node skills. Dependencies must be copied so that the game can resolve the skill rows and effects.

## Names And Loc Chain

Name changes require both DB and loc rows.

DB table priority for RPFM pack sessions:

1. `db/names_tables/_mtu_characters_names`
2. `db/names_tables/data__`
3. `db/names_tables/data`

The priority is necessary because an input pack can contain all three. A short table name like `names` is ambiguous without this rule.

Loc output:

- Character names are written to `text/hby_mtu_pack_editor_names.loc`.
- Event names/descriptions are written to `text/db/hby_mtu_pack_editor_event.loc`.

The loc writer uses an existing loc file as a schema template. If the first loc file is empty, it now scans for a non-empty loc template. If all loc templates are empty, it creates default key/text/tooltip cells from field names.

## Spawn Event Chain

Spawn event output has two parts:

- Lua script: `script/campaign/mod/hby_mtu_pack_editor_player_spawn.lua`
- Incident DB/loc rows:
  - `db/incidents_tables/event`
  - `db/cdir_events_incident_payloads_tables/event`
  - `db/cdir_events_incident_option_junctions_tables/event`
  - `text/db/hby_mtu_pack_editor_event.loc`

The script controls actual joining. Incident rows control the visible message.

## Table Alias Policy

There are two table-resolution paths.

RPFM pack session:

- `tk_pack_builder/adapters.py`
- `RPFM_TABLE_ALIASES`
- Must resolve ambiguous real pack paths consistently.

Internal material session:

- `tk_pack_builder/internal_materials.py`
- `MATERIAL_TABLE_ALIASES`
- Must mirror the RPFM priority where possible.

Character tables:

- `tk_pack_builder/character_clone.py`
- `CHARACTER_TABLE_ALIASES`

Stat tables:

- `tk_pack_builder/stat_tables.py`
- `TABLE_ALIASES`

When adding a new table dependency, update both the RPFM path and material path rules. Otherwise dev/material tests may pass while the release/RPFM path fails.

## Release Packaging Rules

The Windows release zip must include:

- `MTU Pack Editor.exe`
- `web/`
- `work/rpfm-dist/rpfm_server.exe`
- `work/rpfm-schema-store/schema_3k.ron`
- `work/packs/my_hero.pack`
- `work/assets`
- `work/internal_materials/materials.v015.json`
- `work/internal_materials/asset_manifest.v015.json`

The release zip must not include runtime artifacts:

- `work/pack_cache.sqlite3`
- `work/api-build-error.log`
- RPFM/server log files
- generated output packs from local testing

## Diagnostics

Generated output diagnostics are written next to the output pack:

```text
output/my_hero_patch.diagnostics.json
```

The UI should only report whether pack generation succeeded or failed. Detailed validation/debugging should use the diagnostics JSON and logs.

## Common Failure Patterns

`RPFM table name is ambiguous: names`

- Cause: RPFM saw multiple `names_tables` paths.
- Fix: ensure `RPFM_TABLE_ALIASES["names"]` priority is applied.

`list index out of range` in `_loc_db_with_rows`

- Cause: source loc template had zero rows.
- Fix: scan for a non-empty loc template or use default field-based loc cells.

Character appears twice

- Cause: existing-character edit accidentally created a new template.
- Fix: existing edits must patch the same `character_generation_templates.key`.

Image file exists in pack but does not show in game

- Cause: art row `portrait/card` folder does not match the copied image target, or art set chain is not connected to the template.
- Fix: inspect `character_generation_templates.art_set_override`, `campaign_character_art_sets.art_set_id`, `campaign_character_arts.art_set_id`, and `ui/characters/...` together.

Battle stats do not change

- Cause: `land_units` was patched but the retinue/main-unit chain still points to old rows.
- Fix: inspect `detail.retinue -> retinues -> retinue_slot_initial_units -> main_units -> land_units`.
