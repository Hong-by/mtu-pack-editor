'use strict';

function selectedCharacter() {
  const roster = browsableCharacters();
  return roster.find((character) => realTemplateKey(character) === state.selectedKey || character.key === state.selectedKey)
    || roster[0]
    || state.characters.find((character) => hasRealTemplateRow(character) && hasCharacterDetails(character))
    || state.characters[0];
}

function selectedCharacterByKey() {
  const roster = browsableCharacters();
  return roster.find((character) => realTemplateKey(character) === state.selectedKey || character.key === state.selectedKey) || null;
}

function characters() {
  return state.characters;
}

function characterLookup() {
  return cachedDerived('characterLookup', () => {
    const byKey = new Map();
    const byArtSet = new Map();
    const byUniform = new Map();
    const bySlug = new Map();
    for (const character of characters()) {
      if (character.key && !byKey.has(character.key)) byKey.set(character.key, character);
      const templateKey = realTemplateKey(character);
      if (templateKey && !byKey.has(templateKey)) byKey.set(templateKey, character);
      if (character.artSet && !byArtSet.has(character.artSet)) byArtSet.set(character.artSet, character);
      if (character.uniform && !byUniform.has(character.uniform)) byUniform.set(character.uniform, character);
      for (const value of [character.key, templateKey, character.artSet, character.uniform]) {
        const slug = slugFromKey(value);
        if (slug && !bySlug.has(slug)) bySlug.set(slug, character);
      }
    }
    return { byKey, byArtSet, byUniform, bySlug };
  });
}

function charactersByUiKeys(keys) {
  const lookup = characterLookup().byKey;
  const seen = new Set();
  const result = [];
  for (const key of Array.isArray(keys) ? keys : []) {
    const normalizedKey = String(key || '');
    if (!normalizedKey || seen.has(normalizedKey)) continue;
    const character = lookup.get(normalizedKey);
    if (!character) continue;
    seen.add(normalizedKey);
    result.push(character);
  }
  return result;
}

function realTemplateKey(character) {
  const key = character?.templateRow?.key || '';
  return typeof key === 'string' ? key : String(key || '');
}

function hasRealTemplateRow(character) {
  return Boolean(realTemplateKey(character));
}

function hasCharacterDetails(character) {
  return Boolean((character?.details || []).some((detail) => detail?.gameMode));
}

function hasUniqueImageSet(character) {
  const artSet = String(character?.artSet || '').toLowerCase();
  const imageSetName = String(character?.imageSetName || '').toLowerCase();
  const portraitPath = String(character?.portraitPath || '').toLowerCase();
  const cardPath = String(character?.cardPath || '').toLowerCase();
  const combined = `${artSet} ${imageSetName} ${portraitPath} ${cardPath}`;
  return Boolean(character?.artSet)
    && !combined.includes('generic')
    && !combined.includes('scripted');
}

function browsableCharacters() {
  return cachedDerived('browsableCharacters', () => {
    return sortBrowsableCharacters(characters().filter((character) => (
      hasRealTemplateRow(character)
      && hasCharacterDetails(character)
      && !character.imageOnly
      && !character.virtualImageOnly
      && !isRosterHiddenCharacter(character)
    )));
  });
}

function isRosterHiddenCharacter(character) {
  return Boolean(character?.rosterHidden || character?.koreaRosterHidden);
}

function rosterCharacters() {
  return cachedDerived('rosterCharacters', () => {
    return collapseRosterDuplicates(browsableCharacters());
  });
}

function rosterCharactersForCurrentGender() {
  return cachedDerived(`rosterCharacters:${state.workflowGender}`, () => {
    return rosterCharacters().filter((character) => matchesGender(character, state.workflowGender));
  });
}

function collapseRosterDuplicates(items) {
  const byKey = new Map();
  for (const character of items) {
    const key = rosterIdentityKey(character);
    const current = byKey.get(key);
    if (!current || rosterVariantRank(character) > rosterVariantRank(current)) {
      byKey.set(key, character);
    }
  }
  return sortBrowsableCharacters([...byKey.values()]);
}

function rosterIdentityKey(character) {
  return String(
    realTemplateKey(character)
    || character?.baseTemplateKey
    || character?.templateKey
    || character?.key
    || '',
  ).toLowerCase();
}

function rosterVariantRank(character) {
  const source = sourceInfo(character).tag;
  const localRank = source === 'MY' ? 40 : source === 'MTU' ? 30 : source === 'KR' ? 25 : 0;
  const referencePenalty = character?.source === 'reference' ? -5 : 0;
  const imageRank = character?.portraitImagePath ? 4 : character?.portraitPath ? 2 : 0;
  return localRank + referencePenalty + imageRank;
}

function isLeaderCharacter(character) {
  return character?.koreaRole === 'leader'
    || character?.isFactionLeader
    || /leader|faction_leader|emperor|king|queen|monarch/i.test(`${character?.tags || ''} ${character?.titleKey || ''} ${character?.key || ''}`);
}

function isUniqueRosterCharacter(character) {
  if (character?.unique === true || character?.templateRow?.unique === true) return true;
  if (hasUniqueImageSet(character)) return true;
  return !/generic|dummy|placeholder/i.test(`${character?.key || ''} ${character?.retinue || ''} ${character?.imageSetName || ''}`);
}

function isRecommendedRosterCharacter(character) {
  return isFavoriteCharacter(character)
    || isLeaderCharacter(character)
    || character?.isKoreaAddon
    || isUniqueRosterCharacter(character);
}

function matchesRosterFilter(character) {
  if (!matchesGender(character, state.workflowGender)) return false;
  if (state.filter === 'all') return true;
  if (state.filter === 'recommended') return isRecommendedRosterCharacter(character);
  if (state.filter === 'unique') return isUniqueRosterCharacter(character);
  if (state.filter === 'leader') return isLeaderCharacter(character);
  if (state.filter === 'korea') return Boolean(character?.isKoreaAddon);
  if (state.filter === 'favorites') return isFavoriteCharacter(character);
  if (Object.prototype.hasOwnProperty.call(ELEMENTS, state.filter)) return character?.element === state.filter;
  if (state.filter.startsWith('element:')) return character?.element === state.filter.slice(8);
  if (state.filter.startsWith('korea:')) return character?.koreaFaction === state.filter.slice(6);
  return true;
}

function characterFavoriteKey(item) {
  return rosterIdentityKey(item);
}

function isFavoriteCharacter(itemOrKey) {
  const key = typeof itemOrKey === 'string' ? itemOrKey : characterFavoriteKey(itemOrKey);
  return Boolean(key && state.favoriteCharacterKeys.has(key));
}

function toggleFavoriteCharacter(key) {
  if (!key) return;
  if (state.favoriteCharacterKeys.has(key)) {
    state.favoriteCharacterKeys.delete(key);
  } else {
    state.favoriteCharacterKeys.add(key);
  }
  saveFavoriteCharacterKeys();
  renderRoster();
}

function loadFavoriteCharacterKeys() {
  try {
    const raw = window.localStorage?.getItem(FAVORITE_CHARACTER_STORAGE_KEY);
    const values = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(values) ? values.map(String) : []);
  } catch {
    return new Set();
  }
}

function saveFavoriteCharacterKeys() {
  try {
    window.localStorage?.setItem(
      FAVORITE_CHARACTER_STORAGE_KEY,
      JSON.stringify([...state.favoriteCharacterKeys].sort()),
    );
  } catch {
    // Ignore storage errors; favorites are a convenience feature.
  }
}

function appearanceGalleryCharacters() {
  const query = normalizeLookupText(state.imageGalleryQuery);
  const items = selectableImageAppearances();
  const filtered = query
    ? items.filter((appearance) => normalizeLookupText(appearanceSearchText(appearance)).includes(query))
    : items;
  return sortFavoriteAppearances(filtered);
}

function appearanceFavoriteKey(item) {
  return String(item?.key || item?.artSet || '');
}

function isFavoriteAppearance(itemOrKey) {
  const key = typeof itemOrKey === 'string' ? itemOrKey : appearanceFavoriteKey(itemOrKey);
  return Boolean(key && state.favoriteAppearanceKeys.has(key));
}

function toggleFavoriteAppearance(key) {
  if (!key) return;
  if (state.favoriteAppearanceKeys.has(key)) {
    state.favoriteAppearanceKeys.delete(key);
  } else {
    state.favoriteAppearanceKeys.add(key);
  }
  saveFavoriteAppearanceKeys();
  renderAppearanceGallery();
}

function sortFavoriteAppearances(items) {
  return [...items].sort((a, b) => Number(isFavoriteAppearance(b)) - Number(isFavoriteAppearance(a)));
}

function loadFavoriteAppearanceKeys() {
  try {
    const raw = window.localStorage?.getItem(FAVORITE_APPEARANCE_STORAGE_KEY);
    const values = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(values) ? values.map(String) : []);
  } catch {
    return new Set();
  }
}

function saveFavoriteAppearanceKeys() {
  try {
    window.localStorage?.setItem(
      FAVORITE_APPEARANCE_STORAGE_KEY,
      JSON.stringify([...state.favoriteAppearanceKeys].sort()),
    );
  } catch {
    // Ignore storage errors; favorites are a convenience feature.
  }
}

function activeImageSelectId() {
  return state.mode === 'create' ? 'sourceImageSet' : 'editImageSet';
}

function currentImageSelectionKey() {
  return $(activeImageSelectId())?.value || '';
}

function galleryCardKey(character) {
  return character?.key || character?.artSet || '';
}

function appearanceKeyForGalleryCharacter(character) {
  return character?.key || '';
}

function currentGallerySelectionKey(galleryCharacters = appearanceGalleryCharacters()) {
  const selectedAppearanceKey = currentImageSelectionKey();
  const storedCharacter = galleryCharacters.find((character) => (
    galleryCardKey(character) === state.selectedAppearanceCardKey
  ));
  if (storedCharacter && appearanceKeyForGalleryCharacter(storedCharacter) === selectedAppearanceKey) {
    return state.selectedAppearanceCardKey;
  }
  const selectedCharacter = galleryCharacters.find((character) => (
    appearanceKeyForGalleryCharacter(character) === selectedAppearanceKey
  ));
  return galleryCardKey(selectedCharacter);
}

function applyGalleryImageSelection(cardKey) {
  const character = appearanceGalleryCharacters().find((item) => galleryCardKey(item) === cardKey);
  const appearanceKey = appearanceKeyForGalleryCharacter(character) || cardKey;
  const appearance = character || appearanceByKey(appearanceKey);
  if (!appearance) return;
  state.selectedAppearanceCardKey = cardKey;
  const imageSelectId = activeImageSelectId();
  const imageSelect = $(imageSelectId);
  if (imageSelect) imageSelect.value = appearanceKey;
  if (state.mode === 'create') {
    setSelectValue('sourceImageSet', appearanceKey);
  } else {
    setSelectValue('editImageSet', appearanceKey);
  }
  updateImagePreviews();
  renderAppearanceGallery();
  renderValidation();
}

function sortBrowsableCharacters(items) {
  return [...items].sort((a, b) => {
    const aImageOnly = Number(Boolean(a.virtualImageOnly));
    const bImageOnly = Number(Boolean(b.virtualImageOnly));
    if (aImageOnly !== bImageOnly) return aImageOnly - bImageOnly;
    const priorityDiff = sourcePriority(a) - sourcePriority(b);
    if (priorityDiff) return priorityDiff;
    return String(a.name || '').localeCompare(String(b.name || ''), 'ko');
  });
}
