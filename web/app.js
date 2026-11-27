function renderAll() {
  renderRoster();
  renderSelected({ fillEditor: false });
  renderAppearanceGallery();
  renderQueue();
  refreshStageButtons();
  renderValidation();
}

function bind(id, eventName, handler) {
  const element = $(id);
  if (!element) {
    console.warn(`[MTU Pack Editor] missing element: #${id}`);
    return null;
  }
  element.addEventListener(eventName, handler);
  return element;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

for (const button of document.querySelectorAll('.filter')) {
  button.addEventListener('click', () => {
    state.filter = button.dataset.filter;
    resetRosterRenderLimit();
    for (const item of document.querySelectorAll('.filter')) item.classList.remove('active');
    button.classList.add('active');
    renderRoster();
  });
}

for (const button of document.querySelectorAll('[data-workflow-gender]')) {
  button.addEventListener('click', () => setWorkflowGender(button.dataset.workflowGender));
}

bind('rosterFavorites', 'click', () => {
  state.favoritesOnly = !state.favoritesOnly;
  $('rosterFavorites').setAttribute('aria-pressed', String(state.favoritesOnly));
  resetRosterRenderLimit();
  renderRoster();
});
bind('rosterClear', 'click', () => {
  state.filter = 'all';
  state.rosterFaction = 'all';
  state.favoritesOnly = false;
  $('searchInput').value = '';
  $('rosterFavorites').setAttribute('aria-pressed', 'false');
  document.querySelectorAll('.filter').forEach((item) => item.classList.toggle('active', item.dataset.filter === 'all'));
  resetRosterRenderLimit();
  renderRoster();
});
bind('rosterFaction', 'change', () => {
  state.rosterFaction = $('rosterFaction').value;
  resetRosterRenderLimit();
  renderRoster();
});
bind('searchInput', 'input', () => {
  resetRosterRenderLimit();
  debounceRender('roster', renderRoster);
});
bind('characterList', 'scroll', () => debounceRender('rosterScroll', maybeLoadMoreRoster, 40));
const appearanceSearch = $('appearanceSearchInput');
if (appearanceSearch) {
  appearanceSearch.addEventListener('input', () => {
    state.imageGalleryQuery = appearanceSearch.value;
    resetAppearanceGalleryRenderLimit();
    debounceRender('appearanceGallery', renderAppearanceGallery);
  });
}
const detailPanel = document.querySelector('.detail-panel');
if (detailPanel) {
  detailPanel.addEventListener('scroll', () => debounceRender('appearanceGalleryScroll', maybeLoadMoreAppearanceGallery, 40));
}
bind('characterList', 'click', (event) => {
  const favoriteButton = event.target.closest('[data-character-favorite]');
  if (favoriteButton) {
    event.preventDefault();
    event.stopPropagation();
    toggleFavoriteCharacter(favoriteButton.dataset.characterFavorite);
    return;
  }
  const card = event.target.closest('[data-character-key]');
  if (card) selectRosterCharacter(card.dataset.characterKey);
});
bind('characterList', 'keydown', (event) => {
  if (event.key !== 'Enter' && event.key !== ' ') return;
  const favoriteButton = event.target.closest('[data-character-favorite]');
  if (favoriteButton) {
    event.preventDefault();
    event.stopPropagation();
    toggleFavoriteCharacter(favoriteButton.dataset.characterFavorite);
    return;
  }
  const card = event.target.closest('[data-character-key]');
  if (!card) return;
  event.preventDefault();
  selectRosterCharacter(card.dataset.characterKey);
});
bind('appearanceGallery', 'click', (event) => {
  const favoriteButton = event.target.closest('[data-favorite-key]');
  if (favoriteButton) {
    event.preventDefault();
    event.stopPropagation();
    toggleFavoriteAppearance(favoriteButton.dataset.favoriteKey);
    return;
  }
  const card = event.target.closest('.appearance-card');
  if (card) applyGalleryImageSelection(card.dataset.key);
});
bind('appearanceGallery', 'keydown', (event) => {
  if (event.key !== 'Enter' && event.key !== ' ') return;
  const favoriteButton = event.target.closest('[data-favorite-key]');
  if (favoriteButton) {
    event.preventDefault();
    event.stopPropagation();
    toggleFavoriteAppearance(favoriteButton.dataset.favoriteKey);
    return;
  }
  const card = event.target.closest('.appearance-card');
  if (!card) return;
  event.preventDefault();
  applyGalleryImageSelection(card.dataset.key);
});
bind('editModeButton', 'click', () => beginWorkflowMode('edit'));
bind('createModeButton', 'click', () => beginWorkflowMode('create'));
bind('queueModeButton', 'click', () => {
  renderQueue();
  setWorkView('queue');
});
bind('startEditButton', 'click', () => beginWorkflowMode('edit'));
bind('startCreateButton', 'click', () => beginWorkflowMode('create'));
bind('startQueueButton', 'click', () => {
  renderQueue();
  setWorkView('queue');
});
for (const button of document.querySelectorAll('.tab-btn')) {
  button.addEventListener('click', () => setWorkTab(button.dataset.tabTarget));
}
for (const button of document.querySelectorAll('.flow-step')) {
  button.addEventListener('click', () => setWorkTab(button.dataset.flowTab));
}
for (const button of document.querySelectorAll('[data-title-filter-prefix]')) {
  button.addEventListener('click', () => applyTitleFilter(button.dataset.titleFilterPrefix, button.dataset.titleFilter));
}
bind('editCombatProfile', 'change', () => syncEquipmentSummary('edit', 'editCombatProfile'));
bind('sourceCombatProfile', 'change', () => {
  for (const id of [
    'sourceDedicatedArmourValue',
    'sourceMeleeDefenceBonus',
    'sourceMissileDefenceBonus',
  ]) {
    $(id).value = '';
  }
  syncEquipmentSummary('source', 'sourceCombatProfile');
});
bind('sourceDedicatedArmourEnabled', 'change', () => {
  const character = characters().find((item) => item.key === $('sourceCombatProfile').value);
  syncDedicatedArmourControls(character);
  renderValidation();
});
for (const id of [
  'sourceDedicatedArmourValue',
  'sourceMeleeDefenceBonus',
  'sourceMissileDefenceBonus',
]) {
  bind(id, 'input', () => {
    const character = characters().find((item) => item.key === $('sourceCombatProfile').value);
    syncDedicatedArmourControls(character);
    renderValidation();
  });
}
bind('editEquipmentSet', 'change', () => syncCeoSetSummary('edit', 'equipment', 'editEquipmentSet'));
bind('sourceEquipmentSet', 'change', () => syncCeoSetSummary('source', 'equipment', 'sourceEquipmentSet'));
bind('editTraitSet', 'change', () => syncCeoSetSummary('edit', 'trait', 'editTraitSet'));
bind('sourceTraitSet', 'change', () => syncCeoSetSummary('source', 'trait', 'sourceTraitSet'));
bind('editAttributeSet', 'change', () => syncAttributeSummary('edit', 'editAttributeSet'));
bind('sourceAttributeSet', 'change', () => syncAttributeSummary('source', 'sourceAttributeSet'));
bind('editUnitProfile', 'change', () => syncUnitSummary('edit', 'editUnitProfile'));
bind('sourceUnitProfile', 'change', () => syncUnitSummary('source', 'sourceUnitProfile'));
bind('sourceBase', 'change', () => {
  const base = characters().find((item) => item.key === $('sourceBase').value);
  if (base) {
    syncWorkflowGender(characterGenderKey(base));
    renderWorkflowGenderButtons();
    applyCreateBaseDefaults(base);
  }
  renderSelectedPreview();
  renderValidation();
});
bind('editSubtype', 'change', () => {
  refreshTitleSelectForElement('edit', '', selectedCharacter());
  renderTitleSummary('edit', resolveTitleChoice($('editTitle').value));
  renderSelectedPreview();
  renderValidation();
});
bind('createSubtype', 'change', () => {
  const base = characters().find((item) => item.key === $('sourceBase').value) || selectedCharacter();
  refreshTitleSelectForElement('source', '', base);
  renderTitleSummary('source', resolveTitleChoice($('sourceTitle').value) || base);
  renderSelectedPreview();
  renderValidation();
});
bind('editSkill', 'change', () => {
  state.activeSkillNode = null;
  renderSkillTreeEditor('edit');
  renderValidation();
});
bind('sourceSkill', 'change', () => {
  state.activeSkillNode = null;
  renderSkillTreeEditor('source');
  renderValidation();
});
bind('sourceTitle', 'change', () => {
  renderTitleSummary('source', resolveTitleChoice($('sourceTitle').value));
  renderValidation();
});
bind('editTitle', 'change', () => {
  renderTitleSummary('edit', resolveTitleChoice($('editTitle').value));
  renderValidation();
});
bind('sourceSpawn', 'change', () => {
  const spawn = characters().find((item) => item.key === $('sourceSpawn').value);
  if (spawn) $('createAgeRange').value = spawn.birthYear ?? birthYearForAgeRange(spawn.spawnAge) ?? '';
  renderValidation();
});
bind('editImageSet', 'change', () => {
  state.selectedAppearanceCardKey = '';
  updateImagePreviews();
  renderAppearanceGallery();
});
bind('sourceImageSet', 'change', () => {
  state.selectedAppearanceCardKey = '';
  updateImagePreviews();
  renderAppearanceGallery();
  renderValidation();
});
bind('editSpawnEvent', 'change', () => {
  updateSpawnFieldLabels('edit');
  renderValidation();
});
bind('sourceSpawnEvent', 'change', () => {
  updateSpawnFieldLabels('create');
  renderValidation();
});
bind('createMinRound', 'input', () => updateSpawnFieldLabels('create'));
bind('stageEditButton', 'click', stageEdit);
bind('stageCreateButton', 'click', stageCreate);
bind('workQueue', 'click', (event) => {
  const editButton = event.target.closest('[data-edit-queue]');
  if (editButton) {
    loadQueueItem(Number(editButton.dataset.editQueue));
    return;
  }
  const deleteButton = event.target.closest('[data-remove-queue]');
  if (deleteButton) {
    removeQueueItem(Number(deleteButton.dataset.removeQueue));
    return;
  }
  const item = event.target.closest('[data-load-queue]');
  if (item) loadQueueItem(Number(item.dataset.loadQueue));
});
bind('workQueue', 'keydown', (event) => {
  if (!['Enter', ' '].includes(event.key)) return;
  const item = event.target.closest('[data-load-queue]');
  if (!item) return;
  event.preventDefault();
  loadQueueItem(Number(item.dataset.loadQueue));
});
document.addEventListener('click', (event) => {
  if (!SKILL_TREE_EDITING_ENABLED && event.target.closest('[data-skill-reset], [data-skill-element-tab], [data-skill-node], [data-skill-candidate]')) {
    event.preventDefault();
    return;
  }
  const reset = event.target.closest('[data-skill-reset]');
  if (reset) {
    const prefix = reset.dataset.skillReset;
    const draft = skillTreeDraft(prefix);
    draft.replacements = {};
    state.activeSkillNode = null;
    renderSkillTreeEditor(prefix);
    renderValidation();
    return;
  }
  const elementTab = event.target.closest('[data-skill-element-tab]');
  if (elementTab) {
    const prefix = elementTab.dataset.skillPrefix;
    state.skillCandidateTabs[prefix] = elementTab.dataset.skillElementTab || 'all';
    skillDiscoveryState(prefix).limit = 40;
    renderSkillTreeEditor(prefix);
    return;
  }
  const node = event.target.closest('[data-skill-node]');
  if (node) {
    state.activeSkillNode = {
      prefix: node.dataset.skillPrefix,
      nodeKey: node.dataset.skillNode,
    };
    const setKey = selectedSkillSetKey(node.dataset.skillPrefix);
    const tree = skillTreeBySet(setKey);
    const selectedNode = dedupeSkillTreeNodes(tree?.nodes || []).find((item) => item.key === node.dataset.skillNode);
    const info = selectedNode ? skillInfo(selectedNode.skillKey) : null;
    // Preserve the user's search and filters when changing the target node.
    renderSkillTreeEditor(node.dataset.skillPrefix);
    return;
  }
  const candidate = event.target.closest('[data-skill-candidate]');
  if (candidate) {
    const prefix = candidate.dataset.skillPrefix;
    const target = candidate.dataset.skillTarget;
    const draft = skillTreeDraft(prefix);
    draft.replacements[target] = candidate.dataset.skillCandidate;
    renderSkillTreeEditor(prefix);
    renderValidation();
  }
});
document.addEventListener('input', (event) => {
  if (!SKILL_TREE_EDITING_ENABLED && event.target.closest('[data-skill-search]')) {
    event.preventDefault();
    return;
  }
  const search = event.target.closest('[data-skill-search]');
  if (!search) return;
  const prefix = search.dataset.skillSearch;
  skillDiscoveryState(prefix).query = search.value;
  skillDiscoveryState(prefix).limit = 40;
  const target = document.querySelector(`[data-skill-candidates="${prefix}"]`);
  if (target) target.innerHTML = renderSkillCandidates(prefix, search.value);
});
bind('loadPackButton', 'click', () => loadPack());
bind('refreshPackButton', 'click', () => loadPack({ forceRefresh: true }));
bind('validateButton', 'click', validateServerRecipe);
bind('buildButton', 'click', buildServerPack);
bind('previewRecipeButton', 'click', previewRecipe);
bind('closeRecipeButton', 'click', () => $('recipeDialog').close());
bind('saveModeSelect', 'change', () => {
  $('outputPackPath').disabled = $('saveModeSelect').value === 'in_place';
  renderValidation();
});
bind('saveDraftButton', 'click', () => {
  state.queue.push({
    kind: 'draft_note',
    type: '초안 저장',
    title: '작업 초안 저장',
    description: '연동 전 UI 흐름 확인용 상태입니다.',
    payload: {
      selectedKey: state.selectedKey,
      mode: state.mode,
    },
  });
  renderQueue();
  renderValidation();
});

let selectedPreviewFrame = 0;
function scheduleSelectedPreview() {
  if (selectedPreviewFrame) return;
  selectedPreviewFrame = window.requestAnimationFrame(() => {
    selectedPreviewFrame = 0;
    renderSelectedPreview();
  });
}

function isEditorPreviewControl(control) {
  if (!control?.closest) return false;
  if (!control.closest('#editPanel, #createPanel')) return false;
  if (control.matches('[data-skill-search], .combo-search')) return false;
  return control.matches('input, select');
}

for (const control of document.querySelectorAll('#editPanel input, #editPanel select, #createPanel input, #createPanel select')) {
  if (!isEditorPreviewControl(control)) continue;
  control.addEventListener('input', scheduleSelectedPreview);
  control.addEventListener('change', () => {
    scheduleSelectedPreview();
    scheduleValidation();
  });
}
bind('referencePackPaths', 'input', scheduleValidation);
bind('referencePackPaths', 'change', scheduleValidation);

function showBootstrapError(error) {
  console.error('[MTU Pack Editor] bootstrap failed', error);
  state.serverMessages = [validationItem('error', '초기화 실패', error?.message || String(error))];
  try {
    renderValidation();
  } catch (renderError) {
    console.error('[MTU Pack Editor] failed to render bootstrap error', renderError);
  }
}

function bootstrapApp() {
  try {
    setWorkView('queue');
    renderQueue();
    renderValidation();
    loadPack();
  } catch (error) {
    showBootstrapError(error);
  }
}

window.addEventListener('beforeunload', persistWorkQueue);
bootstrapApp();
