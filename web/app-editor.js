'use strict';

function fillForms(character) {
  const editGender = characterGenderKey(character);
  syncWorkflowGender(editGender);
  renderWorkflowGenderButtons();
  const createGender = editGender;

  $('editName').value = character.name;
  $('editWeight').value = character.weight;
  $('editMinRound').value = character.minRound;
  $('editMaxRound').value = character.maxRound;
  $('createWeight').value = character.weight;
  $('createMinRound').value = 0;
  $('createMaxRound').value = 999;

  const selectableCharacters = selectableFormCharacters();
  const selectedBase = character;
  const baseCandidates = [selectedBase].filter(Boolean);
  const editTitleFilter = titleFilterForPrefix('edit');
  const sourceTitleFilter = titleFilterForPrefix('source');
  const editTitleCandidates = titleChoicesForPrefix('edit', character);
  const sourceTitleCandidates = titleChoicesForPrefix('source', selectedBase);
  const selectedTitleChoice = sourceTitleCandidates.find((item) => titleChoiceMatchesCharacter(item, selectedBase)) || sourceTitleCandidates.find((item) => titleChoiceMatchesCharacter(item, character)) || sourceTitleCandidates[0];
  const currentTitleChoice = editTitleCandidates.find((item) => titleChoiceMatchesCharacter(item, character)) || editTitleCandidates[0];
  const appearances = selectableImageAppearances();
  const attributeCandidates = attributeSetChoices();
  const traitSetCandidates = traitSetChoices();
  const equipmentSetCandidates = equipmentSetChoices();
  const optionSignature = formOptionsSignature({
    selectableCharacters,
    appearances,
    attributeCandidates,
    traitSetCandidates,
    equipmentSetCandidates,
  });
  if (state.formOptionsSignature !== optionSignature) {
    state.formOptionsSignature = optionSignature;
    fillSelect('editImageSet', appearances.map(appearanceOption));
    fillSelect('sourceImageSet', appearances.map(appearanceOption));
    fillSelect('editSkill', selectableCharacters.map((item) => option(item.key, skillSourceOptionLabel(item), `${item.name} ${item.historicalSkill} ${item.romanceSkill} ${item.key}`)));
    fillSelect('sourceSkill', selectableCharacters.map((item) => option(item.key, skillSourceOptionLabel(item), `${item.name} ${item.historicalSkill} ${item.romanceSkill} ${item.key}`)));
    fillSelect('editTraitSet', traitSetCandidates.map((item) => option(item.key, ceoSetOptionLabel(item), ceoSetOptionSearch(item))));
    fillSelect('sourceTraitSet', traitSetCandidates.map((item) => option(item.key, ceoSetOptionLabel(item), ceoSetOptionSearch(item))));
    fillSelect('editAttributeSet', attributeCandidates.map((item) => option(item.key, attributeOptionLabel(item), `${item.name} ${item.attributeSet} ${item.sourceIdentity || ''}`)));
    fillSelect('sourceAttributeSet', attributeCandidates.map((item) => option(item.key, attributeOptionLabel(item), `${item.name} ${item.attributeSet} ${item.sourceIdentity || ''}`)));
    fillSelect('editEquipmentSet', equipmentSetCandidates.map((item) => option(item.key, ceoSetOptionLabel(item), ceoSetOptionSearch(item))));
    fillSelect('sourceEquipmentSet', equipmentSetCandidates.map((item) => option(item.key, ceoSetOptionLabel(item), ceoSetOptionSearch(item))));
    fillSelect('editCombatProfile', selectableCharacters.map((item) => option(item.key, `${item.name} · ${equipmentBrief(item)}`)));
    fillSelect('sourceCombatProfile', selectableCharacters.map((item) => option(item.key, `${item.name} · ${equipmentBrief(item)}`)));
    fillSelect('editUnitProfile', selectableCharacters.map((item) => option(item.key, `${item.name} · ${displayLabel(item.unitProfile, item.key)}`)));
    fillSelect('sourceUnitProfile', selectableCharacters.map((item) => option(item.key, `${item.name} · ${displayLabel(item.unitProfile, item.key)}`)));
    fillSelect('sourceSpawn', selectableCharacters.map((item) => option(item.key, `${item.name} · ${displayLabel(item.spawnAge, item.key)}`)));
    fillSelect('editSpawnEvent', SPAWN_EVENTS.map((item) => option(item.key, `${item.name} · ${item.note}`)));
    fillSelect('sourceSpawnEvent', SPAWN_EVENTS.map((item) => option(item.key, `${item.name} · ${item.note}`)));
    fillSelect('editSubtype', Object.entries(ELEMENTS).map(([key, item]) => option(item.subtype, `${item.label} ${item.name}`)));
    fillSelect('createSubtype', createSubtypeOptions(createGender));
  }
  syncTitleSelectOptions('edit', editTitleFilter, editTitleCandidates, currentTitleChoice);
  syncTitleSelectOptions('source', sourceTitleFilter, sourceTitleCandidates, selectedTitleChoice);

  setSelectValue('editGender', editGender);
  setSelectValue('createGender', createGender);
  setSelectValue('editImageSet', character.artSet || character.key);
  setSelectValue('sourceImageSet', character.artSet || character.key);
  fillSelect('sourceBase', baseCandidates.map((item) => option(item.key, baseCharacterOptionLabel(item), `${item.name} ${item.titleName} ${item.key}`)));
  setSelectValue('sourceBase', selectedBase.key);
  setSelectValue('editSkill', character.key);
  setSelectValue('sourceSkill', selectedBase.key || character.key);
  setSelectValue('editTitle', titleChoiceValue(currentTitleChoice));
  setSelectValue('sourceTitle', titleChoiceValue(selectedTitleChoice));
  setSelectValue('editTraitSet', CEO_SET_BASE_VALUE);
  setSelectValue('sourceTraitSet', CEO_SET_BASE_VALUE);
  setSelectValue('editAttributeSet', attributeCandidates.find((item) => item.attributeSet === character.attributeSet)?.key || character.key);
  setSelectValue('sourceAttributeSet', attributeCandidates.find((item) => item.attributeSet === selectedBase.attributeSet)?.key || selectedBase.key || character.key);
  setSelectValue('editEquipmentSet', CEO_SET_BASE_VALUE);
  setSelectValue('sourceEquipmentSet', CEO_SET_BASE_VALUE);
  setSelectValue('editCombatProfile', character.key);
  setSelectValue('sourceCombatProfile', selectedBase.key || character.key);
  setSelectValue('editUnitProfile', character.key);
  setSelectValue('sourceUnitProfile', selectedBase.key || character.key);
  setSelectValue('sourceSpawn', selectedBase.key || character.key);
  $('editAgeRange').value = '';
  $('editAgeRange').placeholder = character.birthYear ? `기본 ${character.birthYear}` : '출생년도';
  $('createAgeRange').value = '';
  $('createAgeRange').placeholder = selectedBase.birthYear ? `기본 ${selectedBase.birthYear}` : '출생년도';
  setSelectValue('editSpawnEvent', character.spawnEvent);
  setSelectValue('sourceSpawnEvent', generatedSpawnEventFromRound($('createMinRound').value));
  setSelectValue('editSubtype', elementMeta(character.element).subtype);
  setSelectValue('createSubtype', elementMeta(selectedBase.element || character.element).subtype);
  $('createName').value = `${selectedBase.name || character.name} 파생`;
  renderAllTitleFilterButtons();
  renderTitleSummary('edit', resolveTitleChoice($('editTitle').value) || character);
  renderTitleSummary('source', resolveTitleChoice($('sourceTitle').value) || selectedBase);
  syncCeoSetSummary('edit', 'trait', 'editTraitSet');
  syncCeoSetSummary('source', 'trait', 'sourceTraitSet');
  syncModelLockSummaries(character, selectedBase);
  syncCeoSetSummary('edit', 'equipment', 'editEquipmentSet');
  syncCeoSetSummary('source', 'equipment', 'sourceEquipmentSet');
  syncEquipmentSummary('edit', 'editCombatProfile');
  syncEquipmentSummary('source', 'sourceCombatProfile');
  syncAttributeSummary('edit', 'editAttributeSet');
  syncAttributeSummary('source', 'sourceAttributeSet');
  syncUnitSummary('edit', 'editUnitProfile');
  syncUnitSummary('source', 'sourceUnitProfile');
  updateImagePreviews();
  updateAllSpawnFieldLabels();
  renderSkillTreeEditors();
}

function selectableFormCharacters() {
  const browsable = browsableCharacters();
  return browsable.length ? browsable : selectableFallbackCharacters();
}

function characterSearchText(character) {
  return [
    character?.name,
    character?.titleName,
    character?.key,
    character?.artSet,
    character?.historicalSkill,
    character?.romanceSkill,
    character?.attributeSet,
    character?.unitProfile,
    character?.spawnAge,
  ].filter(Boolean).join(' ');
}

function baseSelectOption(character) {
  return option(character.key, baseCharacterOptionLabel(character), characterSearchText(character));
}

function skillSelectOption(character) {
  return option(
    character.key,
    skillSourceOptionLabel(character),
    `${characterSearchText(character)} ${character?.historicalSkill || ''} ${character?.romanceSkill || ''}`,
  );
}

function combatProfileOption(character) {
  return option(character.key, `${character.name} · ${equipmentBrief(character)}`, characterSearchText(character));
}

function unitProfileOption(character) {
  return option(character.key, `${character.name} · ${displayLabel(character.unitProfile, character.key)}`, characterSearchText(character));
}

function spawnProfileOption(character) {
  return option(character.key, `${character.name} · ${displayLabel(character.spawnAge, character.key)}`, characterSearchText(character));
}

function imageSelectOptionForCharacter(character) {
  return appearanceOption(appearanceByKey(character?.artSet || character?.key));
}

function titleSelectOptionForCharacter(character) {
  return option(titleChoiceValue(character), titleOptionLabel(character), titleSearchText(character));
}

function attributeSelectOptionForCharacter(character) {
  const value = attributeChoiceValueFor(character?.attributeSet || character?.key);
  const choice = resolveAttributeChoice(value) || character;
  return option(value, attributeOptionLabel(choice), `${choice?.name || ''} ${choice?.attributeSet || ''} ${choice?.sourceIdentity || ''}`);
}

function traitSetOption(set) {
  return option(set.key, ceoSetOptionLabel(set), ceoSetOptionSearch(set));
}

function equipmentSetOption(set) {
  return option(set.key, ceoSetOptionLabel(set), ceoSetOptionSearch(set));
}

function setupEditLazySelects(character) {
  setLazySelect('editImageSet', () => selectableImageAppearances().map(appearanceOption), imageSelectOptionForCharacter(character));
  setLazySelect('editSkill', () => selectableFormCharacters().map(skillSelectOption), skillSelectOption(character));
  setLazySelect('editTitle', () => titleChoicesForPrefix('edit', character).map((item) => option(titleChoiceValue(item), titleOptionLabel(item), titleSearchText(item))), titleSelectOptionForCharacter(character));
  setLazySelect('editTraitSet', () => traitSetChoices().map(traitSetOption), traitSetOption(traitSetChoices()[0]));
  setLazySelect('editAttributeSet', () => attributeSetChoices().map((item) => option(item.key, attributeOptionLabel(item), `${item.name} ${item.attributeSet} ${item.sourceIdentity || ''}`)), attributeSelectOptionForCharacter(character));
  setLazySelect('editEquipmentSet', () => equipmentSetChoices().map(equipmentSetOption), equipmentSetOption(equipmentSetChoices()[0]));
  setLazySelect('editCombatProfile', () => selectableFormCharacters().map(combatProfileOption), combatProfileOption(character));
  setLazySelect('editUnitProfile', () => selectableFormCharacters().map(unitProfileOption), unitProfileOption(character));
}

function setupCreateLazySelects(character) {
  setLazySelect('sourceBase', () => selectableFormCharacters().map(baseSelectOption), baseSelectOption(character));
  setLazySelect('sourceImageSet', () => selectableImageAppearances().map(appearanceOption), imageSelectOptionForCharacter(character));
  setLazySelect('sourceSkill', () => selectableFormCharacters().map(skillSelectOption), skillSelectOption(character));
  setLazySelect('sourceTitle', () => titleChoicesForPrefix('source', character).map((item) => option(titleChoiceValue(item), titleOptionLabel(item), titleSearchText(item))), titleSelectOptionForCharacter(character));
  setLazySelect('sourceTraitSet', () => traitSetChoices().map(traitSetOption), traitSetOption(traitSetChoices()[0]));
  setLazySelect('sourceAttributeSet', () => attributeSetChoices().map((item) => option(item.key, attributeOptionLabel(item), `${item.name} ${item.attributeSet} ${item.sourceIdentity || ''}`)), attributeSelectOptionForCharacter(character));
  setLazySelect('sourceEquipmentSet', () => equipmentSetChoices().map(equipmentSetOption), equipmentSetOption(equipmentSetChoices()[0]));
  setLazySelect('sourceCombatProfile', () => selectableFormCharacters().map(combatProfileOption), combatProfileOption(character));
  setLazySelect('sourceUnitProfile', () => selectableFormCharacters().map(unitProfileOption), unitProfileOption(character));
  setLazySelect('sourceSpawn', () => selectableFormCharacters().map(spawnProfileOption), spawnProfileOption(character));
}

function prepareEditWorkflowForms(character, { deferSummaries = false } = {}) {
  const editGender = characterGenderKey(character);
  resetWorkflowDraft('edit', character);
  syncWorkflowGender(editGender);
  renderWorkflowGenderButtons();
  $('editName').value = character.name;
  $('editWeight').value = character.weight;
  $('editMinRound').value = character.minRound;
  $('editMaxRound').value = character.maxRound;
  $('editAgeRange').value = '';
  $('editAgeRange').placeholder = character.birthYear ? `기본 ${character.birthYear}` : '출생년도';
  setupEditLazySelects(character);
  fillSelect('editSpawnEvent', SPAWN_EVENTS.map((item) => option(item.key, `${item.name} · ${item.note}`)));
  fillSelect('editSubtype', Object.entries(ELEMENTS).map(([key, item]) => option(item.subtype, `${item.label} ${item.name}`)));
  setSelectValue('editGender', editGender);
  setSelectValue('editSpawnEvent', character.spawnEvent);
  setSelectValue('editSubtype', elementMeta(character.element).subtype);
  renderTitleFilterButtons('edit');
  if (deferSummaries) return;
  renderTitleSummary('edit', character);
  syncCeoSetSummary('edit', 'trait', 'editTraitSet');
  syncModelLockSummaries(character, characters().find((item) => item.key === $('sourceBase')?.value) || character);
  syncCeoSetSummary('edit', 'equipment', 'editEquipmentSet');
  syncEquipmentSummary('edit', 'editCombatProfile');
  syncAttributeSummary('edit', 'editAttributeSet');
  syncUnitSummary('edit', 'editUnitProfile');
  updateImagePreview('editImagePreview', 'editImageSet', '기존 장수 수정');
  updateSpawnFieldLabels('edit');
  renderSkillTreeEditor('edit');
}

function prepareCreateWorkflowForms(character, { deferSummaries = false } = {}) {
  const createGender = characterGenderKey(character);
  resetWorkflowDraft('source', character);
  syncWorkflowGender(createGender);
  renderWorkflowGenderButtons();
  $('createWeight').value = character.weight;
  $('createMinRound').value = 0;
  $('createMaxRound').value = 999;
  $('createAgeRange').value = '';
  $('createAgeRange').placeholder = character.birthYear ? `기본 ${character.birthYear}` : '출생년도';
  $('createName').value = `${character.name} 파생`;
  setupCreateLazySelects(character);
  fillSelect('sourceSpawnEvent', SPAWN_EVENTS.map((item) => option(item.key, `${item.name} · ${item.note}`)));
  fillSelect('createSubtype', createSubtypeOptions(createGender));
  setSelectValue('createGender', createGender);
  setSelectValue('sourceSpawnEvent', generatedSpawnEventFromRound($('createMinRound').value));
  setSelectValue('createSubtype', elementMeta(character.element).subtype);
  renderTitleFilterButtons('source');
  if (deferSummaries) return;
  renderTitleSummary('source', character);
  syncCeoSetSummary('source', 'trait', 'sourceTraitSet');
  syncModelLockSummaries(selectedCharacter(), character);
  syncCeoSetSummary('source', 'equipment', 'sourceEquipmentSet');
  syncEquipmentSummary('source', 'sourceCombatProfile');
  syncAttributeSummary('source', 'sourceAttributeSet');
  syncUnitSummary('source', 'sourceUnitProfile');
  updateImagePreview('sourceImagePreview', 'sourceImageSet', '신규 장수 생성');
  updateSpawnFieldLabels('create');
  renderSkillTreeEditor('source');
}

function prepareWorkflowForms(character, mode) {
  if (mode === 'create') {
    prepareCreateWorkflowForms(character);
  } else {
    prepareEditWorkflowForms(character);
  }
  renderSelectedPreview();
  renderValidation();
}

function resetWorkflowDraft(prefix, character) {
  state.activeSkillNode = null;
  const setKey = skillSetKeyForEditor(character);
  if (setKey) delete state.skillTreeDrafts[skillDraftKey(prefix, setKey)];
}

function applyCreateBaseDefaults(base) {
  if (!base) return;
  syncWorkflowGender(characterGenderKey(base));
  renderWorkflowGenderButtons();
  $('createName').value = `${base.name} 파생`;
  setSelectValue('createSubtype', elementMeta(base.element).subtype);
  setupCreateLazySelects(base);
  state.selectedAppearanceCardKey = '';
  setSelectValue('sourceImageSet', base.artSet || base.key);
  setSelectValue('sourceTraitSet', CEO_SET_BASE_VALUE);
  setSelectValue('sourceEquipmentSet', CEO_SET_BASE_VALUE);
  $('createAgeRange').value = base.birthYear ?? '';
  syncModelLockSummaries(selectedCharacter(), base);
  renderTitleSummary('source', base);
  syncCeoSetSummary('source', 'trait', 'sourceTraitSet');
  syncAttributeSummary('source', 'sourceAttributeSet');
  syncCeoSetSummary('source', 'equipment', 'sourceEquipmentSet');
  syncEquipmentSummary('source', 'sourceCombatProfile');
  syncUnitSummary('source', 'sourceUnitProfile');
  updateImagePreview('sourceImagePreview', 'sourceImageSet', '신규 장수 생성');
}

function formOptionsSignature(groups) {
  return [
    signatureForOptions(groups.selectableCharacters),
    signatureForOptions(groups.appearances),
    signatureForOptions(groups.attributeCandidates),
    signatureForOptions(groups.traitSetCandidates),
    signatureForOptions(groups.equipmentSetCandidates),
  ].join('|');
}

function syncTitleSelectOptions(prefix, filter, choices, selectedChoice) {
  if (!state.titleOptionsSignatures) state.titleOptionsSignatures = {};
  const signature = [
    prefix,
    filter || 'all',
    titleChoiceValue(selectedChoice),
    signatureForOptions(choices, titleChoiceValue),
  ].join('|');
  if (state.titleOptionsSignatures[prefix] === signature) return;
  state.titleOptionsSignatures[prefix] = signature;
  fillSelect(`${prefix}Title`, choices.map((item) => option(titleChoiceValue(item), titleOptionLabel(item), titleSearchText(item))));
}

function titleSearchText(item) {
  const elements = titleElementsForChoice(item).map((element) => `${element} ${elementMeta(element).label} ${elementMeta(element).name}`);
  return [
    item?.titleName,
    item?.titleOwnerName,
    item?.name,
    item?.titleCeoKey,
    item?.titleKey,
    item?.titleInitialCeoKey,
    item?.titleEffectSummary,
    item?.titleEffectTitle,
    ...elements,
  ].filter(Boolean).join(' ');
}

function refreshTitleSelectForElement(prefix, element, fallbackChoice = null) {
  const selectId = `${prefix}Title`;
  const currentChoice = resolveTitleChoice($(selectId)?.value) || fallbackChoice;
  const choices = titleChoicesForPrefix(prefix, currentChoice, fallbackChoice);
  fillSelect(selectId, choices.map((item) => option(titleChoiceValue(item), titleOptionLabel(item), titleSearchText(item))));
  const currentValue = titleChoiceValue(currentChoice);
  if (currentValue) setSelectValue(selectId, currentValue);
  if (!$(selectId).value && choices[0]) setSelectValue(selectId, titleChoiceValue(choices[0]));
  renderTitleFilterButtons(prefix);
}

function titleChoiceMatchesCharacter(choice, character) {
  if (!choice || !character) return false;
  if (choice.key && character.key && choice.key === character.key) return true;
  const choiceKey = canonicalTitleChoiceKey(choice);
  const characterKey = canonicalTitleChoiceKey(character);
  return Boolean(choiceKey && characterKey && choiceKey === characterKey);
}

function renderTitleFilterButtons(prefix) {
  const activeFilter = titleFilterForPrefix(prefix);
  document.querySelectorAll(`[data-title-filter-prefix="${prefix}"]`).forEach((button) => {
    button.classList.toggle('active', button.dataset.titleFilter === activeFilter);
    button.setAttribute('aria-pressed', String(button.dataset.titleFilter === activeFilter));
  });
}

function renderAllTitleFilterButtons() {
  renderTitleFilterButtons('edit');
  renderTitleFilterButtons('source');
}

function applyTitleFilter(prefix, filter) {
  if (!state.titleFilters) state.titleFilters = {};
  state.titleFilters[prefix] = normalizeTitleStatFilter(filter);
  if (!state.titleOptionsSignatures) state.titleOptionsSignatures = {};
  state.titleOptionsSignatures[prefix] = '';
  const fallback = prefix === 'source'
    ? characters().find((item) => item.key === $('sourceBase')?.value) || selectedCharacter()
    : selectedCharacter();
  refreshTitleSelectForElement(prefix, '', fallback);
  const titleSelect = $(`${prefix}Title`);
  if (titleSelect?._discoveryPanel) {
    titleSelect._discoveryPanel.hidden = false;
    titleSelect._discoveryLimit = 30;
    renderDiscoverySelect(titleSelect);
  }
  renderTitleSummary(prefix, resolveTitleChoice($(`${prefix}Title`)?.value) || fallback);
  renderSelectedPreview();
  renderValidation();
}

function signatureForOptions(items, keyFunc = (item) => item?.key || '') {
  const list = Array.isArray(items) ? items : [];
  const first = keyFunc(list[0] || {}) || '';
  const last = keyFunc(list[list.length - 1] || {}) || '';
  return `${list.length}:${first}:${last}`;
}

function option(value, label, search = '') {
  return { value, label, search };
}

function createSubtypeOptions(gender) {
  const unsupportedGenericFemaleElements = new Set(['fire', 'wood']);
  return Object.entries(ELEMENTS).map(([key, item]) => {
    const warning = gender === 'female' && unsupportedGenericFemaleElements.has(key)
      ? ' · ⚠ 공용 여성 모델 없음'
      : '';
    return option(item.subtype, `${item.label} ${item.name}${warning}`);
  });
}

function syncCreateSubtypeWarning() {
  const warning = $('createSubtypeWarning');
  if (!warning) return;
  const element = elementKeyFromSubtype($('createSubtype')?.value);
  const isUnsupportedFemale = state.workflowGender === 'female' && new Set(['fire', 'wood']).has(element);
  warning.hidden = !isUnsupportedFemale;
  warning.innerHTML = isUnsupportedFemale
    ? `<strong>⚠ ${escapeHtml(elementMeta(element).name)} 여성 모델 주의</strong><span>바닐라에는 이 오행의 공용 여성 3D 모델이 없습니다. 생성은 가능하지만 기준 장수의 고유 모델 및 장비 의존성이 유지될 수 있습니다.</span>`
    : '';
}

function baseCharacterOptionLabel(character) {
  const meta = elementMeta(character?.element);
  return `${sourceLabel(character)} ${character?.name || '-'} · ${genderLabel(characterGenderKey(character))} · ${meta.label} ${meta.name} · ${rosterTitleLabel(character)}`;
}

function skillSourceOptionLabel(character) {
  const historical = displayLabel(character?.historicalSkill, character?.key || '');
  const romance = displayLabel(character?.romanceSkill, character?.key || '');
  const suffix = historical === romance ? historical : `역사 ${historical} / 연희 ${romance}`;
  return `${sourceLabel(character)} ${character?.name || '-'} · ${suffix}`;
}

function modelLockSummaryMarkup(character, prefix) {
  if (!character) return '<p class="empty">기준 장수를 먼저 선택하세요.</p>';
  return `
    <div class="summary-line">
      <strong>${escapeHtml(prefix)} 모델 고정</strong>
      <span>${escapeHtml(character.name || '-')} · ${escapeHtml(genderLabel(characterGenderKey(character)))} · ${escapeHtml(displayLabel(character.modelSetName, character.artSet || character.key))}</span>
    </div>
    <small>모델과 성별은 기준 장수 체인을 유지합니다. 이미지 세트만 자유롭게 교체합니다.</small>
  `;
}

function syncModelLockSummaries(editCharacter, createBase) {
  if ($('editModelLockSummary')) $('editModelLockSummary').innerHTML = modelLockSummaryMarkup(editCharacter, '기존 장수');
  if ($('sourceModelLockSummary')) $('sourceModelLockSummary').innerHTML = modelLockSummaryMarkup(createBase, '신규 기준 장수');
}

function fillSelect(id, options) {
  const select = $(id);
  select._optionLoader = null;
  select._optionsLoaded = true;
  select._allOptions = options;
  select._lastQuery = '';
  renderSelectOptions(select, options, select.value);
  enhanceSearchableSelect(select);
  const input = select.parentNode.querySelector(`[data-search-for="${select.id}"]`);
  renderDiscoverySelect(select);
}

function setLazySelect(id, optionLoader, selectedOption = null) {
  const select = $(id);
  if (!select) return;
  select._optionLoader = optionLoader;
  select._optionsLoaded = false;
  select._allOptions = selectedOption ? [selectedOption] : [];
  select._lastQuery = '';
  renderSelectOptions(select, select._allOptions, selectedOption?.value || select.value);
  enhanceSearchableSelect(select);
  wireLazySelect(select);
  const input = select.parentNode.querySelector(`[data-search-for="${select.id}"]`);
  renderDiscoverySelect(select);
}

function setLazySelectedOption(id, selectedOption) {
  const select = $(id);
  if (!select) return;
  if (typeof select._optionLoader !== 'function') {
    fillSelect(id, selectedOption ? [selectedOption] : []);
    return;
  }
  select._optionsLoaded = false;
  select._allOptions = selectedOption ? [selectedOption] : [];
  select._lastQuery = '';
  renderSelectOptions(select, select._allOptions, selectedOption?.value || select.value);
  const input = select.parentNode.querySelector(`[data-search-for="${select.id}"]`);
  renderDiscoverySelect(select);
}

function ensureSelectOptionsLoaded(select) {
  if (!select || select._optionsLoaded || typeof select._optionLoader !== 'function') {
    return select?._allOptions || [];
  }
  const selectedValue = select.value;
  const selectedOption = (select._allOptions || []).find((item) => String(item.value) === selectedValue);
  const options = select._optionLoader() || [];
  if (selectedOption && !options.some((item) => String(item.value) === selectedValue)) {
    options.unshift(selectedOption);
  }
  select._allOptions = options;
  select._optionsLoaded = true;
  renderSelectOptions(select, options, selectedValue);
  return options;
}

function wireLazySelect(select) {
  if (select.dataset.lazyReady === '1') return;
  const load = () => ensureSelectOptionsLoaded(select);
  select.addEventListener('focus', load);
  select.addEventListener('pointerdown', load);
  select.dataset.lazyReady = '1';
}

function renderSelectOptions(select, options, selectedValue = select.value) {
  options = dedupePickerOptions(select, options, selectedValue);
  const previousValue = String(selectedValue || '');
  const selectedOption = previousValue
    ? (select._allOptions || options).find((item) => String(item.value) === previousValue)
    : null;
  const visibleOptions = options.slice(0, SELECT_RENDER_LIMIT);
  if (selectedOption && !visibleOptions.some((item) => String(item.value) === previousValue)) {
    visibleOptions.unshift(selectedOption);
  }
  const fragment = document.createDocumentFragment();
  const seen = new Set();
  for (const item of visibleOptions) {
    const value = String(item.value ?? '');
    if (seen.has(value)) continue;
    seen.add(value);
    const optionEl = document.createElement('option');
    optionEl.value = value;
    optionEl.textContent = item.label;
    fragment.appendChild(optionEl);
  }
  const hiddenCount = Math.max(0, options.length - visibleOptions.length);
  if (hiddenCount) {
    const notice = document.createElement('option');
    notice.disabled = true;
    notice.value = '';
    notice.textContent = `검색하면 ${hiddenCount}개 더 볼 수 있습니다`;
    fragment.appendChild(notice);
  }
  select.replaceChildren(fragment);
  if (previousValue && selectHasValue(select, previousValue)) {
    select.value = previousValue;
  }
  renderDiscoverySelect(select);
}

function selectHasValue(select, value) {
  const stringValue = String(value ?? '');
  for (const item of select.options) {
    if (item.value === stringValue) return true;
  }
  return false;
}

function setSelectValue(id, value) {
  const select = $(id);
  if (!select) return;
  const stringValue = String(value ?? '');
  if (stringValue && !selectHasValue(select, stringValue) && typeof select._optionLoader === 'function' && !select._optionsLoaded) {
    select._allOptions = [
      option(stringValue, String(stringValue), stringValue),
      ...(select._allOptions || []).filter((item) => String(item.value) !== stringValue),
    ];
    renderSelectOptions(select, select._allOptions, stringValue);
  }
  if (select._allOptions?.length && !selectHasValue(select, stringValue)) {
    const query = String(select._lastQuery || '').trim().toLowerCase();
    const sourceOptions = query
      ? select._allOptions.filter((item) => `${item.label} ${item.value} ${item.search || ''}`.toLowerCase().includes(query))
      : select._allOptions;
    renderSelectOptions(select, sourceOptions, stringValue);
  }
  if (selectHasValue(select, stringValue)) {
    select.value = stringValue;
  }
}

function enhanceSearchableSelect(select) {
  if (!SEARCHABLE_SELECT_IDS.has(select.id) || select.dataset.searchReady === '1') return;
  const input = document.createElement('input');
  input.className = 'select-search';
  input.type = 'search';
  input.placeholder = '검색해서 목록 줄이기';
  input.autocomplete = 'off';
  input.dataset.searchFor = select.id;
  select.parentNode.insertBefore(input, select);
  input.addEventListener('input', () => debounceRender(`select:${select.id}`, () => filterSelectOptions(select), 80));
  input.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      select.focus();
    }
  });
  attachDiscoverySelect(select, input);
  select.dataset.searchReady = '1';
}

function filterSelectOptions(select) {
  ensureSelectOptionsLoaded(select);
  const input = select.parentNode.querySelector(`[data-search-for="${select.id}"]`);
  select._lastQuery = input?.value || '';
  // The native select retains the selection; the expanded list holds only matches.
  renderDiscoverySelect(select);
}

function titleSummaryMarkup(character) {
  if (!character) return '<p class="empty">칭호 정보를 확인할 수 없습니다.</p>';
  const { title, detail } = titleEffectDisplayParts(character);
  const description = String(character.titleDescription || '').trim();
  return `
    ${detail ? `
      <div class="title-effect">
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(detail)}</span>
      </div>
    ` : description ? `
      <div class="title-effect">
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(description)}</span>
      </div>
    ` : `
      <div class="title-effect compact">
        <strong>${escapeHtml(title)}</strong>
        <span>칭호 효과 정보가 아직 정리되지 않았습니다.</span>
      </div>
    `}
  `;
}

function renderTitleSummary(prefix, character) {
  const target = $(`${prefix}TitleSummary`);
  if (target) target.innerHTML = titleSummaryMarkup(character);
}

function imagePreviewMarkup(character, modeLabel) {
  if (!character) return '<p class="empty">이미지 세트를 선택하세요.</p>';
  const portraitLabel = character.portraitPath || '초상화 경로 대기';
  const imagePath = character.portraitImagePath || character.cardImagePath;
  const imageSourcePath = character.portraitImagePath ? character.portraitImageSourcePath : character.cardImageSourcePath;
  const portraitUrl = assetUrl(imagePath, imageSourcePath);
  return `
    <div class="preview-art portrait-art element-${character.element}">
      ${portraitUrl ? `<img src="${escapeHtml(portraitUrl)}" alt="${escapeHtml(displayNameWithDummyMarker(character))} 초상화">` : `<span>${escapeHtml(character.portrait)}</span>`}
      <b>초상화</b>
    </div>
    <div class="preview-copy">
      <strong>${sourceBadgeMarkup(character)} ${escapeHtml(displayNameWithDummyMarker(character))} 이미지 세트</strong>
      <span>${escapeHtml(displayLabel(character.imageSetName, character.artSet || character.key))}</span>
      <small>${escapeHtml(modeLabel)}</small>
      <details class="debug-details inline">
        <summary>세부 정보</summary>
        <small>출처: ${escapeHtml(sourceInfo(character).label)}</small>
        <small>이미지: ${escapeHtml(portraitLabel)}</small>
        <small>art set: ${escapeHtml(character.artSet || '-')}</small>
      </details>
    </div>
  `;
}

function portraitMarkup(character, className) {
  const imagePath = character.portraitImagePath || character.cardImagePath;
  const imageSourcePath = character.portraitImagePath ? character.portraitImageSourcePath : character.cardImageSourcePath;
  const url = assetUrl(imagePath, imageSourcePath);
  const fallback = `<span>${escapeHtml(character.portrait)}</span>`;
  return `
    <div class="${className} element-${character.element}">
      ${url ? `<img src="${escapeHtml(url)}" alt="${escapeHtml(character.name)}">` : fallback}
    </div>
  `;
}

function assetUrl(path, sourcePath = '') {
  if (!path || location.protocol === 'file:') return '';
  const params = new URLSearchParams({
    inputPath: sourcePath || $('inputPackPath').value,
    path,
    v: String(state.assetCacheVersion || state.dataVersion || 0),
  });
  return `/api/asset?${params.toString()}`;
}

document.addEventListener('error', (event) => {
  const target = event.target;
  if (!(target instanceof HTMLImageElement)) return;
  const appearanceCard = target.closest('.appearance-card');
  if (appearanceCard) {
    appearanceCard.hidden = true;
    return;
  }
  const parent = target.parentElement;
  if (!parent?.matches('.mini-portrait, .portrait-image, .preview-art')) return;
  const fallback = document.createElement('span');
  fallback.className = 'portrait-fallback';
  fallback.textContent = (target.alt || '?').trim().slice(0, 1) || '?';
  target.replaceWith(fallback);
}, true);

function updateImagePreview(containerId, selectId, modeLabel) {
  const appearance = appearanceByKey($(selectId).value);
  $(containerId).innerHTML = imagePreviewMarkup(appearance, modeLabel);
}

function updateImagePreviews() {
  updateImagePreview('editImagePreview', 'editImageSet', '기존 장수 수정');
  updateImagePreview('sourceImagePreview', 'sourceImageSet', '신규 장수 생성');
}

function updateSpawnFieldLabels(prefix) {
  const isCreate = prefix === 'create';
  const eventSelect = $(isCreate ? 'sourceSpawnEvent' : 'editSpawnEvent');
  const minLabel = $(`${prefix}MinRoundLabel`);
  const maxLabel = $(`${prefix}MaxRoundLabel`);
  const minNote = $(`${prefix}MinRoundNote`);
  const maxNote = $(`${prefix}MaxRoundNote`);
  if (isCreate) {
    const plan = syncGeneratedSpawnEventField();
    if (minLabel) minLabel.textContent = '등장 턴';
    if (minNote) {
      minNote.textContent = plan.minRound <= 0
        ? '0이면 새 캠페인 시작 시 바로 플레이어 세력에 등록됩니다.'
        : `${plan.minRound}턴부터 플레이어 턴 시작에 1회 합류합니다.`;
    }
    if ($('createMaxRound')) $('createMaxRound').value = 999;
    renderSpawnHelp(prefix);
    return;
  }
  if (!eventSelect || !minLabel || !maxLabel) return;
  const delayed = eventSelect.value === 'delayed_join';
  minLabel.textContent = delayed ? '플레이어 합류 턴' : (isCreate ? '최소 등장 턴' : '최소 라운드');
  maxLabel.textContent = delayed ? '최대 턴(사용 안 함)' : (isCreate ? '최대 등장 턴' : '최대 라운드');
  if (minNote) minNote.textContent = delayed ? '예: 5 입력 시 5턴부터 인간 플레이어 턴 시작에 1회 합류합니다.' : '';
  if (maxNote) maxNote.textContent = delayed ? '이 이벤트는 합류 턴만 사용하고 최대 턴은 무시됩니다.' : '';
  renderSpawnHelp(prefix);
}

function updateAllSpawnFieldLabels() {
  updateSpawnFieldLabels('edit');
  updateSpawnFieldLabels('create');
}

function renderSpawnHelp(prefix) {
  const isCreate = prefix === 'create';
  const eventSelect = $(isCreate ? 'sourceSpawnEvent' : 'editSpawnEvent');
  const target = $(`${prefix}SpawnHelp`);
  if (!target) return;
  const plan = isCreate ? syncGeneratedSpawnEventField() : null;
  if (!isCreate && !eventSelect) return;
  const meta = spawnEventMeta(isCreate ? plan.event : eventSelect.value);
  target.innerHTML = `
    <strong>${escapeHtml(meta.helpTitle || meta.name)}</strong>
    <p>${escapeHtml(meta.helpText || meta.note)}</p>
    <ul>
      ${(meta.fields || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('')}
    </ul>
  `;
}

function setMode(mode, { deferRender = false } = {}) {
  state.mode = mode;
  setWorkView('editor');
  clearReferenceEditWarning();
  for (const button of document.querySelectorAll('.mode-btn')) {
    button.classList.toggle('active', button.dataset.mode === mode);
  }
  $('editPanel').classList.toggle('active', mode === 'edit');
  $('createPanel').classList.toggle('active', mode === 'create');
  if (deferRender) return;
  refreshStageButtons();
  updateAllSpawnFieldLabels();
  renderSelectedPreview();
  renderValidation();
}

function beginWorkflowMode(mode) {
  ensureWorkflowSelection();
  setMode(mode);
  prepareWorkflowForms(selectedCharacter(), mode);
  setWorkTab(`${mode}-basic`);
}

function setWorkView(view) {
  state.workView = view;
  const workPanel = document.querySelector('.work-panel');
  const queueMode = view === 'queue';
  const startMode = view === 'start';
  setPreviewModeLabel(queueMode
    ? '작업 목록 확인'
    : (startMode ? '기준 장수 확인' : (state.mode === 'create' ? '신규 생성 미리보기' : '기존 수정 미리보기')));
  workPanel?.classList.toggle('queue-mode', queueMode);
  workPanel?.classList.toggle('start-mode', startMode);
  $('editPanel')?.classList.toggle('active', !queueMode && !startMode && state.mode === 'edit');
  $('createPanel')?.classList.toggle('active', !queueMode && !startMode && state.mode === 'create');
  const queueButton = $('queueModeButton');
  if (queueButton) queueButton.classList.toggle('active', queueMode);
  if (startMode) {
    for (const button of document.querySelectorAll('.mode-btn')) {
      button.classList.remove('active');
    }
  } else if (!queueMode) {
    for (const button of document.querySelectorAll('.mode-btn')) {
      if (button.dataset.mode === 'queue') button.classList.remove('active');
      if (button.dataset.mode !== 'queue') button.classList.toggle('active', button.dataset.mode === state.mode);
    }
  } else {
    for (const button of document.querySelectorAll('.mode-btn')) {
      if (button.dataset.mode !== 'queue') button.classList.remove('active');
    }
  }
  renderWorkflowStart();
}

function setWorkTab(target) {
  const prefix = target.split('-')[0];
  for (const button of document.querySelectorAll(`.tab-bar[data-tabs-for="${prefix}"] .tab-btn`)) {
    button.classList.toggle('active', button.dataset.tabTarget === target);
  }
  for (const button of document.querySelectorAll(`.editor-flow[data-flow-for="${prefix}"] .flow-step`)) {
    button.classList.toggle('active', button.dataset.flowTab === target);
  }
  for (const section of document.querySelectorAll(`[data-tab-section^="${prefix}-"]`)) {
    section.classList.toggle('active', section.dataset.tabSection === target);
  }
  if (target.endsWith('-appearance')) renderAppearanceGallery();
  renderEditorFlowSummary();
}

function syncEquipmentSummary(prefix, sourceId, { deferValidation = false } = {}) {
  const character = characters().find((item) => item.key === $(sourceId).value);
  if (!character) return;
  $(`${prefix}EquipmentSummary`).innerHTML = equipmentSummaryMarkup(character, prefix);
  if (prefix === 'source') syncDedicatedArmourControls(character);
  if (!deferValidation) renderValidation();
}

function syncDedicatedArmourControls(character) {
  const toggle = $('sourceDedicatedArmourEnabled');
  const bonusInputs = [
    ['sourceDedicatedArmourValue', '방어력'],
    ['sourceMeleeDefenceBonus', '근접 회피'],
    ['sourceMissileDefenceBonus', '원거리 방어 확률'],
  ];
  const statusNode = $('sourceDedicatedArmourStatus');
  if (!toggle || !statusNode) return;
  const resolvedInputs = bonusInputs
    .map(([id, label]) => [$(id), label])
    .filter(([input]) => input);

  const slot = availableDedicatedArmourSlot(character);
  const hasSourceData = Boolean(
    character?.armourCeo
    && character?.armourStatKey
    && characterInitialCeoKey(character)
    && Number.isFinite(Number(character?.baseDefense))
  );
  const available = Boolean(slot && hasSourceData);
  toggle.disabled = !available;
  if (!available) toggle.checked = false;
  for (const [input] of resolvedInputs) {
    input.disabled = !available || !toggle.checked;
    if (input.value === '') input.value = 0;
  }
  if (!hasSourceData || !slot) {
    statusNode.textContent = '선택한 장수의 기존 갑옷과 기본 방어력을 확인할 수 없습니다.';
  } else {
    const summary = resolvedInputs
      .map(([input, label]) => {
        const value = Number(input.value);
        const bonus = Number.isFinite(value) ? value : 0;
        return `${label} ${bonus >= 0 ? '+' : ''}${bonus}`;
      })
      .join(' · ');
    statusNode.textContent = `기존 장비 유지 · 숨김 장수 효과 · ${summary}`;
  }
}

function syncUnitSummary(prefix, sourceId, { deferValidation = false } = {}) {
  const character = characters().find((item) => item.key === $(sourceId).value);
  if (!character) return;
  $(`${prefix}UnitSummary`).innerHTML = unitSummaryMarkup(character, prefix);
  const canEditUnit = Boolean(character.landUnitKey);
  for (const suffix of ['ChargeBonus', 'Morale', 'PrimaryAmmo']) {
    const input = $(`${prefix}${suffix}`);
    if (input) {
      input.disabled = !canEditUnit;
      bindValidationInput(input);
    }
  }
  if (!deferValidation) renderValidation();
}

function syncAttributeSummary(prefix, sourceId, { deferValidation = false } = {}) {
  const character = resolveAttributeChoice($(sourceId).value);
  if (!character) return;
  $(`${prefix}AttributeSummary`).innerHTML = attributeSummaryMarkup(character, prefix);
  for (const [suffix] of ATTRIBUTE_FIELDS) {
    const input = $(`${prefix}Attr${suffix}`);
    bindValidationInput(input);
  }
  if (!deferValidation) renderValidation();
}

function attributeSetChoices() {
  return cachedDerived('attributeSetChoices:grouped', () => {
    const catalog = state.options?.attributeSetCatalog || [];
    if (!catalog.length) return characters();
    const groups = new Map();
    const priority = (item) => item.key.startsWith('3k_main_') ? 0 : 1;
    for (const item of [...catalog].sort((a, b) => priority(a) - priority(b) || a.key.localeCompare(b.key))) {
      if (!item?.key || !Object.keys(item.stats || {}).length || item.key === 'placeholder_attribute_set') continue;
      const groupKey = item.equivalenceKey && item.gameMode ? item.equivalenceKey : item.key;
      if (!groups.has(groupKey)) groups.set(groupKey, []);
      groups.get(groupKey).push(item);
    }
    return [...groups.values()].map((items) => {
      const first = items[0];
      const historical = items.find((item) => item.gameMode === 'historical');
      const romance = items.find((item) => item.gameMode === 'romance');
      const selected = romance || first;
      let name = attributeSetDisplayName(selected.key, selected.label);
      if (name === '능력치') {
        const stats = ATTRIBUTE_FIELDS.map(([, key, label]) => ({label, value: Number(selected.stats[key])}));
        stats.sort((a, b) => b.value - a.value);
        name = new Set(stats.map((stat) => stat.value)).size === 1
          ? '균형 기본 능력치' : `${stats.slice(0, 2).map((stat) => stat.label).join('·')} 중심 능력치`;
      }
      return {
        key: `attribute_set::${selected.key}`,
        name,
        attributeSet: selected.key,
        attributeStats: selected.stats,
        attributeAliases: items.map((item) => item.key),
        details: [
          { gameMode: 'historical', attributeSet: historical?.key || selected.key },
          { gameMode: 'romance', attributeSet: romance?.key || selected.key },
        ],
        sourceTag: selected.sourceTag || '',
        sourceIdentity: selected.sourceTablePath || '',
        referenceSourcePath: selected.referenceSourcePath || '',
      };
    });
  });
}

function resolveAttributeChoice(value) {
  const key = String(value || '');
  const character = characters().find((item) => item.key === key);
  const attributeSetKey = character?.attributeSet || key.replace(/^attribute_set::/, '');
  return attributeSetChoices().find((item) => item.key === key || item.attributeSet === attributeSetKey || item.attributeAliases?.includes(attributeSetKey))
    || character
    || characters().find((item) => item.attributeSet === attributeSetKey)
    || null;
}

function attributeChoiceValueFor(value) {
  return resolveAttributeChoice(value)?.key || String(value || '');
}

function attributeOptionLabel(item) {
  const source = sourceLabel(item);
  const stats = item.attributeStats || {};
  const statText = ATTRIBUTE_FIELDS
    .map(([, key, label]) => `${label} ${nullableNumber(stats[key]) ?? 0}`)
    .join(' · ');
  return `${source} · ${attributeSetDisplayName(item.attributeSet, item.name)}${statText ? ` · ${statText}` : ''}`;
}

function attributeSummaryMarkup(character, prefix) {
  const stats = character.attributeStats || {};
  const rows = ATTRIBUTE_FIELDS.map(([suffix, key, label]) => {
    const value = nullableNumber(stats[key]);
    const displayValue = value ?? 0;
    return `
      <label class="inline-stat">
        <span>${label}</span>
        <input id="${prefix}Attr${suffix}" type="number" value="${escapeHtml(String(displayValue))}">
      </label>
    `;
  }).join('');
  return `
    <div class="group-title">
      <strong>오행 스탯</strong>
      <span>${escapeHtml(attributeSetDisplayName(character.attributeSet, character.name || ''))}</span>
    </div>
    <div class="three-col">${rows}</div>
  `;
}

function attributeSetCloneFrom(prefix, character, slug, index) {
  if (!character?.attributeSet || character.attributeSet === '-') return null;
  const overrides = {};
  const changes = [];
  for (const [suffix, key, label] of ATTRIBUTE_FIELDS) {
    const input = $(`${prefix}Attr${suffix}`);
    if (!input) continue;
    const previousValue = nullableNumber(character.attributeStats?.[key]) ?? 0;
    const value = nullableNumber(input.value);
    if (value === null || value < 0 || value === previousValue) continue;
    overrides[key] = value;
    changes.push({ key, label, value, previousValue });
  }
  if (!changes.length) return null;
  const baseKey = `3k_main_attribute_set_general_hby_${slug}_${index}`;
  const details = detailsByMode(character);
  const modeClones = ['historical', 'romance'].map((mode) => ({
    sourceSetKey: details[mode]?.attributeSet || character.attributeSet,
    newSetKey: `${baseKey}_${mode === 'historical' ? 'records' : 'romance'}`,
    overrides,
    gameMode: mode,
  }));
  return { ...modeClones[1], overrides, changes, modeClones };
}

function attributePatchDescription(clone) {
  if (!clone?.changes?.length) return '';
  return ` · 오행 ${clone.changes.map((patch) => `${patch.label} ${patch.previousValue}→${patch.value}`).join(', ')}`;
}

function unitStatCloneFrom(prefix, character, slug, index, { force = false, armourKey = '' } = {}) {
  return null;
  if (!character?.landUnitKey) return null;
  const fields = [
    ['MeleeAttack', 'melee_attack', character.unitMeleeAttack],
    ['MeleeDefence', 'melee_defence', character.unitMeleeDefence],
    ['ChargeBonus', 'charge_bonus', character.unitChargeBonus],
    ['DismountedMeleeAttack', 'dismounted_melee_attack', character.unitDismountedMeleeAttack],
    ['DismountedChargeBonus', 'dismounted_charge_bonus', character.unitDismountedChargeBonus],
    ['Morale', 'morale', character.unitMorale],
    ['PrimaryAmmo', 'primary_ammo', character.unitPrimaryAmmo],
  ];
  const overrides = {};
  const changes = [];
  for (const [suffix, column, previousValue] of fields) {
    const input = $(`${prefix}${suffix}`);
    if (!input) continue;
    const value = nullableNumber(input.value);
    if (value === null || value < 0 || value === previousValue) continue;
    overrides[column] = value;
    changes.push({ column, value, previousValue });
  }
  if (armourKey) {
    overrides.armour = armourKey;
    changes.push({ column: 'armour', value: armourKey, previousValue: character.armourStatKey || '' });
  }
  if (!force && !changes.length) return null;
  return {
    sourceKey: character.landUnitKey,
    newKey: `hby_land_unit_${slug}_${index}`,
    sourceRetinueKey: retinueKeyForCharacter(character),
    newRetinueKey: `hby_land_unit_${slug}_${index}`,
    overrides,
    changes,
  };
}

function unitPatchDescription(clone) {
  if (!clone?.changes?.length) return '';
  const labels = {
    melee_attack: '근공',
    melee_defence: '근방',
    charge_bonus: '돌격',
    dismounted_melee_attack: '말 내림 근공',
    dismounted_charge_bonus: '말 내림 돌격',
    morale: '사기',
    primary_ammo: '탄약',
    armour: '방어구',
  };
  return ` · 유닛 ${clone.changes.map((patch) => `${labels[patch.column] || patch.column} ${patch.previousValue}→${patch.value}`).join(', ')}`;
}
