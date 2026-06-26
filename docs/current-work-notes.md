# MTU Pack Editor Current Work Notes

## Quick Run

- Current packaged app URL: `http://127.0.0.1:8765/`
- If the in-app browser is on `http://127.0.0.1:8766/`, that is the old dev-server URL and may be stale/off.
- Packaged exe path:
  `E:\mtu-pack-editor-main\mtu-pack-editor-main\dist\MTU Pack Editor\MTU Pack Editor.exe`

## Korea Character DB

- Korea characters are not meant to be read from the workshop pack at runtime.
- The workshop pack was extracted into an internal DB JSON:
  `work/internal_dbs/korea_characters.json`
- Source pack used for extraction:
  `E:\SteamLibrary\steamapps\workshop\content\779340\2875547086\!!190_expanded_with_characters.pack`
- Extraction command:
  `python scripts/build_korea_internal_db.py`

Current extracted counts:

- Character DB tables: 25 table groups
- Loc text rows: 15,600
- Asset paths: 16,811
- Summary rows: 634
- Real Korea roster templates tagged for `韓`: 104

Important distinction:

- The internal DB keeps all extracted summary rows, including image/model candidates.
- Only real template characters are tagged with `regionTag: "korea"` for the `韓` roster filter.
- This prevents image-only candidates from appearing as normal generals.

## UI Behavior

- `韓` filter exists in `web/index.html`.
- `web/app.js` uses `regionTag === "korea"` for the Korea filter.
- Normal roster still favors characters with unique image sets.
- For `韓` only, the roster intentionally shows all real Korea templates, even if they do not have unique image sets.

Verified packaged app result:

- API path: `dist\MTU Pack Editor\work\reference_snapshot.json`
- Internal DB count: 1
- Total character/candidate data: 2507
- `韓` roster count: 104

## Build Notes

- Build command:
  `powershell -ExecutionPolicy Bypass -File scripts\build_windows_exe.ps1 -Python "C:\Users\hby03\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -SkipPyInstallerInstall`
- `scripts/build_windows_exe.ps1` copies `work/internal_dbs` into:
  `dist\MTU Pack Editor\work\internal_dbs`
- Runtime should not auto-open default/reference pack files for built-in data. Default stat and localisation sources are extracted into:
  `work\internal_dbs\default_stat_reference.json`
  `work\internal_dbs\localisation_kr.json`
- Built-in/reference character images should be served from `work\assets` when available. Use:
  `python scripts\extract_reference_assets.py`

## RPFM Notes

- RPFM must have schemas loaded before decoding custom DB tables.
- If table decoding fails with `Missing or invalid extra data provided: "schema"`, run:
  `python scripts\rpfm_schema_smoke.py`
- RPFM config path is under:
  `%APPDATA%\FrodoWazEre\rpfm\config`
- Do not force `APPDATA`/`LOCALAPPDATA` to the workspace for RPFM. That caused config initialization failures.

## Useful Workshop Pack Roles

- `!!190_expanded_kr.pack`: Korean localization patch.
- `!!190_expanded_region.pack`: extra regions/map, includes Korea.
- `!!190_expanded_overhauladdition.pack`: overhaul/gameplay additions.
- `!!190_expanded_with_characters.pack`: character/faction content; this is the Korea character DB source.

## Next Likely Work

- Make Baekje/Goguryeo/Silla leader replacement write actual pack deltas using internal DB source rows.
- Add a small in-app DB status panel showing whether `korea_characters.json` is loaded and how many Korea characters are available.
- If names like `generic agent legendary f` are too raw, improve loc/name resolution for the Korea internal DB summary.

## Removed Korea Internal Roster

- The Korea internal roster DB was removed after deciding it is not useful for the current event/startpos replacement work.
- Removed generated files:
  `work\internal_dbs\korea_characters.json`
  `dist\MTU Pack Editor\work\internal_dbs\korea_characters.json`
- Restored `work\reference_snapshot.json` and packaged `dist\MTU Pack Editor\work\reference_snapshot.json` from:
  `work\reference_snapshot.before-korea-internal-20260626150704.json`
- Current verified counts:
  total pack characters: 1903
  Korea-tagged characters: 0
  loaded internal DBs: 0

## Korean Plus Internal Roster Restored

- The Korea internal roster DB is now sourced from Korean Plus instead of the base 190 Expanded character pack.
- Source pack:
  `E:\SteamLibrary\steamapps\workshop\content\779340\3415534775\!!190expande_korea_addon.pack`
- Generated file:
  `work\internal_dbs\korea_characters.json`
- Packaged copy:
  `dist\MTU Pack Editor\work\internal_dbs\korea_characters.json`
- The DB keeps Korean Plus unique templates for Goguryeo/Baekje/Silla/Gaya/Tamna-adjacent rosters and related Korean unique characters.
- Current generated counts:
  character templates: 84
  game mode detail rows: 168
  art sets: 28
  art rows: 84
  skill node sets: 42
  summary character rows: 87
  Korea-tagged real templates: 84
- `web/index.html` has the `韓` roster filter restored, plus faction filters:
  `고구려`, `백제`, `신라`, `가야`, `탐라`.
- The internal DB now includes every non-dummy, non-scripted historical character template from:
  `db/character_generation_templates_tables/!!ironic_addon_korea`
  `db/character_generation_templates_tables/!!ironic_addon_korea_leader_fix`
- Scripted generic event templates such as `3k_mod_template_scripted_korean_*` are intentionally excluded from the normal roster.
