'use strict';

function renderRoster({ syncSelection = true, renderSelection = true } = {}) {
  renderWorkflowGenderButtons();
  const previousSelectedKey = state.selectedKey;
  const query = normalizeLookupText($('searchInput').value);
  const list = $('characterList');
  list.innerHTML = '';
  const visibleCharacters = rosterCharactersForCurrentGender();
  const filtered = visibleCharacters.filter((character) => {
    const matchesQuery = !query || String(character.rosterSearchText || '').includes(query);
    return matchesQuery && matchesRosterFilter(character);
  });
  if (syncSelection && !filtered.some((character) => realTemplateKey(character) === state.selectedKey) && filtered.length) {
    state.selectedKey = realTemplateKey(filtered[0]);
  }

  $('rosterCount').textContent = `${filtered.length}명`;
  state.rosterResultCount = filtered.length;
  state.rosterFilteredCharacters = filtered;
  state.rosterRenderedCount = 0;
  if (!filtered.length) {
    list.innerHTML = '<p class="empty">검색 결과가 없습니다.</p>';
    return;
  }

  appendRosterSlice();
  if (renderSelection && previousSelectedKey !== state.selectedKey) {
    renderSelected({ fillEditor: false });
    renderQueue();
    setWorkView('start');
  }
}

function renderRosterCard(character) {
  const meta = elementMeta(character.element);
  const templateKey = realTemplateKey(character);
  const favoriteKey = characterFavoriteKey(character);
  const button = document.createElement('button');
  button.type = 'button';
  button.className = `character-card ${templateKey === state.selectedKey ? 'active' : ''}`;
  button.dataset.characterKey = templateKey;
  button.innerHTML = `
    ${portraitMarkup(character, 'mini-portrait')}
    <div class="card-main">
      <strong>${sourceBadgeMarkup(character)} ${escapeHtml(displayNameWithDummyMarker(character))}</strong>
      <span title="${escapeHtml(rosterTitleTooltip(character))}">${meta.name} · ${escapeHtml(rosterTitleLabel(character))}</span>
    </div>
    <div class="card-actions">
      <span class="roster-element">${meta.label}</span>
      <span class="character-favorite ${isFavoriteCharacter(favoriteKey) ? 'active' : ''}" data-character-favorite="${escapeHtml(favoriteKey)}" role="button" tabindex="0" title="즐겨찾기">
        ${starIconMarkup()}
      </span>
    </div>
  `;
  return button;
}

function appendRosterSlice() {
  const list = $('characterList');
  if (!list) return;
  list.querySelector('.lazy-load-sentinel')?.remove();
  const start = state.rosterRenderedCount;
  const end = Math.min(start + SCROLL_RENDER_STEP, state.rosterFilteredCharacters.length);
  for (const character of state.rosterFilteredCharacters.slice(start, end)) {
    list.appendChild(renderRosterCard(character));
  }
  state.rosterRenderedCount = end;
  state.rosterRenderLimit = end;
  const hiddenCount = Math.max(0, state.rosterFilteredCharacters.length - end);
  list.insertAdjacentHTML('beforeend', renderScrollLoadMarker(hiddenCount));
}

function selectRosterCharacter(templateKey) {
  if (!templateKey) return;
  const previousGender = state.workflowGender;
  state.selectedKey = templateKey;
  const character = characters().find((item) => realTemplateKey(item) === templateKey || item.key === templateKey);
  if (character) {
    syncWorkflowGender(characterGenderKey(character));
  }
  state.editingQueueIndex = null;
  if (previousGender !== state.workflowGender) {
    renderRoster({ syncSelection: false, renderSelection: false });
  } else {
    updateRosterActiveState(templateKey);
    renderWorkflowGenderButtons();
  }
  renderSelected({ fillEditor: false });
  setWorkView('start');
  refreshStageButtons();
  renderValidation();
}

function updateRosterActiveState(templateKey = state.selectedKey) {
  const selected = String(templateKey || '');
  for (const card of document.querySelectorAll('[data-character-key]')) {
    card.classList.toggle('active', card.dataset.characterKey === selected);
  }
}

function renderSelected({ fillEditor = true } = {}) {
  const character = selectedCharacter();
  if (fillEditor) {
    fillForms(character);
  }
  renderWorkflowStart();
  if (fillEditor) {
    renderSelectedPreview();
  } else {
    renderSelectedSummary(character);
  }
}

function renderSelectedSummary(character) {
  const templateKey = realTemplateKey(character) || character.key;
  const meta = elementMeta(character.element);
  $('portraitFrame').className = `portrait-frame element-${character.element}`;
  $('portraitFrame').innerHTML = portraitMarkup(character, 'portrait-image');
  $('selectedName').textContent = character.name;
  $('selectedKey').textContent = [
    character.isKoreaAddon ? character.koreaFactionLabel : '',
    character.retinue,
    character.source === 'reference' ? '참조 장수' : '',
  ].filter(Boolean).join(' · ') || '선택한 장수';
  $('elementBadge').className = `element-badge element-${character.element}`;
  $('elementBadge').textContent = `${meta.label} ${meta.name}`;
  $('currentImageSet').textContent = displayLabel(character.imageSetName, character.artSet || character.key);
  $('currentModelSet').textContent = displayLabel(character.modelSetName, character.artSet || character.key);
  $('currentAttributeSet').textContent = attributeSetDisplayName(character.attributeSet);
  $('currentCombatProfile').textContent = combatPair(character);
  $('currentUnitProfile').textContent = character.unitProfile;
  $('currentHistSkill').textContent = character.historicalSkill;
  $('currentRomanceSkill').textContent = character.romanceSkill;
  $('currentSpawn').textContent = `${character.minRound}~${character.maxRound} 라운드 · 가중치 ${character.weight}`;
  $('currentSpawnEvent').textContent = spawnEventMeta(character.spawnEvent).name;

  $('selectedChips').innerHTML = `
    ${character.isKoreaAddon ? `<span>${escapeHtml(character.koreaFactionLabel)} ${character.koreaRole === 'leader' ? '지도자' : character.koreaRole === 'event' ? '이벤트 장수' : '장수'}</span>` : ''}
    <span>${escapeHtml(character.retinue)}</span>
    <span>${escapeHtml(character.spawnAge)}</span>
  `;
}

function baseLockCardMarkup(character, label = '기준 장수') {
  if (!character) {
    return `
      <div class="empty-portrait">-</div>
      <div class="base-lock-copy">
        <b>${escapeHtml(label)}</b>
        <span>선택된 장수가 없습니다.</span>
      </div>
    `;
  }
  const meta = elementMeta(character.element);
  return `
    ${portraitMarkup(character, 'mini-portrait')}
    <div class="base-lock-copy">
      <small>${escapeHtml(label)}</small>
      <b>${escapeHtml(character.name || '-')}</b>
      <span>${meta.label} ${meta.name} · ${genderLabel(characterGenderKey(character))} · ${escapeHtml(rosterTitleLabel(character))}</span>
      <small>${escapeHtml(displayLabel(character.retinue, realTemplateKey(character) || character.key))}</small>
    </div>
  `;
}

function renderWorkflowStart() {
  const selected = selectedCharacter();
  const startCard = $('workflowBaseCard');
  if (startCard) startCard.innerHTML = baseLockCardMarkup(selected, '현재 기준 장수');
  const createCard = $('createBaseSummary');
  if (createCard) createCard.innerHTML = baseLockCardMarkup(selected, '신규 생성 기준');
}

function renderSelectedPreview() {
  const selected = selectedCharacter();
  if (!selected) return;
  setPreviewModeLabel(state.workView === 'queue'
    ? '작업 목록 확인'
    : (state.mode === 'create' ? '신규 생성 미리보기' : '기존 수정 미리보기'));
  const formBase = state.mode === 'create'
    ? (characters().find((item) => item.key === $('sourceBase')?.value) || selected)
    : selected;
  const prefix = state.mode === 'create' ? 'source' : 'edit';
  const nameInput = state.mode === 'create' ? $('createName') : $('editName');
  const subtypeInput = state.mode === 'create' ? $('createSubtype') : $('editSubtype');
  const imageSet = appearanceByKey($(state.mode === 'create' ? 'sourceImageSet' : 'editImageSet')?.value);
  const titleSource = resolveTitleChoice($(`${prefix}Title`)?.value);
  const attribute = resolveAttributeChoice($(`${prefix}AttributeSet`)?.value);
  const combat = characters().find((item) => item.key === $(`${prefix}CombatProfile`)?.value) || formBase;
  const unit = formBase;
  const skillSource = characters().find((item) => item.key === $(state.mode === 'create' ? 'sourceSkill' : 'editSkill')?.value) || formBase;
  const minRound = $(state.mode === 'create' ? 'createMinRound' : 'editMinRound')?.value;
  const maxRound = $(state.mode === 'create' ? 'createMaxRound' : 'editMaxRound')?.value;
  const weight = $(state.mode === 'create' ? 'createWeight' : 'editWeight')?.value;
  const birthYear = $(state.mode === 'create' ? 'createAgeRange' : 'editAgeRange')?.value;
  const rawSpawnEvent = state.mode === 'create'
    ? generatedSpawnEventFromRound(minRound)
    : $('editSpawnEvent')?.value;
  const spawnPlan = state.mode === 'create'
    ? generatedSpawnPlan({ minRound, event: rawSpawnEvent })
    : templateSpawnPlan({ minRound, event: rawSpawnEvent });
  const spawnEvent = spawnEventMeta(spawnPlan.event);
  const element = elementFromSubtype(subtypeInput?.value || formBase.subtype || formBase.element);
  const preview = {
    ...formBase,
    ...(imageSet || {}),
    isMale: formBase.isMale,
    templateRow: formBase.templateRow,
    name: nameInput?.value || formBase.name,
    element,
    retinue: unit?.retinue || formBase.retinue,
    imageSetName: imageSet?.imageSetName || imageSet?.name || formBase.imageSetName,
    modelSetName: formBase.modelSetName,
    titleName: titleSource?.titleName || formBase.titleName,
    titleOwnerName: titleSource?.titleOwnerName || titleSource?.name || formBase.titleOwnerName,
    titleDescription: titleSource?.titleDescription || formBase.titleDescription,
    titleKey: titleSource?.titleKey || formBase.titleKey,
    titleInitialCeoKey: titleSource?.titleInitialCeoKey || formBase.titleInitialCeoKey,
    attributeSet: attribute?.attributeSet || formBase.attributeSet,
    unitProfile: unit?.unitProfile || formBase.unitProfile,
    historicalSkill: skillSource?.historicalSkill || skillSource?.name || formBase.historicalSkill,
    romanceSkill: skillSource?.romanceSkill || skillSource?.historicalSkill || skillSource?.name || formBase.romanceSkill,
    minRound: minRound === '' ? formBase.minRound : spawnPlan.minRound,
    maxRound: maxRound === '' ? formBase.maxRound : maxRound,
    weight: weight === '' ? formBase.weight : weight,
    birthYear: birthYear === '' ? formBase.birthYear : birthYear,
    spawnEvent: spawnPlan.event,
  };

  renderSelectedSummary(preview);
  $('currentCombatProfile').textContent = combatPair(combat);
  $('currentSpawn').textContent = `${preview.minRound}~${preview.maxRound} 라운드 · 가중치 ${preview.weight}`;
  $('currentSpawnEvent').textContent = spawnEvent.name;
  if (birthYear !== '' && birthYear !== undefined) {
    const chips = $('selectedChips');
    const birthChip = `<span>출생년도 ${escapeHtml(birthYear)}</span>`;
    if (!chips.innerHTML.includes('출생년도')) chips.innerHTML += birthChip;
  }
  renderEditorFlowSummary();
}

function setFlowText(id, value) {
  const node = $(id);
  if (node) node.textContent = value || '-';
}

function setPreviewModeLabel(label) {
  const node = $('previewModeLabel');
  if (node) node.textContent = label;
}

function renderEditorFlowSummary() {
  const selected = selectedCharacter();
  if (!selected) return;
  const createBase = characters().find((item) => item.key === $('sourceBase')?.value) || selected;
  const editImage = appearanceByKey($('editImageSet')?.value);
  const createImage = appearanceByKey($('sourceImageSet')?.value);
  const editCombat = characters().find((item) => item.key === $('editCombatProfile')?.value) || selected;
  const createCombat = characters().find((item) => item.key === $('sourceCombatProfile')?.value) || createBase;
  const editSkill = characters().find((item) => item.key === $('editSkill')?.value) || selected;
  const createSkill = characters().find((item) => item.key === $('sourceSkill')?.value) || createBase;
  const editSpawnEvent = spawnEventMeta($('editSpawnEvent')?.value);
  const createSpawnPlan = generatedSpawnPlan({ minRound: $('createMinRound')?.value });
  setFlowText('editFlowTarget', `${genderLabel(characterGenderKey(selected))} · ${selected.name || '-'}`);
  setFlowText('editFlowImage', displayLabel(editImage?.imageSetName || editImage?.name, editImage?.artSet || editImage?.key));
  setFlowText('editFlowGear', equipmentBrief(editCombat));
  setFlowText('editFlowSpawn', editSpawnEvent.name);
  setFlowText('editFlowSkill', editSkill?.name || editSkill?.historicalSkill || '-');
  setFlowText('createFlowTarget', `${genderLabel(characterGenderKey(createBase))} · ${createBase.name || '-'}`);
  setFlowText('createFlowImage', displayLabel(createImage?.imageSetName || createImage?.name, createImage?.artSet || createImage?.key));
  setFlowText('createFlowGear', equipmentBrief(createCombat));
  setFlowText('createFlowSpawn', createSpawnPlan.minRound <= 0 ? '캠페인 시작' : `${createSpawnPlan.minRound}턴 등장`);
  setFlowText('createFlowSkill', createSkill?.name || createSkill?.historicalSkill || '-');
}

function renderAppearanceGallery() {
  const galleryCharacters = appearanceGalleryCharacters();
  const selectedCardKey = currentGallerySelectionKey(galleryCharacters);
  state.appearanceGalleryResultCount = galleryCharacters.length;
  const { visible, hiddenCount } = cappedList(galleryCharacters, state.appearanceGalleryRenderLimit);
  $('appearanceGallery').innerHTML = visible.map((character) => `
    <button class="appearance-card ${galleryCardKey(character) === selectedCardKey ? 'active' : ''}" data-key="${escapeHtml(galleryCardKey(character))}" type="button">
      <span class="favorite-toggle ${isFavoriteAppearance(character) ? 'active' : ''}" data-favorite-key="${escapeHtml(appearanceFavoriteKey(character))}" role="button" tabindex="0" title="즐겨찾기">
        ${starIconMarkup()}
      </span>
      ${portraitMarkup(character, 'mini-portrait')}
      <strong>${sourceBadgeMarkup(character)} ${escapeHtml(displayNameWithDummyMarker(character))}</strong>
      <span>이미지: ${escapeHtml(displayLabel(character.imageSetName, character.artSet || character.key))}</span>
    </button>
  `).join('') || '<p class="empty">검색 결과가 없습니다.</p>';
  $('appearanceGallery').insertAdjacentHTML('beforeend', renderScrollLoadMarker(hiddenCount));
}

function starIconMarkup() {
  return '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.77.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z"/></svg>';
}
