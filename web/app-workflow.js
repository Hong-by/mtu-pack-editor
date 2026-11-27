'use strict';

function voiceoverActorForGender(isMale, subtype = '') {
  const value = String(subtype || '');
  const element = value.includes('water') ? 'water'
    : value.includes('wood') ? 'wood'
      : value.includes('fire') ? 'fire'
        : value.includes('metal') ? 'metal'
          : value.includes('earth') ? 'earth'
            : 'metal';
  return isMale
    ? `vo_actor_group_generic_male_${element}_general`
    : `vo_actor_group_generic_female_${element}_general`;
}

function elementKeyFromSubtype(subtype = '') {
  const value = String(subtype || '').toLowerCase();
  if (value.includes('water')) return 'water';
  if (value.includes('wood')) return 'wood';
  if (value.includes('fire')) return 'fire';
  if (value.includes('metal')) return 'metal';
  if (value.includes('earth')) return 'earth';
  return 'metal';
}

function genderCompatibleInitialCeoKey(initialCeoKey, isMale, subtype = '') {
  const key = String(initialCeoKey || '');
  if (!key || isMale === undefined || isMale === null || isMale === '') return key;
  const male = parseBoolean(isMale);
  const lower = key.toLowerCase();
  if (male) {
    if (lower.includes('generic_f_')) return key.replace('generic_f_', 'generic_m_');
    return key;
  }
  if (lower.includes('generic_f_')) {
    return key;
  }
  if (lower.includes('generic_m_')) return key.replace('generic_m_', 'generic_f_');
  return key;
}

function genericInitialCeoKeyForGender(isMale, subtype = '') {
  if (isMale === undefined || isMale === null || isMale === '') return '';
  const gender = parseBoolean(isMale) ? 'm' : 'f';
  const element = elementKeyFromSubtype(subtype);
  return `3k_main_ceo_initial_data_character_generic_${gender}_${element}_general`;
}

function spawnSafeInitialCeoKey(initialCeoKey, isMale, subtype = '') {
  const key = genderCompatibleInitialCeoKey(initialCeoKey, isMale, subtype);
  if (!key) return key;
  const lower = key.toLowerCase();
  if (lower.includes('generic_f_') || lower.includes('generic_m_')) return key;
  return genericInitialCeoKeyForGender(isMale, subtype) || key;
}

function voiceoverActorOptions() {
  const actors = new Set();
  for (const character of characters()) {
    if (character.voiceoverActor) actors.add(character.voiceoverActor);
    if (character.templateRow?.voiceover_actor) actors.add(character.templateRow.voiceover_actor);
  }
  for (const appearance of appearanceSets()) {
    if (appearance.voiceoverActor) actors.add(appearance.voiceoverActor);
    if (appearance.voiceover_actor) actors.add(appearance.voiceover_actor);
  }
  for (const element of Object.values(ELEMENTS)) {
    if (!element.subtype) continue;
    actors.add(voiceoverActorForGender(true, element.subtype));
    actors.add(voiceoverActorForGender(false, element.subtype));
  }
  return [
    option('__auto__', '모델 기준 자동'),
    option('__keep__', '원본 유지'),
    ...[...actors]
      .filter(Boolean)
      .sort((a, b) => friendlyVoiceoverActor(a).localeCompare(friendlyVoiceoverActor(b), 'ko'))
      .map((actor) => option(`voice:${actor}`, friendlyVoiceoverActor(actor))),
  ];
}

function friendlyVoiceoverActor(actor) {
  const value = String(actor || '');
  if (!value) return '-';
  const generic = value.match(/^vo_actor_group_generic_(male|female)_(earth|fire|wood|water|metal)_general$/);
  if (generic) {
    const gender = generic[1] === 'male' ? '남성' : '여성';
    const element = {
      earth: '토',
      fire: '화',
      wood: '목',
      water: '수',
      metal: '금',
    }[generic[2]] || generic[2];
    return `${gender} ${element} 기본 · ${value}`;
  }
  return `${value.replace(/^vo_actor_group_/, '')} · ${value}`;
}

function voiceoverActorFromSelection(selectionValue, modelSet, fallbackTemplate = {}) {
  const value = String(selectionValue || '__auto__');
  const overrides = modelGenderOverridesFromAppearance(modelSet, fallbackTemplate);
  if (value === '__keep__') {
    delete overrides.voiceover_actor;
    return overrides;
  }
  if (value.startsWith('voice:')) {
    overrides.voiceover_actor = value.slice('voice:'.length);
  }
  return overrides;
}

function parseBoolean(value) {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value !== 0;
  const text = String(value || '').trim().toLowerCase();
  return ['true', '1', 'yes', 'y'].includes(text);
}

function characterGenderKey(character) {
  const raw = character?.isMale ?? character?.templateRow?.is_male;
  if (raw === true || raw === 1 || String(raw).toLowerCase() === 'true' || String(raw) === '1') return 'male';
  if (raw === false || raw === 0 || String(raw).toLowerCase() === 'false' || String(raw) === '0') return 'female';
  const hint = `${character?.key || ''} ${character?.name || ''} ${character?.englishName || ''} ${character?.retinue || ''}`.toLowerCase();
  if (/lady|queen|empress|female|generic_f|부인|여성|여장|왕후/.test(hint)) return 'female';
  return 'male';
}

function genderLabel(gender) {
  return gender === 'female' ? '여성' : '남성';
}

function matchesGender(character, gender) {
  if (!gender || gender === 'all') return true;
  return characterGenderKey(character) === gender;
}

function genderedCharacters(items, gender) {
  return (items || []).filter((item) => matchesGender(item, gender));
}

function selectedCharacterMatchesWorkflowGender() {
  const selected = selectedCharacterByKey();
  return selected && matchesGender(selected, state.workflowGender);
}

function syncWorkflowGender(gender) {
  const normalized = gender === 'female' ? 'female' : 'male';
  state.workflowGender = normalized;
  state.editGender = normalized;
  state.createGender = normalized;
  setSelectValue('editGender', normalized);
  setSelectValue('createGender', normalized);
}

function ensureWorkflowSelection() {
  if (selectedCharacterMatchesWorkflowGender()) return selectedCharacter();
  const next = rosterCharacters().find((character) => matchesRosterFilter(character))
    || browsableCharacters().find((character) => matchesGender(character, state.workflowGender))
    || browsableCharacters()[0]
    || selectableFallbackCharacters().find((character) => matchesGender(character, state.workflowGender))
    || selectableFallbackCharacters()[0]
    || characters()[0];
  if (next) {
    state.selectedKey = realTemplateKey(next) || next.key;
    syncWorkflowGender(characterGenderKey(next));
  }
  return next || null;
}

function setWorkflowGender(gender) {
  syncWorkflowGender(gender);
  state.editingQueueIndex = null;
  resetRosterRenderLimit();
  ensureWorkflowSelection();
  renderWorkflowGenderButtons();
  setWorkView('start');
  renderRoster({ syncSelection: false, renderSelection: false });
  renderSelected({ fillEditor: false });
  refreshStageButtons();
  renderValidation();
}

function renderWorkflowGenderButtons() {
  for (const button of document.querySelectorAll('[data-workflow-gender]')) {
    button.classList.toggle('active', button.dataset.workflowGender === state.workflowGender);
  }
}

function retinueKeyForCharacter(character) {
  const explicit = character?.sourceRetinueKey || '';
  if (explicit && explicit !== '-') return explicit;
  const profile = character?.unitProfile || '';
  return profile && profile !== '-' ? profile : '';
}

function retargetImageAssetPath(path, sourceToken, targetToken) {
  const normalized = String(path || '').replace(/\\/g, '/');
  if (!sourceToken || !targetToken) return normalized;
  const parts = normalized.split('/');
  const characterIndex = parts.findIndex((part, index) => (
    part === 'characters' && parts[index - 1] === 'ui' && parts[index + 1]
  ));
  if (characterIndex >= 0) {
    parts[characterIndex + 1] = targetToken;
  }
  let lowerParts = parts.map((part) => part.toLowerCase());
  if (!lowerParts.includes('composites') && characterIndex >= 0) {
    const directPanelIndex = lowerParts.findIndex((part, index) => (
      index > characterIndex + 1 && ['large_panel', 'small_panel'].includes(part)
    ));
    if (directPanelIndex >= 0) {
      parts.splice(directPanelIndex, 0, 'composites');
    }
  }
  const fileName = parts[parts.length - 1] || '';
  const faceIndex = parts.indexOf('faces');
  if (faceIndex > 0 && parts[faceIndex - 1] === 'composites'
      && parts[faceIndex + 1] === sourceToken) parts[faceIndex + 1] = targetToken;
  const extensionIndex = fileName.lastIndexOf('.');
  if (extensionIndex > 0 && fileName.slice(0, extensionIndex) === sourceToken) {
    parts[parts.length - 1] = `${targetToken}${fileName.slice(extensionIndex)}`;
  }
  return parts.join('/');
}

function retargetImageAssetPaths(path, sourceToken, targetToken) {
  const primary = retargetImageAssetPath(path, sourceToken, targetToken);
  if (!primary) return [];
  const aliases = [primary];
  const compositeMatch = primary.match(/^(.*\/composites\/(?:large_panel|small_panel)\/(norm|happy|angry)\/)([^/]+)$/i);
  if (compositeMatch) {
    const [, prefix, state, fileName] = compositeMatch;
    const extension = fileName.match(/\.[^.]+$/)?.[0] || '.png';
    if (state.toLowerCase() === 'norm') {
      aliases.push(`${prefix}norm${extension}`, `${prefix}normal${extension}`, `${prefix}noanim${extension}`);
    } else {
      aliases.push(`${prefix}${state}${extension}`, `${prefix}noanim${extension}`);
    }
  }
  const seen = new Set();
  return aliases.filter((item) => {
    const key = normalizeImageAssetPath(item);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function customImageAssetsFromAppearance(appearance, targetToken, targetCardToken = targetToken) {
  const sourceAssets = imageAssetsFromAppearance(appearance);
  const retargetedAssets = sourceAssets.flatMap((asset) => (
    retargetImageAssetPaths(asset.gamePath || gameImageAssetPath(asset.path), imageTokenForAsset(appearance, asset.gamePath || asset.path), targetToken)
      .map((targetPath) => retargetStillFileToken(targetPath, targetToken, targetCardToken))
      .map((targetPath) => ({
        ...asset,
        targetPath,
      }))
  ));
  // Generic bodies resolve faces separately from armour; unique bodies also
  // need the direct paths. Supply both layouts for the selected portrait only.
  for (const asset of [...retargetedAssets]) {
    const path = asset.targetPath;
    const still = path.match(/^(.*\/stills\/[^/]+\/)(large\/)?([^/]+\.png)$/i);
    if (still && imageFileStemFromPath(path) === targetCardToken) {
      retargetedAssets.push({...asset, targetPath: `${still[1]}faces/${still[2] || ''}${still[3]}`});
    }
    const panel = path.match(/^(.*\/composites\/)((?:large_panel|small_panel)\/.*)$/i);
    if (panel) retargetedAssets.push({...asset, targetPath: `${panel[1]}faces/${targetCardToken}/${panel[2]}`});
  }
  const seenTargets = new Set();
  return retargetedAssets.filter((asset) => {
    const targetPath = normalizeImageAssetPath(asset.targetPath);
    if (!targetPath || seenTargets.has(targetPath)) return false;
    seenTargets.add(targetPath);
    return true;
  });
}

function patchImageAssetsFromAppearance(appearance, targetAppearance, targetToken, targetCardToken) {
  const assets = customImageAssetsFromAppearance(appearance, targetToken, targetCardToken);
  // The Korea shared male face set uses transparent armour layers. These
  // audited source layers must follow the face when its folder is isolated.
  if (imageFolderName(targetAppearance).toLowerCase() !== 'krc_artsets'
      || targetAppearance?.isMale !== true) return assets;
  const seen = new Set(assets.map(asset => asset.targetPath.toLowerCase()));
  for (const asset of imageAssetsFromAppearance(targetAppearance)) {
    const path = gameImageAssetPath(asset.path);
    if (!/(?:^|\/)\w*ancillary_armour_[^/]*_male(?:\/|\.png$)/i.test(path)) continue;
    const targetPath = retargetImageAssetPath(path, imageFolderName(targetAppearance), targetToken);
    if (!seen.has(targetPath.toLowerCase())) {
      assets.push({...asset, targetPath});
      seen.add(targetPath.toLowerCase());
    }
    const emptyPath = targetPath.replace(/\w*ancillary_armour_[^/]*_male(?=\/|\.png$)/i, 'EMPTY');
    if (!seen.has(emptyPath.toLowerCase())) {
      assets.push({...asset, targetPath: emptyPath});
      seen.add(emptyPath.toLowerCase());
    }
  }
  return assets;
}

function artImageKeysFromTargetAssets(imageAssets, fallbackPortraitToken = '', fallbackCardToken = '') {
  const paths = (imageAssets || []).map((asset) => normalizeImageAssetPath(asset.targetPath || asset.path));
  const portraitPath = paths.find((path) => /\/composites\/large_panel\/norm\/(?:noanim|norm|normal)\.png$/i.test(path))
    || paths.find((path) => /\/stills\/halfbody_large\//i.test(path))
    || '';
  const cardPath = paths.find((path) => /\/stills\/unitcards\//i.test(path)) || '';
  const portraitFolder = imageCharacterFolderFromPath(portraitPath) || fallbackPortraitToken;
  const cardStem = imageFileStemFromPath(cardPath) || fallbackCardToken;
  return compactObject({
    portrait: portraitFolder ? `${portraitFolder}/` : '',
    card: cardStem,
  });
}

function imageCharacterFolderFromPath(path) {
  const parts = normalizeImageAssetPath(path).split('/').filter(Boolean);
  const index = parts.findIndex((part, i) => part === 'characters' && parts[i - 1] === 'ui');
  return index >= 0 ? (parts[index + 1] || '') : '';
}

function imageFileStemFromPath(path) {
  const fileName = normalizeImageAssetPath(path).split('/').filter(Boolean).pop() || '';
  return fileName.replace(/\.(png|jpg|jpeg|dds)$/i, '');
}

function retargetStillFileToken(path, targetToken, targetCardToken) {
  if (!targetCardToken || targetCardToken === targetToken) return path;
  const normalized = String(path || '');
  if (!normalized.toLowerCase().includes('/stills/')) return normalized;
  return normalized.replace(new RegExp(`${escapeRegExp(targetToken)}(?=\\.png$)`, 'i'), targetCardToken);
}

function escapeRegExp(value) {
  return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function retargetArtImageKey(value, targetToken) {
  if (!value || !targetToken) return value;
  return String(value).endsWith('/') ? `${targetToken}/` : targetToken;
}

function characterByAppearanceKey(key) {
  if (!key) return null;
  const candidates = characters().filter((item) => (
    (item.key === key || item.artSet === key)
    && !item.virtualImageOnly
    && !isTemplateVariantPoolCharacter(item)
  ));
  return candidates.find((item) => item.source === 'reference')
    || candidates.find((item) => item.source === 'pack')
    || candidates[0]
    || null;
}

function elementMeta(element) {
  return ELEMENTS[element] || { label: '將', name: '기타', subtype: '' };
}

function spawnEventMeta(key) {
  return SPAWN_EVENTS.find((event) => event.key === key) || SPAWN_EVENTS[0];
}

function normalizedRoundValue(value, fallback = 0) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return fallback;
  return Math.max(0, Math.trunc(numeric));
}

function generatedSpawnPlan(raw = {}) {
  const minRound = normalizedRoundValue(raw.minRound, 0);
  return {
    ...raw,
    minRound,
    event: minRound <= 0 ? 'campaign_start' : 'delayed_join',
  };
}

function templateSpawnPlan(raw = {}) {
  const event = raw.event || 'round_pool';
  const minRound = event === 'campaign_start'
    ? 0
    : normalizedRoundValue(raw.minRound, 0);
  return {
    ...raw,
    minRound,
    event,
  };
}

function generatedSpawnEventFromRound(minRound) {
  return generatedSpawnPlan({ minRound }).event;
}

function syncGeneratedSpawnEventField() {
  const plan = generatedSpawnPlan({ minRound: $('createMinRound')?.value });
  const field = $('sourceSpawnEvent');
  if (field) field.value = plan.event;
  return plan;
}
