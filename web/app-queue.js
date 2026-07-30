'use strict';

function currentQueueEditKind() {
  const item = state.queue[state.editingQueueIndex];
  if (!item) return null;
  return item.kind;
}

function nextQueueWorkNumber() {
  return state.queue.reduce((maxValue, item) => {
    const value = Number(item?.payload?.workNumber);
    return Number.isFinite(value) && value > maxValue ? value : maxValue;
  }, 0) + 1;
}

function queueItemNumberFor(kind) {
  const item = state.queue[state.editingQueueIndex];
  if (item?.kind === kind) {
    const value = Number(item?.payload?.workNumber);
    if (Number.isFinite(value) && value > 0) return value;
  }
  return nextQueueWorkNumber();
}

function queueWorkNumber(item, index) {
  const value = Number(item?.payload?.workNumber);
  return Number.isFinite(value) && value > 0 ? value : index + 1;
}

function queueWorkSlug(item, index, fallback) {
  const fixed = item?.payload?.workSlug;
  if (fixed) return fixed;
  return slugify(`${fallback || item?.kind || 'work'}_${queueWorkNumber(item, index)}`);
}

function ceoSetDescription(kind, selection) {
  return selection?.label || ceoSetBaseLabel(kind);
}

function combatAdjustmentDescription(adjustment) {
  if (!adjustment) return '';
  const value = Number(adjustment.armourBonus || 0);
  return `방어력 ${value >= 0 ? '+' : ''}${value}`;
}

function commitQueueItem(item) {
  const editingKind = currentQueueEditKind();
  if (editingKind === item.kind) {
    state.queue[state.editingQueueIndex] = item;
  } else {
    state.queue.push(item);
  }
  clearEditorDraftState();
  renderQueue();
  setWorkView('queue');
  refreshStageButtons();
  renderValidation();
}

function syncQueuedDedicatedArmourFromEditor() {
  const toggle = $('sourceDedicatedArmourEnabled');
  const combatKey = $('sourceCombatProfile')?.value || '';
  const baseKey = $('sourceBase')?.value || '';
  if (!toggle || !combatKey) return;

  const cloneIndexes = state.queue
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => item?.kind === 'clone_character');
  let targetIndex = (
    state.editingQueueIndex !== null
    && state.queue[state.editingQueueIndex]?.kind === 'clone_character'
  )
    ? state.editingQueueIndex
    : null;

  if (targetIndex === null) {
    const exactMatches = cloneIndexes.filter(({ item }) => (
      item?.payload?.sourceKeys?.combatProfile === combatKey
      && (!baseKey || item?.payload?.sourceKeys?.base === baseKey)
    ));
    if (exactMatches.length === 1) {
      targetIndex = exactMatches[0].index;
    } else if (cloneIndexes.length === 1) {
      targetIndex = cloneIndexes[0].index;
    }
  }

  if (targetIndex === null) {
    if (toggle.checked) {
      throw new Error(
        '방어력 보정값을 반영할 신규 장수 작업을 특정할 수 없습니다. '
        + '작업 목록에서 대상 장수를 연 뒤 다시 저장해주세요.',
      );
    }
    return;
  }

  const combat = characters().find((item) => item.key === combatKey);
  const adjustment = toggle.checked ? dedicatedArmourSelection(combat) : null;
  if (toggle.checked && !adjustment) {
    throw new Error('전투 보정값은 각각 -500~500의 정수로 입력해주세요.');
  }
  state.queue[targetIndex].payload.dedicatedArmour = adjustment;
  persistWorkQueue();
}

function clearEditorDraftState() {
  state.editingQueueIndex = null;
  state.activeSkillNode = null;
  state.skillCandidateTabs = {};
  state.skillTreeDrafts = {};
  state.formOptionsSignature = '';
  state.titleOptionsSignatures = {};
  for (const id of [
    'editName',
    'createName',
    'editWeight',
    'createWeight',
    'editAgeRange',
    'createAgeRange',
    'editMinRound',
    'editMaxRound',
    'createMinRound',
    'createMaxRound',
  ]) {
    const node = $(id);
    if (node) node.value = '';
  }
}

function refreshStageButtons() {
  const editingKind = currentQueueEditKind();
  $('stageEditButton').textContent = editingKind === 'patch_character' ? '선택 작업 수정 반영' : '수정 작업에 추가';
  $('stageCreateButton').textContent = editingKind === 'clone_character' ? '선택 작업 수정 반영' : '신규 생성 작업에 추가';
}

function stageEdit() {
  const character = selectedCharacter();
  clearReferenceEditWarning();
  const targetTemplateKey = realTemplateKey(character);
  if (!targetTemplateKey) {
    state.serverMessages = [validationItem('error', '기존 장수 선택 오류', '선택한 항목에 실제 character_generation_templates key가 없습니다. 이미지 후보는 중앙 이미지 패널에서만 선택하세요.')];
    renderValidation();
    return;
  }
  const imageSet = appearanceByKey($('editImageSet').value);
  const skill = characters().find((item) => item.key === $('editSkill').value);
  const titleSource = resolveTitleChoice($('editTitle').value);
  const attribute = resolveAttributeChoice($('editAttributeSet').value);
  const combat = characters().find((item) => item.key === $('editCombatProfile').value);
  const traitSet = ceoSetSelection('trait', $('editTraitSet').value);
  const equipmentSet = ceoSetSelection('equipment', $('editEquipmentSet').value);
  const unit = characters().find((item) => item.key === $('editUnitProfile').value) || character;
  const spawnEvent = spawnEventMeta($('editSpawnEvent').value);
  const itemNumber = queueItemNumberFor('patch_character');
  const editSlug = slugify(`${targetTemplateKey}_${itemNumber}`);
  const attributeSetClone = attributeSetCloneFrom('edit', attribute, editSlug, itemNumber);
  const editBirthYear = birthYearFromInput('editAgeRange');
  if (rejectInvalidBirthYear(editBirthYear)) return;
  const editAgeRange = ageRangePatch(character.spawnAge, editBirthYear, editSlug, itemNumber);
  const unitStatClone = unitStatCloneFrom('edit', unit, editSlug, itemNumber);
  const payload = {
    targetKey: targetTemplateKey,
    displayName: $('editName').value.trim(),
    imageSetKey: imageSet?.key,
    targetImageToken: imageTokenFromAppearance(appearanceFromCharacter(character)),
    titleSourceKey: titleChoiceValue(titleSource),
    attributeSetSourceKey: attribute?.key,
    attributeSetClone,
    traitSet,
    combatProfileSourceKey: combat?.key,
    equipmentSet,
    unitProfileSourceKey: unit?.key,
    unitStatClone,
    subtype: $('editSubtype').value,
    spawn: {
      ageRange: editAgeRange?.newKey || character.spawnAge,
      birthYear: editBirthYear,
      weight: Number($('editWeight').value),
      minRound: Number($('editMinRound').value),
      maxRound: Number($('editMaxRound').value),
      event: $('editSpawnEvent').value,
    },
    ageRangeClone: editAgeRange?.changed ? editAgeRange : null,
    skillSourceKey: skill?.key,
    skillTree: skillTreeSnapshot('edit'),
    workNumber: itemNumber,
    workSlug: editSlug,
  };
  commitQueueItem({
    kind: 'patch_character',
    type: '기존 수정',
    title: `${character.name} 수정`,
    description: `${$('editName').value} · 칭호 ${titleSource?.titleName || titleSource?.name || '-'} · 이미지 ${imageSet?.name || '-'} · 모델 고정(${character.name}) · 트레잇 ${ceoSetDescription('trait', traitSet)} · 능력치 ${attribute?.name || '-'}${attributePatchDescription(attributeSetClone)} · 장비 ${ceoSetDescription('equipment', equipmentSet)} · 장비 수치 참조(${equipmentBrief(combat)}) · 병종 ${unit?.name || '-'}${unitStatClone ? ` · 병종 수치 ${unitStatClone.changes.map((change) => `${change.column} ${change.previousValue}→${change.value}`).join(', ')}` : ''} · 등장 이벤트 ${spawnEvent.name} · 스킬셋 ${skill?.name || '-'}`,
    payload,
  });
}

function stageCreate() {
  clearReferenceEditWarning();
  const imageSet = appearanceByKey($('sourceImageSet').value);
  const selectedBase = characters().find((item) => item.key === $('sourceBase').value);
  const appearanceBase = characterByAppearanceKey(imageSet?.key || $('sourceImageSet').value);
  const base = selectedBase || appearanceBase;
  if (!base) {
    state.serverMessages = [validationItem('error', '신규 생성 준비 실패', '새 장수를 만들 기본 템플릿을 자동 선택하지 못했습니다. pack을 다시 읽어주세요.')];
    renderValidation();
    return;
  }
  syncWorkflowGender(characterGenderKey(base));
  const skill = characters().find((item) => item.key === $('sourceSkill').value);
  const titleSource = resolveTitleChoice($('sourceTitle').value);
  const attribute = resolveAttributeChoice($('sourceAttributeSet').value);
  const combat = characters().find((item) => item.key === $('sourceCombatProfile').value);
  const traitSet = ceoSetSelection('trait', $('sourceTraitSet').value);
  const equipmentSet = ceoSetSelection('equipment', $('sourceEquipmentSet').value);
  const unit = characters().find((item) => item.key === $('sourceUnitProfile').value) || base;
  const spawn = characters().find((item) => item.key === $('sourceSpawn').value);
  const spawnPlan = generatedSpawnPlan({ minRound: $('createMinRound').value });
  const spawnEvent = spawnEventMeta(spawnPlan.event);
  const itemNumber = queueItemNumberFor('clone_character');
  const createSlug = slugify(`${base?.key || $('createName').value.trim() || 'new'}_${itemNumber}`);
  const attributeSetClone = attributeSetCloneFrom('source', attribute, createSlug, itemNumber);
  const spawnAgeSourceKey = spawn?.spawnAge || base?.spawnAge || base?.templateRow?.spawn_age_range;
  const createBirthYear = birthYearFromInput('createAgeRange');
  if (rejectInvalidBirthYear(createBirthYear)) return;
  const createAgeRange = ageRangePatch(spawnAgeSourceKey, createBirthYear, createSlug, itemNumber);
  const dedicatedArmour = dedicatedArmourSelection(combat);
  if ($('sourceDedicatedArmourEnabled').checked && !dedicatedArmour) {
    state.serverMessages = [validationItem(
      'error',
      '전투 보정 설정 실패',
      '기준 갑옷 연결과 각 보정치(-500~500 정수)를 확인해주세요.',
    )];
    renderValidation();
    return;
  }
  const unitStatClone = null;
  const payload = {
    newName: $('createName').value.trim(),
    sourceKeys: {
      base: base?.key,
      imageSet: imageSet?.key,
      skill: skill?.key,
      title: titleChoiceValue(titleSource),
      traitSet: traitSet?.setKey || CEO_SET_BASE_VALUE,
      attributeSet: attribute?.key,
      combatProfile: combat?.key,
      equipmentSet: equipmentSet?.setKey || CEO_SET_BASE_VALUE,
      unitProfile: unit?.key,
      spawn: spawn?.key,
    },
    subtype: $('createSubtype').value,
    traitSet,
    attributeSetClone,
    equipmentSet,
    defaultEquipmentCeos: defaultCharacterEquipmentCeos(combat, equipmentSet),
    dedicatedArmour,
    unitStatClone,
    spawn: {
      ageRange: createAgeRange?.newKey || spawnAgeSourceKey,
      birthYear: createBirthYear,
      weight: Number($('createWeight').value),
      minRound: spawnPlan.minRound,
      maxRound: 999,
      event: spawnPlan.event,
    },
    ageRangeClone: createAgeRange?.changed ? createAgeRange : null,
    skillTree: skillTreeSnapshot('source'),
    workNumber: itemNumber,
    workSlug: createSlug,
  };
  commitQueueItem({
    kind: 'clone_character',
    type: '신규 생성',
    title: `${$('createName').value || '새 장수'} 생성`,
    description: `기본 ${base?.name || '-'} · 원본 성별 ${genderLabel(characterGenderKey(base))} · 칭호 ${titleSource?.titleName || titleSource?.name || '-'} · 트레잇 ${ceoSetDescription('trait', traitSet)} · 이미지 ${imageSet?.name || '-'} · 모델 고정(${base?.name || '-'}) · 능력치 ${attribute?.name || '-'}${attributePatchDescription(attributeSetClone)} · 장비 ${ceoSetDescription('equipment', equipmentSet)} · 장비 수치 참조(${equipmentBrief(combat)})${dedicatedArmour ? ` · 기존 장비 유지 · ${combatAdjustmentDescription(dedicatedArmour)}` : ''} · 병종 ${unit?.name || '-'} · 스킬셋 ${skill?.name || '-'} · 등장 ${spawn?.name || '-'} · 이벤트 ${spawnEvent.name}`,
    payload,
  });
}

function renderQueue() {
  persistWorkQueue();
  $('queueCount').textContent = `${state.queue.length}개`;
  if ($('queueModeButton')) $('queueModeButton').textContent = `작업 목록 ${state.queue.length ? state.queue.length : ''}`.trim();
  $('workQueue').innerHTML = state.queue.length
    ? state.queue.map((item, index) => `
      <article class="queue-item ${queueKindClass(item)} ${index === state.editingQueueIndex ? 'active' : ''}" data-load-queue="${index}" tabindex="0" role="button" aria-label="작업 불러오기">
        ${queueItemPortraitMarkup(item)}
        <div class="queue-main">
          <div class="queue-item-head">
            <b>${index + 1}. ${escapeHtml(item.type)}${index === state.editingQueueIndex ? ' · 수정 중' : ''}</b>
            <span class="queue-actions">
              <button class="queue-edit-btn" type="button" data-edit-queue="${index}" aria-label="작업 수정">수정</button>
              <button class="queue-delete-btn" type="button" data-remove-queue="${index}" aria-label="작업 삭제">삭제</button>
            </span>
          </div>
          <strong>${escapeHtml(item.title)}</strong>
          <span>${escapeHtml(queueItemShortDescription(item))}</span>
        </div>
      </article>
    `).join('')
    : '<p class="empty">아직 추가된 작업이 없습니다.</p>';
}

function queuePreviewCharacter(item) {
  const payload = item?.payload || {};
  if (item?.kind === 'patch_character') {
    const base = characters().find((character) => realTemplateKey(character) === payload.targetKey || character.key === payload.targetKey);
    const imageSet = appearanceByKey(payload.imageSetKey);
    return base ? {
      ...base,
      ...(imageSet || {}),
      isMale: base.isMale,
      templateRow: base.templateRow,
      name: payload.displayName || base.name,
      element: elementFromSubtype(payload.subtype || base.subtype || base.element),
    } : imageSet;
  }
  if (item?.kind === 'clone_character') {
    const base = characters().find((character) => character.key === payload.sourceKeys?.base);
    const imageSet = appearanceByKey(payload.sourceKeys?.imageSet);
    return base ? {
      ...base,
      ...(imageSet || {}),
      isMale: base.isMale,
      templateRow: base.templateRow,
      name: payload.newName || base.name,
      element: elementFromSubtype(payload.subtype || base.subtype || base.element),
    } : imageSet;
  }
  return null;
}

function queueItemPortraitMarkup(item) {
  const character = queuePreviewCharacter(item);
  if (!character) return '<div class="queue-portrait empty-portrait">-</div>';
  return `<div class="queue-portrait element-${escapeHtml(character.element || 'wood')}">${portraitMarkup(character, 'mini-portrait')}</div>`;
}

function queueItemShortDescription(item) {
  const payload = item?.payload || {};
  const character = queuePreviewCharacter(item);
  const element = elementMeta(character?.element).label;
  if (item?.kind === 'patch_character') {
    const imageSet = appearanceByKey(payload.imageSetKey);
    const skill = characters().find((candidate) => candidate.key === payload.skillSourceKey);
    return `${character?.name || '-'} · ${element} · 이미지 ${imageSet?.name || '-'} · 스킬 ${skill?.name || '-'}`;
  }
  if (item?.kind === 'clone_character') {
    const base = characters().find((candidate) => candidate.key === payload.sourceKeys?.base);
    const imageSet = appearanceByKey(payload.sourceKeys?.imageSet);
    const title = resolveTitleChoice(payload.sourceKeys?.title);
    return `기준 ${base?.name || '-'} · ${element} · 칭호 ${title?.titleName || title?.name || '-'} · 이미지 ${imageSet?.name || '-'}`;
  }
  return item?.description || '';
}

function queueKindClass(item) {
  if (item?.kind === 'clone_character') return 'queue-create';
  if (item?.kind === 'patch_character') return 'queue-patch';
  return 'queue-note';
}

function removeQueueItem(index) {
  if (index < 0 || index >= state.queue.length) return;
  state.queue.splice(index, 1);
  if (state.editingQueueIndex === index) {
    state.editingQueueIndex = null;
  } else if (state.editingQueueIndex > index) {
    state.editingQueueIndex -= 1;
  }
  renderQueue();
  refreshStageButtons();
  renderValidation();
}

function loadQueueItem(index) {
  const item = state.queue[index];
  if (!item?.payload) return;
  state.editingQueueIndex = index;
  if (item.kind === 'patch_character') {
    loadPatchQueueItem(item);
  } else if (item.kind === 'clone_character') {
    loadCloneQueueItem(item);
  }
  renderQueue();
  setWorkView('editor');
  refreshStageButtons();
  renderSelectedPreview();
  renderValidation();
}

function loadPatchQueueItem(item) {
  const payload = item.payload;
  if (payload.targetKey) {
    state.selectedKey = payload.targetKey;
    renderRoster({ syncSelection: false, renderSelection: false });
    fillForms(selectedCharacter());
  }
  setMode('edit');
  $('editName').value = payload.displayName || $('editName').value;
  setSelectValue('editImageSet', payload.imageSetKey);
  setSelectValue('editSubtype', payload.subtype);
  refreshTitleSelectForElement('edit', '', selectedCharacter());
  setSelectValue('editTitle', payload.titleSourceKey);
  renderTitleSummary('edit', resolveTitleChoice($('editTitle').value));
  setSelectValue('editTraitSet', payload.traitSet?.setKey || CEO_SET_BASE_VALUE);
  syncCeoSetSummary('edit', 'trait', 'editTraitSet');
  setSelectValue('editAttributeSet', attributeChoiceValueFor(payload.attributeSetSourceKey));
  syncAttributeSummary('edit', 'editAttributeSet');
  applyAttributeSetCloneToInputs('edit', payload.attributeSetClone);
  setSelectValue('editEquipmentSet', payload.equipmentSet?.setKey || CEO_SET_BASE_VALUE);
  syncCeoSetSummary('edit', 'equipment', 'editEquipmentSet');
  setSelectValue('editCombatProfile', payload.combatProfileSourceKey);
  syncEquipmentSummary('edit', 'editCombatProfile');
  setSelectValue('editUnitProfile', payload.unitProfileSourceKey || payload.targetKey);
  syncUnitSummary('edit', 'editUnitProfile');
  applyLandUnitCloneToInputs('edit', payload.unitStatClone);
  $('editWeight').value = payload.spawn?.weight ?? $('editWeight').value;
  $('editAgeRange').value = payload.spawn?.birthYear ?? birthYearForAgeRange(payload.spawn?.ageRange) ?? $('editAgeRange').value;
  $('editMinRound').value = payload.spawn?.minRound ?? $('editMinRound').value;
  $('editMaxRound').value = payload.spawn?.maxRound ?? $('editMaxRound').value;
  setSelectValue('editSpawnEvent', payload.spawn?.event);
  setSelectValue('editSkill', payload.skillSourceKey || payload.skillSources?.historical || payload.skillSources?.romance);
  restoreSkillTreeDraft('edit', payload.skillTree);
  updateImagePreviews();
  updateAllSpawnFieldLabels();
  renderSkillTreeEditors();
}

function loadCloneQueueItem(item) {
  const payload = item.payload;
  const base = characters().find((item) => item.key === payload.sourceKeys?.base);
  if (base) {
    state.selectedKey = realTemplateKey(base) || base.key;
    syncWorkflowGender(characterGenderKey(base));
    state.formOptionsSignature = '';
    renderRoster({ syncSelection: false, renderSelection: false });
    fillForms(base);
  }
  setMode('create');
  $('createName').value = payload.newName || $('createName').value;
  setSelectValue('createGender', state.workflowGender);
  setSelectValue('sourceBase', payload.sourceKeys?.base);
  setSelectValue('sourceImageSet', payload.sourceKeys?.imageSet);
  setSelectValue('sourceSkill', payload.sourceKeys?.skill);
  setSelectValue('createSubtype', payload.subtype);
  refreshTitleSelectForElement('source', '', base);
  setSelectValue('sourceTitle', payload.sourceKeys?.title);
  renderTitleSummary('source', resolveTitleChoice($('sourceTitle').value));
  setSelectValue('sourceTraitSet', payload.traitSet?.setKey || payload.sourceKeys?.traitSet || CEO_SET_BASE_VALUE);
  syncCeoSetSummary('source', 'trait', 'sourceTraitSet');
  setSelectValue('sourceAttributeSet', attributeChoiceValueFor(payload.sourceKeys?.attributeSet));
  syncAttributeSummary('source', 'sourceAttributeSet');
  applyAttributeSetCloneToInputs('source', payload.attributeSetClone);
  setSelectValue('sourceEquipmentSet', payload.equipmentSet?.setKey || payload.sourceKeys?.equipmentSet || CEO_SET_BASE_VALUE);
  syncCeoSetSummary('source', 'equipment', 'sourceEquipmentSet');
  setSelectValue('sourceCombatProfile', payload.sourceKeys?.combatProfile);
  syncEquipmentSummary('source', 'sourceCombatProfile');
  $('sourceDedicatedArmourEnabled').checked = Boolean(payload.dedicatedArmour);
  $('sourceDedicatedArmourValue').value = payload.dedicatedArmour
    ? (payload.dedicatedArmour.armourBonus
      ?? Number(payload.dedicatedArmour.armourValue) - Number(payload.dedicatedArmour.sourceArmourValue))
    : '';
  syncDedicatedArmourControls(
    characters().find((item) => item.key === $('sourceCombatProfile').value),
  );
  setSelectValue('sourceUnitProfile', payload.sourceKeys?.unitProfile || payload.sourceKeys?.base);
  syncUnitSummary('source', 'sourceUnitProfile');
  applyLandUnitCloneToInputs('source', payload.unitStatClone);
  setSelectValue('sourceSpawn', payload.sourceKeys?.spawn);
  $('createWeight').value = payload.spawn?.weight ?? $('createWeight').value;
  $('createAgeRange').value = payload.spawn?.birthYear ?? birthYearForAgeRange(payload.spawn?.ageRange) ?? $('createAgeRange').value;
  $('createMinRound').value = payload.spawn?.minRound ?? $('createMinRound').value;
  $('createMaxRound').value = 999;
  setSelectValue('sourceSpawnEvent', generatedSpawnEventFromRound($('createMinRound').value));
  restoreSkillTreeDraft('source', payload.skillTree);
  updateImagePreviews();
  updateAllSpawnFieldLabels();
  renderSkillTreeEditors();
}

function restoreSkillTreeDraft(prefix, snapshot) {
  if (!snapshot?.sourceSetKey) return;
  state.skillTreeDrafts[skillDraftKey(prefix, snapshot.sourceSetKey)] = {
    sourceSetKey: snapshot.sourceSetKey,
    replacements: { ...(snapshot.replacements || {}) },
  };
}

function applyLandUnitCloneToInputs(prefix, clone) {
  const map = {
    melee_attack: 'MeleeAttack',
    melee_defence: 'MeleeDefence',
    charge_bonus: 'ChargeBonus',
    dismounted_melee_attack: 'DismountedMeleeAttack',
    dismounted_charge_bonus: 'DismountedChargeBonus',
    morale: 'Morale',
    primary_ammo: 'PrimaryAmmo',
  };
  for (const [column, suffix] of Object.entries(map)) {
    const input = $(`${prefix}${suffix}`);
    if (input && clone?.overrides && clone.overrides[column] !== undefined) {
      input.value = clone.overrides[column];
    }
  }
}

function applyAttributeSetCloneToInputs(prefix, clone) {
  const suffixByKey = Object.fromEntries(ATTRIBUTE_FIELDS.map(([suffix, key]) => [key, suffix]));
  for (const [key, value] of Object.entries(clone?.overrides || {})) {
    const suffix = suffixByKey[key];
    const input = suffix ? $(`${prefix}Attr${suffix}`) : null;
    if (input) input.value = value;
  }
}
