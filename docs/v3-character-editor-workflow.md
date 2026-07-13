# V3 Character Editor Workflow

## Goals

The editor uses one common workflow for both existing-character edits and new-character creation.

- Existing edit keeps the selected character template key.
- New create clones from the selected base character and writes new `hby_*` keys.
- Gender and model chains are not edited after the base character is chosen.
- Image, title, attribute set, equipment stats, skillset, spawn, and later traits are editable surfaces.

## Fixed Output Contract

These rules are the baseline contract, not optimization details. If code changes conflict with this section, the code is wrong unless this document is intentionally updated first.

- Existing-character edit patches the existing template and connected source rows. It must not create a second character template for a normal edit.
  Reason: existing edits are replacements for a known in-game character. Creating a second template makes the original campaign/script references keep pointing at the old character.
- New-character create always creates a new `hby_template_*` row and copies the required base rows into new `hby_*` keys.
  Reason: generated characters need their own identity, spawn state, art chain, and patch-owned rows so they do not overwrite or corrupt the source character.
- A new character's default `initial_ceos` comes from the base/source character template, per game mode. If the user explicitly changes the title source in the UI, the changed title source may override `initial_ceos`; otherwise the base value must be kept. If the source detail row is generic but the base template is a named character, derive the named key from the base template, for example `3k_main_template_historical_guan_yu_hero_wood` -> `3k_main_ceo_initial_data_character_historical_guan_yu`.
  Reason: generated characters are base-character clones with selected surfaces swapped in. Default values must preserve the chosen base chain, while explicit UI changes must be reflected in the generated DB rows.
- Clone `frontend_character_ceos_tables` rows from the base/source template to the new template.
  Reason: this is the DB-visible Three Kingdoms link between a frontend character template and CEO presentation/trait data. Without it, a generated template can keep its display name but lose the supporting character CEO chain.
- Selected title/career effects are applied as actual CEO keys, separately from `initial_ceos`. Convert loc/node keys such as `*_ceo_node_career_*_01` to the grantable `*_ceo_career_*` key and add it through the campaign CEO set script.
  Reason: many visible titles are represented by career CEO nodes while the template detail row still uses a generic initial CEO. Treating the node/loc title as `initial_ceos` makes the saved pack differ from the title selected in the UI.
- The editor does not synthesize new `ceos`, `ceo_nodes`, or `ceo_initial_data_*` stage/equipment rows. It may only clone an existing initial-data stage chain when the source materials actually contain that chain.
  Reason: a schema-shaped row with invented category, target, or slot values is not a real game row. If reference materials expose only the key row, keep the source `initial_ceos` and let the generated Lua attempt the explicit title/trait/equipment CEO changes.
- Trait, equipment, and title CEO lists passed to Lua must be plain string keys. Do not pass `{ key, label }` option objects through recipe fields.
  Reason: JavaScript object values stringify to `[object Object]`; if that reaches Lua, the game receives a meaningless CEO key and the visible UI choice is not applied.
- Equipment set selection clones the base/selected character's initial CEO chain into a new `hby_mtu_ceo_initial_data_*` key only when the source chain has real stage rows. The Lua post-process still receives the selected equipment CEO list.
  Reason: starting equipment is most stable when represented in the existing DB stage shape, but an invented stage is worse than no stage because it can point at invalid categories or slots. Lua remains the fallback for explicit user selections when no real DB equipment stage exists.
- Generic initial CEO keys may only be gender-normalized between `generic_m_*` and `generic_f_*` when the template gender requires it.
  Reason: generic keys are interchangeable fallback rows by gender/element. Named, historical, and lady keys are intentional content and must not be downgraded.
- New art set and new art rows created for a new character belong in `_mtu_characters` output tables. Do not let source table resolution write newly created clone art rows back into `data__`, Korea addon tables, or other reference/source tables.
  Reason: source table resolution tells us where the material came from, not where new patch-owned rows should live. Mixing new rows into source/addon table names can make RPFM output and game lookup inconsistent.
- Generated characters use Lua as the creation path. The DB incident remains for the visible event/conditions and keeps `LOCATED = FACTION`, but it must not include `SPAWN_AGENT_OFF_MAP` while Lua direct spawn is active.
  Reason: DB-only and Lua-only attempts failed for different reasons, but the confirmed duplicate output had both DB `SPAWN_AGENT_OFF_MAP` and Lua direct spawn active with no attempt lock. That combination creates two characters per template.
- The generated Lua must run a preflight template-existence check before any spawn/post-process body. If `character_for_template(template)` already returns a live character, mark that spawn save key complete first. If not, set an `attempt_key` saved value for the current turn before calling the direct spawn API.
  Reason: first-turn listeners and dual campaign script paths can race. The Lua side must lock both already-created templates and in-progress spawn attempts, so double triggers do not become double characters.
- Spawn age is not silently normalized. If the user enters a birth year, clone a spawn-age row with that value; if the field is blank, preserve the base/source character's `spawn_age_range`.
  Reason: the editor must not reinterpret user intent. Child-chain risk is real for young sources, but changing it is an explicit UI choice, not a hidden builder correction.
- Generated characters always write `min_rank = 3` and `max_rank = 3` in both historical and romance detail rows. The game displays this as starting rank 4.
  Reason: the created general should enter the campaign at a fixed usable rank instead of inheriting a low or variable source rank.
- The generated Lua is packed at both `script/campaign/3k_main_campaign_map/mod/hby_mtu_pack_editor_player_spawn.lua` and `script/campaign/3k_main_campaign_map/hby_mtu_pack_editor_player_spawn.lua`.
  Reason: local 3K/Korea extracted scripts differ on campaign-map subfolder loading. The shared `attempt_key` prevents the dual write from creating duplicate characters if both paths load.
- Do not add Warhammer-style `cm:spawn_character_to_faction` calls. Verified Lua direct-spawn calls must stay behind the generated preflight and attempt lock, and must not be paired with DB `SPAWN_AGENT_OFF_MAP` for the same template.
  Reason: wrong direct-spawn APIs can crash or silently fail, and valid direct-spawn APIs can duplicate characters if another creator path is still alive.
- Existing-character image replacement usually patches the existing connected art rows. It should stay in the source table unless the recipe explicitly creates a new art set.
  Reason: existing characters may be wired through addon-specific template/art-set chains. Moving them to a new art set without request can disconnect campaign scripts or alias rows.
- Image set selection changes `portrait`, `card`, and copied UI image assets. It also packs common composite aliases (`norm`, `normal`, `noanim`) for the same selected source image. It does not decide template gender and must not block cross-gender-looking image files.
  Reason: image files are presentation assets. Template gender, voice, model, and animation compatibility come from DB rows, not from what the selected portrait looks like.
- Historical and romance detail rows are separate rows. New-character output must always contain both; existing-character edits must also leave both rows present. If the source has only one, duplicate the available source row for the missing mode; for edits, apply the fallback source mode's override when the missing mode has no explicit override.
  Reason: the game reads different detail rows per game mode. Updating or generating only one mode leaves the other mode with stale title, retinue, skill, or attribute data.
- Retinue, land-unit, attribute set, skillset, traits, and equipment are selected surfaces. Changing one surface must not silently reset another surface back to the base character.
  Reason: the UI lets the user compose these choices independently. Hidden fallbacks make the saved pack differ from the visible selections and are hard to diagnose in game.

## New Character Table Contract

This is the required table catalog for generated characters. Treat it as the review checklist when spawn, title, trait, equipment, image, age, or armour values do not match the UI.

### Required identity and visual chain

- `character_generation_templates_tables`
  Reason: registers the generated template key, gender, subtype, name id, art set override, spawn age range, and spawnability flags.
- `character_generation_template_game_mode_details_tables`
  Reason: owns the per-mode `historical` and `romance` detail rows. `initial_ceos`, retinue, skill set, attribute set, and spawn rounds must be valid in both modes.
- `campaign_character_art_sets_tables`
  Reason: provides the `art_set_override` hub referenced by the template.
- `campaign_character_arts_tables`
  Reason: provides the actual portrait, card, stills/unitcards, and model paths used by the art set.
- `ceo_initial_datas_tables`
  Reason: provides the key referenced by `game_mode_details.initial_ceos`. A generated detail row that points at an uncopied or missing initial CEO key is an empty chain.
- `names_tables`
  Reason: stores the generated display-name id used by the template.
- `text/db/*.loc`
  Reason: provides `names_name_<id>` and `names_alt_name_<id>` display strings.
- `character_generation_spawn_age_ranges_tables`
  Reason: used only when the user enters an age/birth-year override. Blank age input preserves the base/source `spawn_age_range`.

### Optional CEO initial chain when a real source stage exists

- `ceo_initial_data_stages_tables`
- `ceo_initial_data_to_stages_tables`
- `ceo_initial_data_active_ceos_tables`
- `ceo_initial_data_equipments_tables`

Reason: Three Kingdoms applies starting title/trait/equipment through the initial CEO stage chain when that chain is valid. `ceo_initial_datas` alone is key-only, so the builder must not create a new `hby_mtu_ceo_initial_data_*` unless it can also clone real stage, active CEO, and equipment rows from the source materials.

### Optional stat and skill chains

- `unit_armour_types_tables`
  Reason: backend/CLI recipes can still resolve armour value/audio rows here, but the web UI must not emit generated-character armour/audio patches. Equipment set application owns the generated armour path.
- `character_skill_nodes_tables`
  Reason: stores selected skill node replacements.
- `character_skill_node_links_tables`
- `character_skill_level_to_effects_junctions_tables`
- `effects_tables`
  Reason: copied only as needed for skill tree links/effects. Skill node labels alone are not enough if linked effect rows are missing.
- `effect_bonus_value_ids_unit_sets_tables`, `effect_bonus_value_unit_ability_junctions_tables`, `unit_abilities_tables`, `unit_special_abilities_tables`, `special_ability_*_tables`, `projectiles_tables`, and projectile display/impact/bombardment tables.
  Reason: active battle skills such as arrow-rain abilities can show an enabled button from the land-unit ability junction but still fail to fire unless the effect unlock, special ability, projectile, contact effect, and targeting/display dependencies are copied together.

### Spawn event and script chain

- `incidents_tables`
- `cdir_events_incident_option_junctions_tables`
- `cdir_events_incident_payloads_tables`
  Reason: used for the visible turn event and conditions. While Lua direct spawn is active, the payload table must not also carry `SPAWN_AGENT_OFF_MAP` for the same generated template.
- `script/campaign/3k_main_campaign_map/hby_mtu_pack_editor_player_spawn.lua`
- `script/campaign/3k_main_campaign_map/mod/hby_mtu_pack_editor_player_spawn.lua`
  Reason: Lua is the current creator path. It must preflight `character_for_template`, set the attempt lock before direct spawn, and only then apply post-spawn CEO/equipment correction.

### Excluded from the generated-character edit contract

- `start_pos_character_inventories_tables`
  Reason: start-pos inventory rows are fixed-faction start-position data. They do not satisfy the "any player faction" generated-character path.
- `campaign_script_paths_tables`
  Reason: this project uses the 3K campaign-map script folder loading path instead of inventing a campaign script path DB dependency.
- `land_units_tables` as a user stat-edit output
- `unit_armour_types_tables` as a web UI stat-edit output
  Reason: armour value/audio patches interfere with generated-character equipment set application. Keep the rows available for backend material lookup, but do not expose or emit them from the web workflow.
- `land_units_tables` as a user stat-edit output
  Reason: current UI must not promise land-unit stat edits. The builder may still copy existing `land_units`, `retinues`, `retinue_slot_initial_units`, and related dependency rows when preserving an existing retinue chain; that is dependency copying, not a land-unit stat edit feature.

## External Guide Baseline

Source: Steam guide `[MOD GUIDE] Custom Character Creation`, https://steamcommunity.com/sharedfiles/filedetails/?id=1798650568

Use this guide as a baseline shape, not as an unquestioned current schema. It was written for an older 3K/RPFM period, but it still captures the core dependency chain that caused the current spawn failures.

- The guide separates custom character creation into seven character tables plus three event tables.
  Reason: if the event message appears but the intended template does not spawn, do not inspect only Lua. Check the DB event payload and the character template chain together.
- `character_generation_templates` depends on the name rows, spawn age range, and art set. Its `art_set_override`, gender, unique flag, voice, and subtype must remain valid for the generated template.
  Reason: a valid event payload can still produce a random generic character if the referenced template fails validation.
- `character_generation_template_game_mode_details` must contain both `historical` and `romance` rows for a generated character.
  Reason: the guide explicitly treats them as separate rows, and the game reads the current campaign mode's row. One good mode does not prove the other mode is valid.
- `initial_ceos` controls starting title, items, and traits. Named/unique initial CEO chains can have one-copy behavior, while generic chains are safer but lose named title/trait identity.
  Reason: our editor defaults to the base character chain, then applies explicit UI swaps. Do not downgrade named base data to generic unless that was the selected source.
- The Steam guide's event spawn is DB-driven through `incidents`, `cdir_events_incident_payloads`, and `cdir_events_incident_option_junctions`, with `SPAWN_AGENT_OFF_MAP` carrying `AGENT_SUBTYPE[...]` and `CHARACTER_TEMPLATE[...]`. This editor intentionally does not use that DB spawn payload while Lua direct spawn is active.
  Reason: the guide remains useful for template/detail/art/age chain validation, but this project uses Lua as the single creator to avoid the confirmed DB-plus-Lua duplicate spawn path.
- Output pack type must remain `Mod` so the patch follows the user's mod-manager load order and can be disabled normally.
  Reason: the guide's event flow assumes the pack is loaded at campaign start without the user enabling it as a normal mod dependency.
- The guide comments contain a later correction: `character_generation_templates.subtype` and a matching `ceo_initial_datas` row were required to stop random generic output.
  Reason: if the event fires and a random character appears, treat subtype and initial CEO chain integrity as first-class checks.

## Fixed Base Chain

Gender is selected first, then the user chooses a base character filtered by that gender.

The following records follow the selected/base character and are not freely swapped in the UI:

- `character_generation_templates.is_male`
- `character_generation_templates.voiceover_actor`
- model/uniform fields in `campaign_character_arts`
- base `art_set_override`
- base retinue/land-unit chain

This avoids cross-gender and cross-model partial overrides where template, art set, initial CEO, voice, and retinue rows no longer agree.

## Editable Fields

The common editor allows:

- display name
- image set
- title / initial CEO source
- attribute set and attribute stat patch
- equipment stat patch
- subtype / element
- spawn age and spawn round
- one skillset source

Skillset source is selected once. The selected source character's historical skillset goes to historical mode, and its romance skillset goes to romance mode. If a romance skillset is missing, the historical skillset is reused.

## Existing Edit

Existing edit uses the selected character template key as the target.

- Image edit copies selected image assets into a dedicated patch image folder and patches the existing art row image keys.
- Model, voice, and gender are not patched.
- Retinue/land unit remains the selected character's original chain.

## New Create

New create clones the selected base character.

- The new character gets a new `hby_template_*` key.
- The cloned template keeps the base character gender, voice, and model chain.
- The cloned art set uses the base art set as source.
- Image edit copies selected image assets into the new `hby_template_*` image folder.
- Retinue/land unit follows the base character.

## Trait Work

Trait free replacement is a separate data task. The current web summary exposes initial CEO/title data, but not a complete user-editable trait list. Do not fake a trait editor until the source trait rows and loc strings are parsed into the snapshot/material data.
