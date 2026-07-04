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
- Historical/romance details (`historical` = 정사, `romance` = 연희) are patched independently through `character_generation_template_game_mode_details`.
- Display name changes create or update `names` rows and loc rows.
- Image/model changes patch the art rows connected to the current `art_set_override` by default.
- A dedicated patch art set is created only when the recipe explicitly supplies a new `art_set_override`.
- Existing character image replacement copies files into a dedicated `ui/characters/hby_patch_.../` folder. It must not overwrite the original image folder.
- Non-appearance edits such as name, spawn, attributes, retinue, or skills must not create a dedicated patch art set by themselves.

The patch path must not create a second character template for a normal existing-character edit. Korea addon aliases such as `3k_mod_template_historical_...` and `ironic_template_historical_...` may both be patched when they are two template rows for the same addon character.

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
  -> historical/romance detail rows (`historical` = 정사, `romance` = 연희)

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

new detail.initial_ceos
  -> existing source/gender-compatible ceo_initial_datas.key
  -> copied ceo_initial_datas key row when the key is owned by a referenced pack
```

Rules:

- New template key must be unique.
  Reason: the game and scripts identify generated characters by template key. Reusing a key merges two characters into one identity.
- New characters must write both historical and romance detail rows. If the source template only has one of those rows, clone the available row as the fallback for the missing mode, then apply the UI's per-mode overrides.
  Reason: each game mode reads its own detail row. A one-mode generated character can look correct in the editor but fail or fall back when the campaign uses the other mode.
- Existing-character edits must also leave both historical and romance detail rows present. If an edited source template only has one detail row, duplicate that row for the missing mode and apply the fallback source mode's override when there is no explicit override for the missing mode.
  Reason: existing edits can target addon or DLC templates that only expose one mode row in the source pack. If the patch writes only the existing row, the other campaign mode keeps stale title, retinue, skill, or unit data.
- If a new art set is created, art set rows and art rows must be copied together.
  Reason: `character_generation_templates.art_set_override` points to an art set, and the art set needs matching `campaign_character_arts` rows for portraits/cards to resolve.
- New rows created for a new character are patch-owned rows. Newly created template/detail/art set/art rows should be written to `_mtu_characters` output tables instead of following the source table resolver into `data__`, Korea addon tables, or reference tables.
  Reason: source table paths describe where the cloned material was found. New clone rows are owned by the generated patch, so writing them into source/addon table names can hide them from the expected patch chain or collide with upstream rows.
- `ceo_initial_datas` is key-only, so a new initial CEO key is valid only when its related `ceo_initial_data_to_stages`, `ceo_initial_data_stages`, `ceo_initial_data_active_ceos`, and `ceo_initial_data_equipments` rows are cloned together.
  Reason: the key row alone is an empty reference. The stage, inventory, and equipped-slot rows are the DB-visible payload that makes the initial CEO usable by the game.
- New characters reuse the base/source character's `initial_ceos` key per game mode by default. Historical/lady initial CEO keys are preserved even for player-spawned generated characters. If the user explicitly changes the title source, that changed title source may provide an `initial_ceos` override. If the final source detail row is generic but the base template is a named character, derive the named key from the base template and copy that `ceo_initial_datas` row into the output.
  Reason: generated characters start as base-character clones, then selected UI surfaces are swapped in. Default values must preserve the chosen base chain, while explicit changes must be represented in the generated detail rows.
- New characters also clone `frontend_character_ceos_tables` rows from the base/source template to the new template.
  Reason: Three Kingdoms uses the frontend character CEO link as part of the character/title/trait presentation chain. If the new template has only a name row but no copied CEO frontend links, the game can still look like it fell back to a generic character chain.
- Visible title/career selection is also written as a separate CEO grant. UI title `ceo_node_career_*_01`/loc keys must be converted to the grantable `ceo_career_*` CEO key, then applied by the generated campaign script after the character exists.
  Reason: for many characters the detail `initial_ceos` row is generic even though the displayed title/effect comes from a career CEO. Relying only on `initial_ceos` produces generic in-game titles and makes the generated character differ from the queued UI choice.
- Do not synthesize new `ceos_tables`, `ceo_nodes_tables`, `character_generation_template_ceos_tables`, or schema-only `ceo_initial_data_*` stage/equipment rows in this project. `ceo_initial_data_*` rows are supported only by cloning an existing initial data chain and replacing selected equipment slots.
  Reason: title/trait CEO definitions still come from existing game/mod CEO data. Equipment starts safely only when the existing initial-data stage shape is preserved. Invented category/target/slot values are not reliable game data.
- CEO set recipe fields must contain string CEO keys only. Catalog display objects such as `{ key, label }` must be normalized before they enter `traitCeoKeys`, `equipmentCeoKeys`, `titleCeoKey`, or the removable lists.
  Reason: object values can stringify to `[object Object]` in the web layer. That invalid key silently reaches Lua and prevents traits, equipment, or titles from being applied.
- New characters take their detail `retinue` from the selected combat/equipment profile per game mode. Do not silently fall back to the base template's unique retinue when the user chose a different combat profile.
  Reason: retinue links into the land-unit chain. Falling back silently makes unit/stat changes appear saved in the UI while the game still uses the old unit data.
- Gender is derived from the selected/source art set when available and written to the new template.
  Reason: the template and art set must agree for voice/model/animation chains. This is DB compatibility, not a judgement based on the selected image files.
- `character_generation_templates.voiceover_actor` is preserved from the base/source template unless the recipe explicitly overrides it.
  Reason: some gender/element generic voice groups are not valid spawn templates in Three Kingdoms. Replacing a named base character's valid voice with a synthesized generic voice can make `CHARACTER_TEMPLATE[...]` fall back to an unrelated generic officer even though the event payload fired.
- Spawn event is controlled by the UI setting. Do not auto-force campaign-start spawn when the user selected another mode.
  Reason: spawn timing is gameplay behavior. Overriding it in the builder makes the output pack differ from the visible user configuration.
- Generated characters are created by the generated Lua path. The Lua must first preflight `character_for_template`, then use an `attempt_key` saved value to lock one spawn attempt per template per turn before calling the direct 3K spawn API.
  Reason: DB-only spawning previously produced event/fallback failures, while a mixed DB-plus-Lua creation model creates two characters per template. First tick can run before the DB incident has produced the character, causing Lua to spawn one, and then the DB `SPAWN_AGENT_OFF_MAP` payload spawns another one.
- Lua-spawned generated templates still keep sample-compatible spawn fields: use a positive `character_generation_templates.weight` (the sample pack uses `19.5`) and force `can_be_born = false`. Spawn age is user controlled: explicit UI birth-year input creates a cloned age row, while blank input preserves the base/source `spawn_age_range` exactly.
  Reason: the direct spawn call still validates the referenced template, but the editor must not silently replace the user's source-chain choice with a hidden adult-safe value.

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

When copying a selected image set into a generated character folder, pack common composite aliases for the same source image (`norm.png`, `normal.png`, and `noanim.png` under the normal panel folder; state plus `noanim.png` under happy/angry folders).
Reason: vanilla, addon, and generated image folders do not always use the same filename convention. Providing aliases prevents the DB art row from pointing at a folder that exists while the UI panel looks for a missing composite filename.

Important fields:

- `campaign_character_arts.portrait`
- `campaign_character_arts.card`
- `campaign_character_arts.uniform`
- `campaign_character_arts.art_set_id`

Portrait/card key rules:

- `portrait` is the character image folder key and normally includes a trailing slash in DB rows.
  - Example: `portrait = 3k_main_hero_special_zhang_bu_fire/`
- `card` is the unitcard filename stem, not necessarily the folder name.
  - Example path: `ui/characters/3k_main_hero_special_zhang_bu_fire/stills/unitcards/SAD_zhang_bu_fire.png`
  - Matching DB value: `card = SAD_zhang_bu_fire`
- Vanilla-style image sets often use the same value for folder and card, so `portrait` and `card` appear to match.
- Modded sets such as SAD/Korea/custom HBY can split these values. Do not infer `card` from the portrait folder.
- When retargeting image assets, derive `portrait` from the target `ui/characters/<folder>/...` path and derive `card` from the target `stills/unitcards/<file>.png` stem.

Current behavior:

- Existing character edit: copy selected image files into a dedicated `hby_patch_...` image folder, then patch the existing art row's `portrait`/`card` to that folder/file key.
- Existing character edit normally keeps the template's current `art_set_override`, because Korea/190 addon aliases can have multiple template rows and art sets that need to remain connected to the mod script chain.
- If a recipe explicitly changes `art_set_override`, the builder clones the source art set and art rows into the new art set before applying image/model overrides.
- New character clone: create/copy the art set chain and point the new template to that art set.
- The file path must not accidentally create duplicated nested character folders, such as `ui/characters/a/a/...`.
- Pack generation should copy/rename the selected image assets only. It should not invent extra image paths or inject PNG coordinate comments at build time.

The `id` in `campaign_character_arts` is part of the art row key space. When cloning art rows, new ids are generated from the new art set plus the original row shape.

## Equipment And Unit Stat Chain

The web combat tab does not create arbitrary equipment and no longer emits armour/audio stat patches. It uses existing rows as read-only material references for equipment set selection.

Supported stat patch columns are defined in `tk_pack_builder/stat_tables.py`.

Armour:

- Equipment CEO is resolved through `ceos_to_equipment_variants_tables`.
- Equipment set changes clone the selected character's initial CEO stage into a new `hby_mtu_ceo_initial_data_*` key only when a real source stage exists, then replace starting inventory (`ceo_initial_data_active_ceos`) and equipped slots (`ceo_initial_data_equipments`) with the selected set. The Lua equipment script still receives the selected equipment CEO list as a fallback/post-process path.
  Reason: a Lua `add_ceo` grant can be less reliable than a valid DB initial equipment chain, but a fabricated DB chain is worse. Keep DB cloning limited to real source rows and let Lua handle explicit user selections when no real equipment stage is available.
- Armour row lookup through `unit_armour_types` remains available to backend validation and CLI recipes, but the web UI must not emit `armour_value` or `audio_type` patches.
  Reason: mixing `unit_armour_types` edits into the generated-character equipment flow has blocked the selected equipment set from applying reliably. Equipment selection owns the generated character's armour path; armour stat edits are excluded from the web workflow.

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

Spawn event output has three parts:

- Lua script:
  - `script/campaign/3k_main_campaign_map/mod/hby_mtu_pack_editor_player_spawn.lua`
  - `script/campaign/3k_main_campaign_map/hby_mtu_pack_editor_player_spawn.lua`
- Incident DB/loc rows:
  - `db/incidents_tables/event`
  - `db/cdir_events_incident_payloads_tables/event`
  - `db/cdir_events_incident_option_junctions_tables/event`
  - `text/db/hby_mtu_pack_editor_event.loc`
- Output pack type: `Movie`

DB incident rows control the visible turn-one event and its conditions. Each generated turn group needs one `historical` incident key with the sample option set: `CND_FIRST_ROUND`, `GEN_CND_SELF`, `GEN_TARGET_FACTION`, `CND_UNIQUE`, `VAR_CHANCE`, and `CND_LAST_ROUND`; its payload table should keep `LOCATED = FACTION` only. It must not include `SPAWN_AGENT_OFF_MAP` while the generated Lua direct-spawn path is active.

The script preflights existing templates, locks one spawn attempt per template per turn with `attempt_key`, directly spawns the missing template, moves it to the player faction if needed, and applies post-spawn CEO/title/trait changes. In Three Kingdoms the loader path is mod-sensitive, so the builder writes the same script to both campaign-map locations above. Save keys, attempt keys, and `character_for_template` preflight keep the dual write from creating duplicate characters. Do not move the active script to top-level `script/campaign/mod/`, and do not invent `campaign_script_paths_tables` for this project unless the loaded 3K schema actually exposes that table.

Do not use Warhammer-style direct spawn functions such as `cm:spawn_character_to_faction`. Do not combine Lua direct-spawn APIs with DB `SPAWN_AGENT_OFF_MAP` payloads for the same generated character.

Legacy incident template source:

- `work/legacy_template/8King_4P_1.7_up.pack`

The builder copies the working shape from that template, including:

  - `db/incidents_tables/event`
  - `db/cdir_events_incident_payloads_tables/event`
  - `db/cdir_events_incident_option_junctions_tables/event`

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
