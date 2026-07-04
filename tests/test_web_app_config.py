from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_web_script(name: str) -> str:
    return (ROOT / "web" / name).read_text(encoding="utf-8")


class WebAppConfigTest(unittest.TestCase):
    def test_index_script_assets_are_served_by_static_router(self) -> None:
        from tk_pack_builder.web import _static_web_file

        index_html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script_names = re.findall(r'<script src="\./([^"?]+)', index_html)

        self.assertIn("app-state.js", script_names)
        self.assertIn("app-server.js", script_names)
        self.assertEqual(
            [],
            [name for name in script_names if _static_web_file(f"/{name}") != name],
        )
        self.assertIsNone(_static_web_file("/../tk_pack_builder/web.py"))

    def test_internal_materials_build_is_enabled_for_patch_pack(self) -> None:
        app_js = read_web_script("app-state.js")
        match = re.search(r"enabledForSaveMode:\s*'([^']*)'", app_js)

        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "patch_pack")

    def test_generated_character_recipe_preserves_source_initial_ceo(self) -> None:
        recipe_js = read_web_script("app-recipe.js")

        self.assertIn("const cloneInitialCeoForMode = (mode) =>", recipe_js)
        clone_func = recipe_js[recipe_js.index("const cloneInitialCeoForMode = (mode) =>"):]
        clone_func = clone_func[:clone_func.index("};", clone_func.index("return genderCompatibleInitialCeoKey"))]
        self.assertIn("baseDetails[mode]?.initialCeos", clone_func)
        self.assertIn("titleChoiceChanged(titleSource, defaultTitleSource)", clone_func)
        self.assertNotIn("(titleChanged ? titleInitialCeoForModeFromChoice(titleSource, mode) : null)", clone_func)
        self.assertIn("const titleInitial = titleInitialCeoForModeFromChoice(titleSource, mode);", clone_func)
        self.assertIn("return genderCompatibleInitialCeoKey(rawInitialCeo, finalTemplateGender, payload.subtype);", clone_func)
        self.assertIn("initial_ceos: cloneInitialCeoForMode(mode)", recipe_js)
        self.assertIn("newInitialCeoKey: null", recipe_js)
        self.assertIn("initialCeoSourceKey: null", recipe_js)

    def test_character_recipe_applies_selected_title_ceo_separately(self) -> None:
        recipe_js = read_web_script("app-recipe.js")

        self.assertIn("function titleCeoKeyFromChoice(titleSource)", recipe_js)
        self.assertIn("function titleCareerCeoKeyFromValue(value)", recipe_js)
        self.assertIn("titleSource?.titleInitialCeoKey", recipe_js)
        self.assertIn("titleSource?.titleCareerCeoKey", recipe_js)
        self.assertIn(".replace('_ceo_node_career_', '_ceo_career_')", recipe_js)
        self.assertIn(".replace('_ceo_initial_data_character_historical_', '_ceo_career_historical_')", recipe_js)
        self.assertIn("function titleInitialCeoKeyFromCareerCeoKey(titleCeoKey)", recipe_js)
        self.assertIn("function titleInitialCeoKeyFromValue(value)", recipe_js)
        self.assertIn("function knownInitialCeoKeys()", recipe_js)
        self.assertIn("function knownTitleInitialCeoKey(initialCeoKey)", recipe_js)
        self.assertIn("function closestKnownTitleInitialCeoKey(initialCeoKey)", recipe_js)
        self.assertIn("function initialCeoTokenMatchScore(requestedToken, candidateToken)", recipe_js)
        self.assertIn("closestKnownTitleInitialCeoKey(initialCeoKey)", recipe_js)
        self.assertIn("known.has(candidate)", recipe_js)
        self.assertIn("3k_dlc04_ceo_initial_data_character_historical_non_deployable_empress_he_fire", recipe_js)
        self.assertIn("key.replace(/_lady_sun_shangxiang$/i, '_lady_sun')", recipe_js)
        self.assertIn("function isBackgroundTitleCeoKey(key)", recipe_js)
        self.assertIn("if (isBackgroundTitleCeoKey(key)) return key;", recipe_js)
        self.assertIn("if (isBackgroundTitleCeoKey(titleCeoKey)) return null;", recipe_js)
        self.assertIn("function defaultTitleChoiceForCharacter(character)", recipe_js)
        self.assertIn("function titleChoiceChanged(titleSource, defaultTitleSource)", recipe_js)
        self.assertIn("const selected = titleCeoKeyFromChoice(titleSource)", recipe_js)
        self.assertIn("const baseline = titleCeoKeyFromChoice(defaultTitleSource)", recipe_js)
        self.assertIn("if (titleChoiceChanged(titleSource, defaultTitleSource))", recipe_js)
        self.assertNotIn("const titleChanged = titleChoiceChanged(titleSource, defaultTitleSource);", recipe_js)
        self.assertNotIn("(titleChanged ? titleInitialCeoForModeFromChoice(titleSource, mode) : null)", recipe_js)
        self.assertIn("if (currentTitleCeoKey && currentTitleCeoKey === titleCeoKey) return {};", recipe_js)
        self.assertIn("initial_ceos: titleInitial", recipe_js)
        self.assertIn("titleCeoKey,", recipe_js)
        self.assertIn("removableTitleCeoKeys:", recipe_js)
        self.assertIn("...titleCeoRecipeFields(titleSource, targetCharacter)", recipe_js)
        self.assertIn("...titleCeoRecipeFields(titleSource, base)", recipe_js)

    def test_trait_set_cleanup_removes_title_initial_residue(self) -> None:
        helper_js = read_web_script("app-form-helpers.js")

        self.assertIn("const TRAIT_CEO_REMOVAL_EXTRAS = [", helper_js)
        self.assertIn("'3k_main_ceo_trait_personality_disloyal'", helper_js)
        self.assertIn("if (kind === 'trait')", helper_js)
        self.assertIn("keys.push(...TRAIT_CEO_REMOVAL_EXTRAS);", helper_js)

    def test_manual_title_effects_keep_catalog_ceo_keys(self) -> None:
        appearance_js = read_web_script("app-appearance.js")

        self.assertIn("const matchedCatalog = titleCatalogChoices().find", appearance_js)
        self.assertIn("const matchedTitleSource = matchedCatalog || matchedCharacter;", appearance_js)
        self.assertIn("function sheetTitleEntryForManualEffect(effect)", appearance_js)
        self.assertIn("titleCareerCeoKey: matchedTitleSource?.titleCareerCeoKey || sheetCareerKey", appearance_js)
        self.assertIn("titleInitialCeoKeyFromCareerKey(sheetCareerKey)", appearance_js)
        self.assertIn("function knownTitleInitialCeoKeyForTitles(initialCeoKey)", appearance_js)
        self.assertIn("function closestKnownTitleInitialCeoKeyForTitles(initialCeoKey)", appearance_js)
        self.assertIn("function initialCeoTokenMatchScoreForTitles(requestedToken, candidateToken)", appearance_js)
        self.assertIn("closestKnownTitleInitialCeoKeyForTitles(initialCeoKey)", appearance_js)
        self.assertIn("knownInitialCeoKeysForTitles", appearance_js)
        self.assertIn("3k_dlc04_ceo_initial_data_character_historical_non_deployable_empress_he_fire", appearance_js)
        self.assertIn("titleKey: matchedTitleSource?.titleKey", appearance_js)
        self.assertIn("manualTitleChoices().filter((item) => titleChoiceCanSetInitialCeo(item) && (!item.manualTitleOnly || canonicalTitleChoiceKey(item)))", appearance_js)

    def test_title_choices_are_deduped_by_canonical_title_key(self) -> None:
        appearance_js = read_web_script("app-appearance.js")

        self.assertIn("function canonicalTitleChoiceKey(item)", appearance_js)
        self.assertIn("function isBackgroundTitleChoiceKey(value)", appearance_js)
        self.assertIn("function isInitialCeoTitleKey(value)", appearance_js)
        self.assertIn("function titleChoiceCanSetInitialCeo(item)", appearance_js)
        self.assertIn("return keys.some(isInitialCeoTitleKey);", appearance_js)
        self.assertIn("function dedupeTitleChoices(items)", appearance_js)
        self.assertIn("function dedupeTitleChoicesByDisplay(items)", appearance_js)
        self.assertIn("item?.titleCeoKey", appearance_js)
        self.assertIn("titleCeoKey: item.titleCeoKey || item.ceoKey || item.key", appearance_js)
        self.assertIn("dedupeTitleChoices((state.options?.titleCatalog || [])", appearance_js)
        self.assertIn("const catalog = titleCatalogChoices().filter(titleChoiceCanSetInitialCeo);", appearance_js)
        self.assertIn("return sortTitleCandidates(dedupeTitleChoicesByDisplay(dedupeTitleChoices([...manual, ...regular])));", appearance_js)
        self.assertIn("function titleDisplayDedupeKey(character)", read_web_script("app-title-effects.js"))

    def test_title_choices_are_filtered_by_stat_buttons(self) -> None:
        appearance_js = read_web_script("app-appearance.js")
        editor_js = read_web_script("app-editor.js")
        app_js = read_web_script("app.js")
        state_js = read_web_script("app-state.js")
        title_js = read_web_script("app-title-effects.js")
        index_html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        self.assertIn("titleElements: Array.isArray(item.elements) ? item.elements : (item.element ? [item.element] : [])", appearance_js)
        self.assertIn("function titleElementsForChoice(item)", appearance_js)
        self.assertIn("function titleChoicesForFilter(filter", appearance_js)
        self.assertIn("function titleChoicesForPrefix(prefix", appearance_js)
        self.assertIn("titleChoiceMatchesStatFilter(item, filter)", appearance_js)
        self.assertIn("return filtered.length ? sortTitleCandidatesForFilter(filtered, filter) : choices;", appearance_js)
        self.assertIn("titleFilters: {", state_js)
        self.assertIn("const editTitleCandidates = titleChoicesForPrefix('edit', character);", editor_js)
        self.assertIn("const sourceTitleCandidates = titleChoicesForPrefix('source', selectedBase);", editor_js)
        self.assertIn("function refreshTitleSelectForElement(prefix, element", editor_js)
        self.assertIn("function applyTitleFilter(prefix, filter)", editor_js)
        self.assertIn("document.querySelectorAll('[data-title-filter-prefix]')", app_js)
        self.assertIn("const TITLE_STAT_FILTERS = {", title_js)
        self.assertIn("function titleStatValueForFilter(character, filter = 'all')", title_js)
        self.assertIn("function sortTitleCandidatesForFilter(items, filter = 'all')", title_js)
        self.assertIn("authority: { label: '권위'", title_js)
        self.assertIn("cunning: { label: '책략'", title_js)
        self.assertIn('data-title-filter="authority" type="button">권위</button>', index_html)
        self.assertIn('data-title-filter="cunning" type="button">책략</button>', index_html)

    def test_title_option_labels_use_title_stat_and_core_effect(self) -> None:
        title_js = read_web_script("app-title-effects.js")
        editor_js = read_web_script("app-editor.js")

        self.assertIn("function titleEffectDisplayParts(character)", title_js)
        self.assertIn("function splitTitleEffectText(effectText = '')", title_js)
        self.assertIn("return [title, detail].filter(Boolean).join(' - ');", title_js)
        self.assertIn("const { title, detail } = titleEffectDisplayParts(character);", editor_js)

    def test_title_effect_lookup_is_cached_for_fast_dropdowns(self) -> None:
        title_js = read_web_script("app-title-effects.js")

        self.assertIn("let titleEffectObjectCache = new WeakMap();", title_js)
        self.assertIn("const titleEffectKeyCache = new Map();", title_js)
        self.assertIn("const catalogTitleEffectLookupCache = new Map();", title_js)
        self.assertIn("function titleCatalogEffectIndex()", title_js)
        self.assertIn("return cachedDerived('titleCatalogEffectIndex'", title_js)
        self.assertIn("if (titleEffectObjectCache.has(character)) return titleEffectObjectCache.get(character);", title_js)
        self.assertIn("function computeTitleEffectFor(character)", title_js)
        self.assertIn("function titleCandidateSortRows(items)", title_js)
        self.assertIn("const statScores = new Map((items || []).map((item) => [item, titleStatValueForFilter(item, filterKey)]));", title_js)

    def test_open_api_uses_compact_json_and_stable_asset_cache_version(self) -> None:
        web_py = (ROOT / "tk_pack_builder" / "web.py").read_text(encoding="utf-8")
        normalize_js = read_web_script("app-normalize.js")
        server_js = read_web_script("app-server.js")

        self.assertIn("OPEN_PAYLOAD_CACHE_SCHEMA_VERSION = 15", web_py)
        self.assertIn('json.dumps(payload, ensure_ascii=False, separators=(",", ":"))', web_py)
        self.assertIn('"assetCacheToken": asset_cache_token', web_py)
        self.assertIn('cached["assetCacheToken"] = asset_cache_token', web_py)
        self.assertIn("function hydrateFromPackData(characterData, responseEnvelope = {})", normalize_js)
        self.assertIn("state.assetCacheVersion = responseEnvelope.assetCacheToken", normalize_js)
        self.assertNotIn("state.assetCacheVersion = Date.now();", normalize_js)
        self.assertIn("hydrateFromPackData(data.characters, data);", server_js)

    def test_material_and_catalog_changes_invalidate_web_ui_lists(self) -> None:
        web_py = (ROOT / "tk_pack_builder" / "web.py").read_text(encoding="utf-8")

        self.assertIn("def _file_cache_fingerprint(path: Path)", web_py)
        self.assertIn("def _file_cache_key(paths: list[Path])", web_py)
        self.assertIn("catalog_paths = _title_effect_catalog_paths()", web_py)
        self.assertIn("skill_catalog_path = _skill_effect_catalog_path()", web_py)
        self.assertIn('"version": 16', web_py)
        self.assertIn("return _load_title_effect_catalog_for_cache_key(_file_cache_key(_title_effect_catalog_paths()))", web_py)
        self.assertIn("@lru_cache(maxsize=8)\ndef _load_title_effect_catalog_for_cache_key", web_py)
        self.assertIn("return _load_skill_effect_catalog_for_cache_key(_file_cache_key([catalog_path] if catalog_path else []))", web_py)
        self.assertIn("@lru_cache(maxsize=8)\ndef _load_skill_effect_catalog_for_cache_key", web_py)

    def test_skill_nodes_and_candidates_are_deduped_for_ui(self) -> None:
        skills_js = read_web_script("app-skills.js")
        app_js = read_web_script("app.js")

        self.assertIn("function dedupeSkillInfos(items)", skills_js)
        self.assertIn("function dedupeSkillTreeNodes(nodes)", skills_js)
        self.assertIn("function skillNodeModeRank(node)", skills_js)
        self.assertIn("betterSkillNodeForPosition(node, existingAtPosition)", skills_js)
        self.assertIn("return cachedDerived('skillIndexList:deduped'", skills_js)
        self.assertIn("const source = normalizedSkillDedupeText(info?.source || skillSourceLabel(info));", skills_js)
        self.assertIn("function skillSourceLabel(info)", skills_js)
        self.assertIn("function skillSourceBadgeMarkup(info)", skills_js)
        self.assertIn("${skillSourceBadgeMarkup(item)}", skills_js)
        self.assertIn("const nodes = dedupeSkillTreeNodes(tree.nodes);", skills_js)
        self.assertIn("const nodes = dedupeSkillTreeNodes(tree?.nodes || []);", skills_js)
        self.assertIn("dedupeSkillTreeNodes(tree?.nodes || []).find", app_js)

    def test_packaged_effect_catalogs_are_included_in_windows_build(self) -> None:
        spec = (ROOT / "MTU Pack Editor.spec").read_text(encoding="utf-8")
        build_script = (ROOT / "scripts" / "build_windows_exe.ps1").read_text(encoding="utf-8")

        self.assertIn("tk_pack_builder\\\\data\\\\title_effects.ko.json", spec)
        self.assertIn("tk_pack_builder\\\\data\\\\background_title_effects.ko.json", spec)
        self.assertIn("tk_pack_builder\\\\data\\\\skill_effects.ko.json", spec)
        self.assertIn('"title_effects.ko.json"', build_script)
        self.assertIn('"skill_effects.ko.json"', build_script)
        self.assertIn('"asset_manifest.v015.json"', build_script)
        self.assertIn("function Convert-LocalBuildPath", build_script)
        self.assertIn("$normalized.Substring($SourceRoot.Length).TrimStart(\"\\\")", build_script)

    def test_ceo_set_helpers_extract_string_keys_from_cached_objects(self) -> None:
        helpers_js = read_web_script("app-form-helpers.js")

        self.assertIn("function ceoKeyFromValue(value)", helpers_js)
        self.assertIn("value.key || value.ceoKey || value.ceoNodeKey", helpers_js)
        self.assertIn("return key === '[object Object]' ? '' : key;", helpers_js)

    def test_refresh_pack_button_is_visible_and_forces_reload(self) -> None:
        index_html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        app_js = read_web_script("app.js")
        css = read_web_script("app.css")

        self.assertIn('id="refreshPackButton" class="ghost-btn" type="button">DB/팩 다시 읽기</button>', index_html)
        self.assertIn("bind('refreshPackButton', 'click', () => loadPack({ forceRefresh: true }));", app_js)
        for match in re.finditer(r"([^{}]+)\{([^{}]+)\}", css, flags=re.S):
            selector, body = match.groups()
            if "#refreshPackButton" in selector:
                self.assertNotIn("display: none", body)

    def test_generated_character_recipe_keeps_base_retinue_chain(self) -> None:
        recipe_js = read_web_script("app-recipe.js")
        queue_js = read_web_script("app-queue.js")

        self.assertIn("const combat = characters().find((candidate) => candidate.key === payload.sourceKeys?.combatProfile);", recipe_js)
        self.assertNotIn("const combatSource = firstCharacterWithDetails(combat);", recipe_js)
        self.assertIn("const unitSource = characters().find((candidate) => candidate.key === payload.sourceKeys?.unitProfile);", recipe_js)
        self.assertIn("const unit = firstCharacterWithDetails(unitSource, detailSource);", recipe_js)
        self.assertIn("const unitRetinue = retinueKeyForCharacter(unit);", recipe_js)
        self.assertIn("retinue: retinueOverride || unitDetails[mode]?.retinue || unitRetinue", recipe_js)
        self.assertIn("unitProfile: unit?.key", queue_js)

    def test_land_unit_and_armour_stat_edits_are_disabled_in_web_ui(self) -> None:
        recipe_js = read_web_script("app-recipe.js")
        queue_js = read_web_script("app-queue.js")
        editor_js = read_web_script("app-editor.js")
        helpers_js = read_web_script("app-form-helpers.js")

        self.assertIn("const unitStatClone = unitStatCloneFrom('edit', unit, editSlug, itemNumber);", queue_js)
        self.assertNotIn("const armourTypeClone = armourTypeCloneFrom('source', combat || unit, createSlug, itemNumber);", queue_js)
        self.assertIn("const unitStatClone = null;", queue_js)
        self.assertNotIn("armourKey: armourTypeClone?.newKey || ''", queue_js)
        self.assertIn("unitStatClone,", queue_js)
        self.assertNotIn("pushEquipmentStatPatch(recipe, payload.armourPatch);", recipe_js)
        self.assertNotIn("pushEquipmentStatPatch(recipe, payload.armourAudioPatch);", recipe_js)
        self.assertNotIn("recipe.armourTypeClones.push({", recipe_js)
        self.assertNotIn("armourPatch,", queue_js)
        self.assertNotIn("armourAudioPatch,", queue_js)
        self.assertIn("recipe.landUnitClones.push({", recipe_js)
        self.assertIn("retinueOverride = payload.unitStatClone?.newRetinueKey || null", recipe_js)
        self.assertIn("return null;", editor_js)
        self.assertNotIn("equipmentKey: character.armourStatKey", editor_js)
        self.assertNotIn("equipmentKey: character.armourCeo", editor_js)
        self.assertNotIn("id=\"${prefix}ArmourValue\"", helpers_js)
        self.assertNotIn("id=\"${prefix}ArmourAudioType\"", helpers_js)
        self.assertNotIn("unit_armour_types row patch", helpers_js)

    def test_roster_selection_avoids_full_list_and_queue_rerender(self) -> None:
        render_js = read_web_script("app-render.js")
        editor_js = read_web_script("app-editor.js")

        select_body = render_js[
            render_js.index("function selectRosterCharacter"):
            render_js.index("function updateRosterActiveState")
        ]
        self.assertIn("updateRosterActiveState(templateKey);", select_body)
        self.assertIn("renderRoster({ syncSelection: false, renderSelection: false });", select_body)
        self.assertIn("renderSelected({ fillEditor: false });", select_body)
        self.assertNotIn("renderQueue();", select_body)
        self.assertIn("function updateRosterActiveState", render_js)
        self.assertIn("function syncTitleSelectOptions", editor_js)
        self.assertNotIn("groups.editTitleCandidates", editor_js)
        self.assertNotIn("groups.sourceTitleCandidates", editor_js)

    def test_gender_switch_and_roster_browse_do_not_fill_editor_forms(self) -> None:
        workflow_js = read_web_script("app-workflow.js")
        editor_js = read_web_script("app-editor.js")
        app_js = read_web_script("app.js")

        gender_body = workflow_js[
            workflow_js.index("function setWorkflowGender"):
            workflow_js.index("function renderWorkflowGenderButtons")
        ]
        self.assertIn("renderRoster({ syncSelection: false, renderSelection: false });", gender_body)
        self.assertIn("renderSelected({ fillEditor: false });", gender_body)
        self.assertNotIn("state.formOptionsSignature = '';", gender_body)
        self.assertNotIn("renderQueue();", gender_body)

        begin_body = editor_js[
            editor_js.index("function beginWorkflowMode"):
            editor_js.index("function setWorkView")
        ]
        self.assertIn("prepareWorkflowForms(selectedCharacter(), mode);", begin_body)
        self.assertNotIn("fillForms(selectedCharacter());", begin_body)
        self.assertIn("bind('editModeButton', 'click', () => beginWorkflowMode('edit'));", app_js)
        self.assertIn("bind('createModeButton', 'click', () => beginWorkflowMode('create'));", app_js)
        self.assertIn("renderSelected({ fillEditor: false });", app_js[app_js.index("function renderAll"):app_js.index("function bind")])

    def test_workflow_buttons_use_lazy_dropdown_option_ownership(self) -> None:
        editor_js = read_web_script("app-editor.js")
        app_js = read_web_script("app.js")

        self.assertIn("function setLazySelect(id, optionLoader, selectedOption = null)", editor_js)
        self.assertIn("select._optionLoader = optionLoader;", editor_js)
        self.assertIn("function ensureSelectOptionsLoaded(select)", editor_js)
        self.assertIn("ensureSelectOptionsLoaded(select);", editor_js)
        self.assertIn("function prepareCreateWorkflowForms(character)", editor_js)
        self.assertIn("setLazySelect('sourceBase', () => selectableFormCharacters().map(baseSelectOption), baseSelectOption(character));", editor_js)
        self.assertIn("setLazySelect('sourceImageSet', () => selectableImageAppearances().map(appearanceOption), imageSelectOptionForCharacter(character));", editor_js)
        self.assertIn("setLazySelect('sourceSkill', () => selectableFormCharacters().map(skillSelectOption), skillSelectOption(character));", editor_js)
        self.assertIn("setLazySelect('sourceTitle', () => titleChoicesForPrefix('source', character).map", editor_js)
        self.assertIn("function applyCreateBaseDefaults(base)", editor_js)
        self.assertIn("applyCreateBaseDefaults(base);", app_js)

        begin_body = editor_js[
            editor_js.index("function beginWorkflowMode"):
            editor_js.index("function setWorkView")
        ]
        self.assertIn("setMode(mode);", begin_body)
        self.assertIn("prepareWorkflowForms(selectedCharacter(), mode);", begin_body)

        mode_body = editor_js[
            editor_js.index("function setMode"):
            editor_js.index("function beginWorkflowMode")
        ]
        self.assertNotIn("renderAppearanceGallery();", mode_body)

        tab_body = editor_js[
            editor_js.index("function setWorkTab"):
            editor_js.index("function syncEquipmentSummary")
        ]
        self.assertIn("if (target.endsWith('-appearance')) renderAppearanceGallery();", tab_body)

    def test_form_option_cache_is_not_invalidated_by_gender_only_change(self) -> None:
        editor_js = read_web_script("app-editor.js")
        signature_body = editor_js[
            editor_js.index("function formOptionsSignature"):
            editor_js.index("function syncTitleSelectOptions")
        ]

        self.assertNotIn("groups.editGender", signature_body)
        self.assertNotIn("groups.createGender", signature_body)
        self.assertIn("signatureForOptions(groups.selectableCharacters)", signature_body)

    def test_roster_uses_client_side_paged_rendering(self) -> None:
        web_py = (ROOT / "tk_pack_builder" / "web.py").read_text(encoding="utf-8")
        catalog_js = read_web_script("app-catalog.js")
        render_js = read_web_script("app-render.js")
        normalize_js = read_web_script("app-normalize.js")
        data_js = read_web_script("app-data.js")
        state_js = read_web_script("app-state.js")

        self.assertNotIn("uiIndexes", web_py)
        self.assertNotIn("state.options?.uiIndexes", catalog_js)
        self.assertIn("function rosterCharactersForCurrentGender", catalog_js)
        self.assertIn("const visibleCharacters = rosterCharactersForCurrentGender();", render_js)
        self.assertIn("function appendRosterSlice", render_js)
        self.assertIn("list.appendChild(renderRosterCard(character));", render_js)
        self.assertIn("rosterFilteredCharacters", state_js)
        self.assertIn("rosterRenderedCount", state_js)
        self.assertIn("appendRosterSlice();", state_js)
        self.assertIn("character.rosterSearchText", render_js)
        self.assertIn("const rosterSearchText = normalizeLookupText", normalize_js)
        self.assertIn("rosterSearchText,", normalize_js)
        self.assertIn("const ROSTER_INITIAL_RENDER_LIMIT = 50;", data_js)
        self.assertIn("const SCROLL_RENDER_STEP = 50;", data_js)
        self.assertIn("const APPEARANCE_GALLERY_INITIAL_RENDER_LIMIT = 80;", data_js)

    def test_index_uses_css_expected_shell_and_filter_values(self) -> None:
        index_html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        self.assertIn('<main class="app-shell">', index_html)
        self.assertNotIn('class="app-layout"', index_html)
        self.assertIn('data-filter="earth" type="button">土</button>', index_html)
        self.assertIn('data-filter="fire" type="button">火</button>', index_html)
        self.assertIn('data-filter="wood" type="button">木</button>', index_html)
        self.assertIn('data-filter="water" type="button">水</button>', index_html)
        self.assertIn('data-filter="metal" type="button">金</button>', index_html)
        self.assertIn('class="filter-row korea-filter-row"', index_html)
        self.assertIn('data-filter="korea:goguryeo"', index_html)
        self.assertIn('data-filter="favorites"', index_html)
        self.assertIn('class="roster-heading"', index_html)
        self.assertIn('class="gender-row roster-gender-row"', index_html)
        self.assertNotIn('<div class="gender-row" role="group" aria-label="성별 필터">', index_html)
        self.assertLess(index_html.index('class="gender-row roster-gender-row"'), index_html.index('id="searchInput"'))
        self.assertIn('class="hero-preview"', index_html)
        self.assertNotIn('class="preview-head"', index_html)
        self.assertIn('class="hero-summary"', index_html)
        self.assertIn('class="stat-grid"', index_html)
        self.assertIn('class="image-set-preview"', index_html)
        self.assertIn('class="spawn-help"', index_html)
        self.assertIn('class="workflow-actions"', index_html)

    def test_character_editor_does_not_expose_model_swaps(self) -> None:
        script_text = "\n".join(
            read_web_script(name)
            for name in ("app.js", "app-queue.js", "app-recipe.js")
        )
        index_html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        self.assertIn('select id="editGender"', index_html)
        self.assertIn('select id="createGender"', index_html)
        self.assertIn('select id="editSkill"', index_html)
        self.assertNotIn('id="editModelSet"', index_html)
        self.assertNotIn('id="sourceModelSet"', index_html)
        self.assertNotIn("payload.modelSetKey", script_text)
        self.assertNotIn("payload.sourceKeys?.modelSet", script_text)

    def test_generated_character_spawn_uses_single_round_input(self) -> None:
        recipe_js = read_web_script("app-recipe.js")
        queue_js = read_web_script("app-queue.js")
        workflow_js = recipe_js + "\n" + queue_js
        index_html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        self.assertIn("const spawnPlan = generatedSpawnPlan({ minRound: $('createMinRound').value });", workflow_js)
        self.assertIn("event: spawnPlan.event", workflow_js)
        self.assertIn("maxRound: 999", workflow_js)
        self.assertIn("spawnEvent: spawnPlan.event", workflow_js)
        self.assertIn("min_spawn_round: spawnPlan.minRound", workflow_js)
        self.assertIn("max_spawn_round: 999", workflow_js)
        self.assertNotIn("event: $('sourceSpawnEvent').value", workflow_js)
        self.assertNotIn("maxRound: Number($('createMaxRound').value)", workflow_js)
        self.assertIn('<select id="sourceSpawnEvent" hidden aria-hidden="true"></select>', index_html)
        self.assertNotIn("<span>등장 이벤트</span>\n              <select id=\"sourceSpawnEvent\"></select>", index_html)

    def test_image_art_keys_do_not_invent_missing_card_assets(self) -> None:
        recipe_js = read_web_script("app-recipe.js")
        workflow_js = read_web_script("app-workflow.js")

        self.assertIn("function artImageKeysFromTargetAssets(imageAssets, fallbackPortraitToken = '', fallbackCardToken = '')", workflow_js)
        self.assertIn("const cardStem = imageFileStemFromPath(cardPath) || fallbackCardToken;", workflow_js)
        self.assertNotIn("const cardStem = imageFileStemFromPath(cardPath) || fallbackCardToken || portraitFolder;", workflow_js)
        self.assertIn("artImageKeysFromTargetAssets(patchImageAssets, targetImageToken)", recipe_js)
        self.assertNotIn("artImageKeysFromTargetAssets(patchImageAssets, targetImageToken, targetCardToken)", recipe_js)

    def test_custom_image_assets_emit_composite_aliases(self) -> None:
        workflow_js = read_web_script("app-workflow.js")

        self.assertIn("function retargetImageAssetPaths(path, sourceToken, targetToken)", workflow_js)
        self.assertIn("`${prefix}normal${extension}`", workflow_js)
        self.assertIn("`${prefix}noanim${extension}`", workflow_js)

    def test_generated_image_tokens_are_shortened_from_long_template_keys(self) -> None:
        recipe_js = read_web_script("app-recipe.js")

        self.assertIn("function shortImageWorkToken(prefix, slug, itemNumber)", recipe_js)
        self.assertIn("const patchImageToken = shortImageWorkToken('hby_patch', workSlug, itemNumber);", recipe_js)
        self.assertIn("const customImageToken = shortImageWorkToken('hby_clone', slug, itemNumber);", recipe_js)
        self.assertNotIn("const patchImageToken = `hby_patch_${workSlug}`;", recipe_js)
        self.assertNotIn("const customImageToken = customTemplateKey;", recipe_js)

    def test_existing_character_patch_preserves_current_art_set_by_default(self) -> None:
        recipe_js = read_web_script("app-recipe.js")

        self.assertIn("const patchArtSetId = '';", recipe_js)
        self.assertIn("art_set_override: patchArtSetId || undefined", recipe_js)

    def test_initial_view_opens_work_queue(self) -> None:
        state_js = read_web_script("app-state.js")
        app_js = read_web_script("app.js")
        index_html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        self.assertIn("workView: 'queue'", state_js)
        self.assertIn('<aside class="work-panel queue-mode">', index_html)
        self.assertIn('id="queueModeButton" class="mode-btn active"', index_html)
        self.assertNotIn('id="editPanel" class="work-mode active"', index_html)
        self.assertLess(app_js.index("setWorkView('queue');"), app_js.index("loadPack();"))
        self.assertIn("function bootstrapApp()", app_js)
        self.assertIn("showBootstrapError(error)", app_js)
        self.assertLess(app_js.index("renderQueue();", app_js.index("function bootstrapApp()")), app_js.index("loadPack();"))

    def test_roster_only_shows_characters_with_game_mode_details(self) -> None:
        catalog_js = read_web_script("app-catalog.js")

        self.assertIn("function hasCharacterDetails(character)", catalog_js)
        self.assertIn("hasRealTemplateRow(character) && hasCharacterDetails(character)", catalog_js)
        self.assertIn("&& hasCharacterDetails(character)", catalog_js)


if __name__ == "__main__":
    unittest.main()
