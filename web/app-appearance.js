'use strict';

function sourceInfo(item) {
  if (item?.isKoreaAddon && (item?.koreaFaction || item?.koreaFactionKey || item?.koreaFactionLabel)) {
    return { tag: 'KR', label: item.koreaFactionLabel || 'Korea', priority: -1 };
  }
  if (String(item?.sourceTag || '').toUpperCase() === 'MTU') {
    return { tag: 'MTU', label: 'MTU', priority: 0 };
  }
  if (String(item?.sourceTag || '').toUpperCase() === 'DATA') {
    return { tag: 'DATA', label: 'DATA', priority: 3 };
  }
  if (String(item?.sourceTag || '').toUpperCase() === 'PACK') {
    return { tag: 'PACK', label: '팩/참조', priority: 2 };
  }
  if (String(item?.sourceTag || '').toUpperCase() === 'MANUAL') {
    return { tag: '수동', label: '수동 정리', priority: 2 };
  }
  const sourceFields = [
    item?.sourceTag,
    item?.referenceSourcePath,
    item?.sourcePackName,
    item?.sourceIdentity,
    item?.titleKey,
    item?.titleInitialCeoKey,
    item?.titleLocKey,
    item?.key,
    item?.name,
    item?.imageSetName,
    item?.portraitPath,
    item?.cardPath,
    item?.portraitImagePath,
    item?.cardImagePath,
  ];
  if (item?.virtualImageOnly || item?.imageOnly) {
    sourceFields.push(item?.portraitImageSourcePath, item?.cardImageSourcePath);
  }
  const text = sourceFields.filter(Boolean).join(' ').toLowerCase();
  if (text.includes('3k_mtu') || text.includes('_mtu_characters') || text.includes('[mtu]') || text.includes('mtu ')) {
    return { tag: 'MTU', label: 'MTU', priority: 0 };
  }
  if (text.includes('aw-design') || text.includes('aw addon') || text.includes('aw ') || text.includes('aw-') || text.includes('aw_')) {
    return { tag: 'AW', label: 'AW', priority: 4 };
  }
  if (text.includes('bfg_')) return { tag: 'BFG', label: 'BFG', priority: 1 };
  if (text.includes('lshz_')) return { tag: 'LSHZ', label: 'LSHZ', priority: 2 };
  if (text.includes('data.pack') || text.includes('database.pack') || text.includes('data_')) {
    return { tag: 'DATA', label: 'DATA', priority: 3 };
  }
  return { tag: 'MY', label: 'MY', priority: 0 };
}

function isAwImageOnly(item) {
  return Boolean(item?.virtualImageOnly || item?.imageOnly) && sourceInfo(item).tag === 'AW';
}

function isLshzImageOnly(item) {
  return Boolean(item?.virtualImageOnly || item?.imageOnly) && sourceInfo(item).tag === 'LSHZ';
}

function displayNameWithDummyMarker(item) {
  const name = displayLabel(item?.name || item?.imageSetName || '-', item?.key || item?.artSet || '');
  return name;
}

function cleanDisplayCandidate(value) {
  return isBadDisplayHint(value) ? '' : String(value || '').trim();
}

function imageOnlySourceSuffix(item) {
  if (!item?.virtualImageOnly && !item?.imageOnly) return '';
  const identity = item.sourceIdentity
    || [
      sourcePackName(item),
      item.portraitPath || item.portrait,
      item.cardPath || item.card,
    ].filter(Boolean).join(' · ');
  return identity ? ` (${identity})` : '';
}

function sourcePackName(item) {
  const explicit = item?.sourcePackName;
  if (explicit) return explicit;
  const source = item?.referenceSourcePath || item?.portraitImageSourcePath || item?.cardImageSourcePath || '';
  return String(source).split(/[\\/]/).filter(Boolean).pop() || '';
}

function canUseAsModelSet(item) {
  return Boolean(item) && !item.imageOnly && !item.virtualImageOnly && !isAwImageOnly(item);
}

function modelArtSetKeyForRecipe(modelSet, fallbackCharacter) {
  if (canUseAsModelSet(modelSet) && modelSet?.artSet) return modelSet.artSet;
  return fallbackCharacter?.artSet || fallbackCharacter?.templateRow?.art_set_override || '';
}

function sourcePriority(item) {
  return sourceInfo(item).priority;
}

function sourceBadgeMarkup(item) {
  const info = sourceInfo(item);
  return `<span class="source-badge source-${info.tag.toLowerCase()}">${escapeHtml(info.tag)}</span>`;
}

function sourceLabel(item) {
  return sourceInfo(item).tag;
}

function cloneBaseCharacters() {
  return browsableCharacters().filter((character) => !character.virtualImageOnly);
}

function titleSourceCharacters() {
  return selectableFallbackCharacters().filter((character) => character.titleInitialCeoKey || character.titleKey);
}

function titleChoiceValue(character) {
  return character?.titleChoiceKey || character?.key || '';
}

function isBackgroundTitleChoiceKey(value) {
  const key = String(value || '').trim();
  return /^bg_/i.test(key) && /character_background/i.test(key);
}

function isInitialCeoTitleKey(value) {
  const key = String(value || '').trim();
  if (!key || isBackgroundTitleChoiceKey(key)) return false;
  return /_ceo_initial_data_character_|_ceo_career_historical_|_ceo_node_career_/i.test(key);
}

function canonicalTitleKey(value = '') {
  const key = String(value || '').trim()
    .replace(/^ceo_nodes_title_/, '')
    .replace(/^ceo_nodes_description_/, '');
  if (!key) return '';
  return key
    .replace('_ceo_node_career_', '_ceo_career_')
    .replace(/_\d\d$/, '')
    .replace('_ceo_initial_data_character_historical_', '_ceo_career_historical_')
    .replace('_ceo_initial_data_character_romance_', '_ceo_career_historical_')
    .replace('_ceo_initial_data_character_', '_ceo_career_historical_');
}

function canonicalTitleChoiceKey(item) {
  if (item?.titleCanonicalKey) return String(item.titleCanonicalKey);
  const keys = [
    item?.titleCeoKey,
    item?.titleCareerCeoKey,
    item?.titleKey,
    item?.titleInitialCeoKey,
    item?.titleLocKey,
    item?.key,
  ];
  return keys.map(canonicalTitleKey).find(Boolean) || '';
}

function titleChoiceCanSetInitialCeo(item) {
  if (!item || item.displayOnlyTitle) return false;
  const keys = [
    item.titleInitialCeoKey,
    item.titleCareerCeoKey,
    item.titleCeoKey,
    item.titleKey,
    item.key,
  ];
  return keys.some(isInitialCeoTitleKey);
}

function titleChoiceQuality(item) {
  if (!item) return -1;
  let score = Number(item.sourceRank || 0);
  if (item.sourceTag === 'MANUAL') score -= 20;
  if (item.manualTitleOnly) score -= 100;
  if (item.titleName && item.titleName !== '칭호 미확인' && !looksLikeTitleSuffixFallback(item.titleName, item.titleKey)) score += 40;
  if (hasHangul(item.titleName)) score += 30;
  if (titleEffectFor(item)) score += 20;
  if (item.titleDescription || item.titleEffectSummary) score += 10;
  if (item.titleKey || item.titleCeoKey || item.titleCareerCeoKey || item.titleInitialCeoKey) score += 10;
  return score;
}

function mergeTitleChoice(base, fallback) {
  const merged = { ...(base || {}) };
  for (const key of [
    'titleDescription',
    'titleHasDescription',
    'titleEffects',
    'titleEffectSummary',
    'titleEffectTitle',
    'titleCeoKey',
    'titleElement',
    'titleElements',
    'titleCareerCeoKey',
    'titleKey',
    'titleInitialCeoKey',
    'titleLocKey',
    'titleCanonicalKey',
    'titleSourceKind',
    'commonTitleRole',
    'manualTitleEffect',
  ]) {
    const value = merged[key];
    const missingArray = Array.isArray(value) && value.length === 0;
    if ((!value || missingArray) && fallback?.[key]) merged[key] = fallback[key];
  }
  return merged;
}

function dedupeTitleChoices(items) {
  const byKey = new Map();
  const order = [];
  for (const item of items || []) {
    const key = canonicalTitleChoiceKey(item);
    if (!key) {
      const fallbackKey = titleChoiceValue(item);
      if (fallbackKey && !byKey.has(fallbackKey)) {
        byKey.set(fallbackKey, item);
        order.push(fallbackKey);
      }
      continue;
    }
    if (!byKey.has(key)) {
      byKey.set(key, item);
      order.push(key);
      continue;
    }
    const existing = byKey.get(key);
    if (titleChoiceQuality(item) > titleChoiceQuality(existing)) {
      byKey.set(key, mergeTitleChoice(item, existing));
    } else {
      byKey.set(key, mergeTitleChoice(existing, item));
    }
  }
  return order.map((key) => byKey.get(key)).filter(Boolean);
}

function dedupeTitleChoicesByDisplay(items) {
  const byKey = new Map();
  const order = [];
  for (const item of items || []) {
    const displayKey = titleDisplayDedupeKey(item);
    const fallbackKey = canonicalTitleChoiceKey(item) || titleChoiceValue(item);
    const key = displayKey || fallbackKey;
    if (!key) continue;
    if (!byKey.has(key)) {
      byKey.set(key, item);
      order.push(key);
      continue;
    }
    const existing = byKey.get(key);
    if (titleChoiceQuality(item) > titleChoiceQuality(existing)) {
      byKey.set(key, mergeTitleChoice(item, existing));
    } else {
      byKey.set(key, mergeTitleChoice(existing, item));
    }
  }
  return order.map((key) => byKey.get(key)).filter(Boolean);
}

function titleCareerCeoKeyFromNodeKey(value) {
  const key = String(value || '').trim()
    .replace(/^ceo_nodes_title_/, '')
    .replace(/^ceo_nodes_description_/, '');
  if (!/_ceo_node_career_/i.test(key)) return '';
  return key.replace('_ceo_node_career_', '_ceo_career_').replace(/_\d\d$/, '');
}

function titleNodeKeyFromCareerKey(value) {
  const key = String(value || '').trim();
  if (!/_ceo_career_/i.test(key)) return '';
  return `${key.replace('_ceo_career_', '_ceo_node_career_')}_01`;
}

function knownInitialCeoKeysForTitles() {
  return cachedDerived('knownInitialCeoKeysForTitles', () => new Set((state.options?.initialCeos || [])
    .map((item) => String(item?.key || '').trim())
    .filter(Boolean)));
}

function titleInitialCeoAliasCandidatesForTitles(initialCeoKey) {
  const key = String(initialCeoKey || '').trim();
  if (!key) return [];
  const candidates = [key];
  if (/_empress_he_fire$/i.test(key)) {
    candidates.push('3k_dlc04_ceo_initial_data_character_historical_non_deployable_empress_he_fire');
  }
  if (/_lady_sun_shangxiang$/i.test(key)) {
    candidates.push(key.replace(/_lady_sun_shangxiang$/i, '_lady_sun'));
  }
  return candidates;
}

function historicalInitialCeoTokenForTitles(initialCeoKey) {
  const key = String(initialCeoKey || '').trim();
  const marker = '_ceo_initial_data_character_historical_';
  const index = key.indexOf(marker);
  return index >= 0 ? key.slice(index + marker.length).replace(/^_+|_+$/g, '').toLowerCase() : '';
}

function stripInitialCeoTokenNoiseForTitles(token) {
  return String(token || '').replace(/^non_deployable_/i, '').replace(/^deployable_/i, '').toLowerCase();
}

function stripInitialCeoElementSuffixForTitles(token) {
  return String(token || '').replace(/_(earth|fire|metal|water|wood)$/i, '').toLowerCase();
}

function initialCeoTokenMatchScoreForTitles(requestedToken, candidateToken) {
  const requested = stripInitialCeoTokenNoiseForTitles(requestedToken);
  const candidate = stripInitialCeoTokenNoiseForTitles(candidateToken);
  if (!requested || !candidate) return 0;
  if (requested === candidate) return 100;
  if (candidate.endsWith(`_${requested}`) || candidate === requested) return 92;
  if (requested.endsWith(`_${candidate}`) && candidate.split('_').length >= 2) return 82;
  const requestedWithoutElement = stripInitialCeoElementSuffixForTitles(requested);
  const candidateWithoutElement = stripInitialCeoElementSuffixForTitles(candidate);
  if (requestedWithoutElement && requestedWithoutElement === candidateWithoutElement) return 78;
  if (requestedWithoutElement && candidateWithoutElement.endsWith(`_${requestedWithoutElement}`)) return 74;
  if (candidateWithoutElement && requestedWithoutElement.endsWith(`_${candidateWithoutElement}`) && candidateWithoutElement.split('_').length >= 2) return 68;
  return 0;
}

function closestKnownTitleInitialCeoKeyForTitles(initialCeoKey) {
  const requestedToken = historicalInitialCeoTokenForTitles(initialCeoKey);
  if (!requestedToken) return '';
  let bestScore = 0;
  let bestKeys = [];
  for (const key of knownInitialCeoKeysForTitles()) {
    const score = initialCeoTokenMatchScoreForTitles(requestedToken, historicalInitialCeoTokenForTitles(key));
    if (score > bestScore) {
      bestScore = score;
      bestKeys = [key];
    } else if (score && score === bestScore) {
      bestKeys.push(key);
    }
  }
  return bestKeys.length === 1 ? bestKeys[0] : '';
}

function knownTitleInitialCeoKeyForTitles(initialCeoKey) {
  const candidates = titleInitialCeoAliasCandidatesForTitles(initialCeoKey);
  if (!candidates.length) return '';
  const known = knownInitialCeoKeysForTitles();
  if (!known.size) return candidates[0];
  return candidates.find((candidate) => known.has(candidate))
    || closestKnownTitleInitialCeoKeyForTitles(initialCeoKey)
    || '';
}

function titleInitialCeoKeyFromCareerKey(value) {
  const key = String(value || '').trim();
  if (!/_ceo_career_historical_/i.test(key)) return '';
  return knownTitleInitialCeoKeyForTitles(key.replace('_ceo_career_historical_', '_ceo_initial_data_character_historical_'));
}

function sheetTitleEntryForManualEffect(effect) {
  const owner = normalizeKoreanText(effect?.owner);
  const title = normalizeKoreanText(effect?.title);
  if (!title) return null;
  const titles = sheetTitleMap();
  const exact = Object.entries(titles).find(([, item]) => (
    normalizeKoreanText(item.krTitle || item.enTitle) === title
    && (!owner || normalizeKoreanText(item.krName || item.enName) === owner)
  ));
  if (exact) return { key: exact[0], info: exact[1] };
  const titleOnly = Object.entries(titles).filter(([, item]) => (
    normalizeKoreanText(item.krTitle || item.enTitle) === title
  ));
  return titleOnly.length === 1 ? { key: titleOnly[0][0], info: titleOnly[0][1] } : null;
}

function titleCatalogChoices() {
  return cachedDerived('titleCatalogChoices', () => dedupeTitleChoices((state.options?.titleCatalog || [])
      .filter((item) => item?.key)
      .filter((item) => !isGeneratedTitleCatalogItem(item))
      .map((item) => {
        const sheetTitle = sheetTitleInfoFor(item.ceoNodeKey || item.initialCeoKey || item.key, item.ownerKey || '');
        const sheetHero = sheetHeroInfoForAny(item.ownerKey, item.key, item.ownerName);
        const ownerName = sheetTitle?.krName || sheetHero?.kr || koreanizeTitleOwnerName(item.ownerName || friendlyKey(item.ownerKey || item.key));
        const titleName = fallbackTitleDisplayName(displayTitleLabel(item.label, item.key, sheetTitle?.krTitle), item.key, ownerName);
        return {
          key: item.ownerKey || item.key,
          titleChoiceKey: `catalog_title::${item.key}`,
          name: ownerName,
          titleOwnerName: ownerName,
          titleName,
          titleDescription: item.description || '',
          titleHasDescription: Boolean(item.hasDescription || item.description),
          titleEffects: Array.isArray(item.effects) ? item.effects : [],
          titleEffectSummary: item.effectSummary || '',
          titleEffectTitle: item.effectTitle || '',
          titleCeoKey: item.titleCeoKey || item.ceoKey || item.key,
          titleElement: item.element || '',
          titleElements: Array.isArray(item.elements) ? item.elements : (item.element ? [item.element] : []),
          titleCareerCeoKey: titleCareerCeoKeyFromNodeKey(item.ceoNodeKey || item.key),
          titleKey: item.ceoNodeKey || item.key,
          titleInitialCeoKey: item.initialCeoKey || '',
          titleLocKey: item.locTitleKey || '',
          titleCanonicalKey: item.canonicalTitleGroup || '',
          titleSourceKind: item.titleSourceKind || '',
          commonTitleRole: item.commonTitleRole || '',
          sourceTag: item.sourceTag || '',
          sourceRank: item.sourceRank,
          sourcePackName: item.sourcePackName || '',
          referenceSourcePath: item.referenceSourcePath || '',
          sourceIdentity: item.sourceTablePath || '',
        };
      })));
}

function isGeneratedTitleCatalogItem(item) {
  const combined = [
    item?.key,
    item?.label,
    item?.ownerKey,
    item?.ownerName,
    item?.initialCeoKey,
    item?.ceoNodeKey,
    item?.sourceTablePath,
    item?.sourceIdentity,
  ].filter(Boolean).join(' ').toLowerCase();
  return /generic_nomads/.test(combined)
    || /xianbei_template_generic/.test(combined)
    || /template_generic_(castellan|colonel)/.test(combined)
    || /generic_(castellan|colonel)/.test(combined)
    || (isLowQualityGeneratedLabel(combined) && !sheetHeroInfoForAny(item?.ownerKey, item?.key, item?.ownerName));
}

function koreanizeTitleOwnerName(value) {
  const text = String(value || '').trim();
  const genericLabel = genericDisplayName(text);
  if (genericLabel) return genericLabel;
  const slug = slugFromKey(text);
  const sheetHero = sheetHeroInfoFor(slug);
  if (sheetHero?.kr) return sheetHero.kr;
  return koreanLabelFromText(text) || text;
}

function displayTitleLabel(label, key = '', fallback = '') {
  const text = String(label || '').trim();
  const sheetTitle = sheetTitleInfoFor(key || text);
  if (sheetTitle?.krTitle) return sheetTitle.krTitle;
  if (fallback) return fallback;
  if (isMixedNameTitleLabel(text)) return '';
  if (text && hasHangul(text) && !looksLikeInternalKey(text) && !looksLikeSlugLabel(text) && !looksLikeTitleSuffixFallback(text, key)) return text;
  return fallbackTitleDisplayName(text, key);
}

function looksLikeTitleSuffixFallback(value, key = '') {
  const text = String(value || '').trim();
  if (!text) return false;
  if (/^\d{1,2}$/.test(text)) return true;
  return /(?:^|\s)\d{1,2}$/.test(text) && /_ceo_node_career_|_ceo_career_|ceo_nodes_title_/i.test(String(key || text));
}

function fallbackTitleDisplayName(label = '', key = '', ownerName = '') {
  const sheetTitle = sheetTitleInfoFor(key || label);
  if (sheetTitle?.krTitle) return sheetTitle.krTitle;
  const owner = cleanTitleOwnerName(ownerName || sheetTitle?.krName || '', key || label);
  if (owner) return `${owner} 기본 칭호`;
  const slug = slugFromKey(key || label).replace(/_(0\d|1\d|2\d)$/, '');
  const slugOwner = cleanTitleOwnerName('', slug);
  if (slugOwner) return `${slugOwner} 기본 칭호`;
  const text = String(label || '').trim();
  const translated = koreanizeTitleLabel(text && !looksLikeTitleSuffixFallback(text, key) ? text : slug, key);
  return translated && !looksLikeTitleSuffixFallback(translated, key) ? translated : '칭호 미확인';
}

function cleanTitleOwnerName(ownerName = '', key = '') {
  const owner = String(ownerName || '').trim();
  if (owner && hasHangul(owner) && !looksLikeInternalKey(owner) && !looksLikeSlugLabel(owner) && !looksLikeTitleSuffixFallback(owner, key)) {
    return owner;
  }
  const hero = sheetHeroInfoFor(key) || sheetHeroInfoFor(slugFromKey(key));
  return hero?.kr || '';
}

function isKoreaAddonItem(item) {
  if (!item) return false;
  if (item.isKoreaAddon || item.koreaFaction || item.koreaFactionLabel || item.koreaRole) return true;
  const keyText = `${item.key || ''} ${item.templateRow?.key || ''}`.toLowerCase();
  return keyText.includes('3k_mod_template_historical_') || keyText.includes('ironic_template_historical_');
}

function koreaTitleOverrideFor(item, titleInfo = {}) {
  if (!isKoreaAddonItem(item)) return '';
  const keys = [
    titleInfo.ceoNodeKey,
    titleInfo.initialCeoKey,
    titleInfo.locTitleKey,
  ].map((value) => String(value || '').trim().replace(/^ceo_nodes_title_/, ''));
  for (const key of keys) {
    if (KOREA_EP_TITLE_OVERRIDES[key]) return KOREA_EP_TITLE_OVERRIDES[key];
  }
  return '';
}

function looksLikeInternalKey(value) {
  return /(^|[ _])3k_|_records$|^[a-z0-9_]+$/i.test(String(value || '').trim());
}

function looksLikeSlugLabel(value) {
  const text = String(value || '').trim();
  if (!text) return false;
  if (/[가-힣]/.test(text)) return false;
  return /^[a-z][a-z0-9_' -]+$/i.test(text);
}

function koreanizeTitleLabel(value, key = '') {
  const original = String(value || '').trim();
  const normalized = slugFromKey(`${key || ''}_${original}`);
  const genericLabel = genericDisplayName(normalized);
  if (genericLabel) return genericLabel;
  const sheetTitle = sheetTitleInfoFor(key || original);
  if (sheetTitle?.krTitle) return sheetTitle.krTitle;
  return koreanLabelFromText(original, key) || friendlyKey(key) || original;
}

function manualTitleChoices() {
  return cachedDerived('manualTitleChoices', () => MANUAL_TITLE_EFFECTS.map((effect, index) => {
      const ownerKey = normalizeKoreanText(effect.owner);
      const sheetEntry = sheetTitleEntryForManualEffect(effect);
      const sheetCareerKey = sheetEntry?.key || '';
      const matchedCharacter = characters().find((character) => {
        const names = [
          character.name,
          character.titleOwnerName,
          sheetHeroInfoFor(character.key)?.kr,
        ];
        return names.some((name) => normalizeKoreanText(name) === ownerKey)
          && normalizeKoreanText(character.titleName) === normalizeKoreanText(effect.title);
      });
      const matchedCatalog = titleCatalogChoices().find((item) => (
        normalizeKoreanText(item.titleOwnerName || item.name) === ownerKey
        && normalizeKoreanText(item.titleName) === normalizeKoreanText(effect.title)
      ));
      const matchedTitleSource = matchedCatalog || matchedCharacter;
      return {
        ...(matchedTitleSource || {}),
        key: matchedTitleSource?.key || `manual_title_effect_${index}`,
        titleChoiceKey: `${matchedCharacter?.key || 'manual'}::manual_title::${index}`,
        name: effect.owner,
        titleOwnerName: effect.owner,
        titleName: effect.title,
        titleDescription: effect.effects || '',
        titleHasDescription: Boolean(effect.effects),
        titleEffects: effect.effects ? [effect.effects] : [],
        titleEffectSummary: effect.effects || '',
        titleEffectTitle: effect.title || '',
        titleCeoKey: matchedTitleSource?.titleCeoKey || matchedTitleSource?.titleKey || '',
        titleElement: matchedTitleSource?.titleElement || matchedTitleSource?.element || '',
        titleElements: matchedTitleSource?.titleElements || (matchedTitleSource?.element ? [matchedTitleSource.element] : []),
        titleCareerCeoKey: matchedTitleSource?.titleCareerCeoKey || sheetCareerKey,
        titleKey: matchedTitleSource?.titleKey || titleNodeKeyFromCareerKey(sheetCareerKey) || '효과 정리 전용',
        titleInitialCeoKey: matchedTitleSource?.titleInitialCeoKey || titleInitialCeoKeyFromCareerKey(sheetCareerKey) || '',
        titleLocKey: matchedTitleSource?.titleLocKey || '',
        sourceTag: 'MANUAL',
        manualTitleEffect: effect,
        manualTitleAnchored: Boolean(matchedTitleSource),
        manualTitleOnly: !matchedTitleSource && !sheetCareerKey,
      };
    }));
}

function allTitleChoices() {
  return cachedDerived('allTitleChoices', () => {
    const manual = manualTitleChoices().filter((item) => item.manualTitleAnchored);
    const catalog = titleCatalogChoices();
    const regularSource = catalog.length ? catalog : titleSourceCharacters();
    const regular = regularSource.filter((character) => {
      const owner = normalizeKoreanText(character.titleOwnerName || character.name);
      const title = normalizeKoreanText(character.titleName);
      return !manual.some((item) => (
        normalizeKoreanText(item.titleOwnerName || item.name) === owner
        && normalizeKoreanText(item.titleName) === title
      ));
    });
    return sortTitleCandidates(dedupeTitleChoicesByDisplay(dedupeTitleChoices([...manual, ...regular])));
  });
}

function titleElementsForChoice(item) {
  const values = [
    ...(Array.isArray(item?.titleElements) ? item.titleElements : []),
    item?.titleElement,
    item?.element,
  ].map((value) => String(value || '').trim()).filter(Boolean);
  return [...new Set(values)];
}

function titleChoiceMatchesElement(item, element) {
  const target = String(element || '').trim();
  if (!target) return true;
  const elements = titleElementsForChoice(item);
  return elements.length ? elements.includes(target) : false;
}

function titleChoicesForFilter(filter, ...preserveChoices) {
  const keep = new Set(
    preserveChoices
      .filter(Boolean)
      .map((item) => titleChoiceValue(item))
      .filter(Boolean),
  );
  const choices = allTitleChoices();
  const filtered = choices.filter((item) => (
    titleChoiceMatchesStatFilter(item, filter) || keep.has(titleChoiceValue(item))
  ));
  return filtered.length ? sortTitleCandidatesForFilter(filtered, filter) : choices;
}

function titleFilterForPrefix(prefix) {
  return state.titleFilters?.[prefix] || 'all';
}

function titleChoicesForPrefix(prefix, ...preserveChoices) {
  return titleChoicesForFilter(titleFilterForPrefix(prefix), ...preserveChoices);
}

function titleChoicesForElement(element, ...preserveChoices) {
  return titleChoicesForFilter('all', ...preserveChoices);
}

function resolveTitleChoice(value) {
  const key = String(value || '');
  return allTitleChoices().find((item) => titleChoiceValue(item) === key)
    || selectableFallbackCharacters().find((item) => item.key === key)
    || null;
}

function packTemplateCharacters() {
  return selectableFallbackCharacters().filter((character) => {
    if (character.source === 'reference') return false;
    const details = detailsByMode(character);
    return Boolean(details.historical || details.romance);
  });
}

function firstCharacterWithDetails(...candidates) {
  for (const character of candidates) {
    if (!character) continue;
    const details = detailsByMode(character);
    if (details.historical || details.romance) return character;
  }
  return packTemplateCharacters()[0] || candidates.find(Boolean) || null;
}

function appearanceSets() {
  return cachedDerived('appearanceSets', () => {
    const artSets = (state.options?.artSets || [])
      .filter((item) => item?.key)
      .map((item) => ({
        key: item.key,
        name: displayLabel(item.label, item.key),
        element: elementFromSubtype(`${item.key} ${item.uniform || ''}`),
        portrait: portraitGlyph(item.label || item.key),
        artSet: item.key,
        imageSetName: displayLabel(item.label, item.key),
        modelSetName: item.imageOnly || item.virtual ? '모델 없음' : displayLabel(item.uniformLabel || item.uniform, item.key),
        portraitPath: item.portrait || '',
        cardPath: item.card || '',
        portraitImagePath: item.portraitImagePath || '',
        portraitImageSourcePath: item.portraitImageSourcePath || '',
        cardImagePath: item.cardImagePath || '',
        cardImageSourcePath: item.cardImageSourcePath || '',
        imageAssets: item.imageAssets || [],
        uniform: item.imageOnly || item.virtual ? '' : (item.uniform || ''),
        uniformLabel: item.imageOnly || item.virtual ? '모델 없음' : (item.uniformLabel || ''),
        isMale: item.isMale,
        voiceoverActor: item.voiceoverActor || item.voiceover_actor || '',
        referenceSourcePath: item.referenceSourcePath || '',
        sourcePackName: item.sourcePackName || '',
        sourceIdentity: item.sourceIdentity || '',
        rows: item.rows || [],
        externalImageSet: Boolean(item.externalImageSet),
        imageOnly: Boolean(item.imageOnly || item.virtual),
        virtualImageOnly: Boolean(item.imageOnly || item.virtual),
        hasImage: Boolean(item.portraitImagePath || item.cardImagePath),
      }));
    if (artSets.length) {
      const byKey = new Map(artSets.map((item) => [item.key, item]));
      for (const character of characters().filter((item) => item.virtualImageOnly || item.imageOnly)) {
        const appearance = appearanceFromCharacter(character);
        if (!appearance.key) continue;
        const existing = byKey.get(appearance.key);
        byKey.set(
          appearance.key,
          existing ? mergeImageOnlyAppearance(existing, appearance) : appearance,
        );
      }
      return sortAppearanceSets([...byKey.values()]);
    }
    return sortAppearanceSets(characters().map((item) => appearanceFromCharacter(item)));
  });
}

function modelAppearanceSets() {
  return cachedDerived('modelAppearanceSets', () => {
    const catalog = (state.options?.modelSets || [])
      .filter((item) => item?.key)
      .map((item) => ({
        key: item.key,
        name: modelDisplayName(item),
        element: modelOwnerCharacterFor(item)?.element || '',
        portrait: portraitGlyph(item.label || item.key),
        artSet: item.key,
        imageSetName: displayLabel(item.label, item.key),
        modelSetName: modelDisplayName(item),
        uniform: item.uniform || '',
        uniformLabel: item.uniformLabel || '',
        isMale: item.isMale,
        voiceoverActor: item.voiceoverActor || item.voiceover_actor || '',
        referenceSourcePath: item.referenceSourcePath || '',
        sourcePackName: item.sourcePackName || '',
        sourceIdentity: item.sourceTablePath || item.sourceIdentity || '',
        sourceTag: item.sourceTag || '',
        rows: item.rows || [],
        imageOnly: false,
        virtualImageOnly: false,
        hasImage: false,
      }));
    if (catalog.length) return sortAppearanceSets(catalog.filter(canUseAsModelSet));
    return appearanceSets().filter(canUseAsModelSet);
  });
}

function selectableImageAppearances() {
  return cachedDerived('selectableImageAppearances', () => appearanceSets().filter((item) => {
      if (sourceInfo(item).tag === 'AW') return false;
      if (!item.portraitImagePath && !item.externalImageSet) return false;
      const combined = `${item.artSet || ''} ${item.imageSetName || ''} ${item.portraitPath || ''} ${item.cardPath || ''}`.toLowerCase();
      const referenceSource = String(item.referenceSourcePath || '').toLowerCase();
      const isBfg = item.externalImageSet || referenceSource.includes('bfg_');
      return isBfg || (!combined.includes('generic') && !combined.includes('scripted'));
    }));
}

function mergeImageOnlyAppearance(existing, incoming) {
  const merged = { ...existing, ...incoming };
  const existingName = cleanDisplayCandidate(existing?.name || existing?.imageSetName);
  const existingImageSetName = cleanDisplayCandidate(existing?.imageSetName || existing?.name);
  if (!cleanDisplayCandidate(incoming?.name) && existingName) merged.name = existingName;
  if (!cleanDisplayCandidate(incoming?.imageSetName) && existingImageSetName) merged.imageSetName = existingImageSetName;
  return merged;
}

function sortAppearanceSets(items) {
  return [...items].sort((a, b) => {
    const aImageOnly = Number(Boolean(a.imageOnly || a.virtualImageOnly));
    const bImageOnly = Number(Boolean(b.imageOnly || b.virtualImageOnly));
    if (aImageOnly !== bImageOnly) return aImageOnly - bImageOnly;
    const priorityDiff = sourcePriority(a) - sourcePriority(b);
    if (priorityDiff) return priorityDiff;
    const hasImageDiff = Number(b.hasImage) - Number(a.hasImage);
    if (hasImageDiff) return hasImageDiff;
    return String(a.name || '').localeCompare(String(b.name || ''), 'ko');
  });
}

function appearanceFromCharacter(character) {
  const isImageOnly = Boolean(character?.virtualImageOnly || character?.imageOnly);
  const displayName = imageDisplayName(character);
  return {
    key: isImageOnly ? (character?.key || character?.artSet || '') : (character?.artSet || character?.key || ''),
    name: displayName,
    element: character?.element || 'earth',
    portrait: character?.portrait || '將',
    artSet: character?.artSet || '',
    imageSetName: displayName,
    modelSetName: isImageOnly ? '모델 없음' : (character?.modelSetName || '-'),
    portraitPath: character?.portraitPath || '',
    cardPath: character?.cardPath || '',
    portraitImagePath: character?.portraitImagePath || '',
    portraitImageSourcePath: character?.portraitImageSourcePath || '',
    cardImagePath: character?.cardImagePath || '',
    cardImageSourcePath: character?.cardImageSourcePath || '',
    imageAssets: character?.imageAssets || [],
    uniform: isImageOnly ? '' : (character?.uniform || ''),
    isMale: character?.isMale ?? character?.templateRow?.is_male,
    voiceoverActor: character?.voiceoverActor || character?.templateRow?.voiceover_actor || '',
    referenceSourcePath: character?.referenceSourcePath || '',
    sourcePackName: character?.sourcePackName || '',
    sourceIdentity: character?.sourceIdentity || '',
    cardImageSourcePath: character?.cardImageSourcePath || '',
    rows: character?.rows || [],
    imageOnly: isImageOnly,
    virtualImageOnly: isImageOnly,
    hasImage: Boolean(character?.portraitImagePath || character?.cardImagePath),
  };
}

function appearanceByKey(key) {
  const normalizedKey = String(key || '');
  const lookup = appearanceLookup();
  return lookup.byKey.get(normalizedKey)
    || lookup.byArtSet.get(normalizedKey)
    || appearanceFromCharacter(characterLookup().byKey.get(normalizedKey) || characterLookup().byArtSet.get(normalizedKey));
}

function appearanceLookup() {
  return cachedDerived('appearanceLookup', () => {
    const byKey = new Map();
    const byArtSet = new Map();
    for (const appearance of [...appearanceSets(), ...modelAppearanceSets()]) {
      if (appearance.key && !byKey.has(appearance.key)) byKey.set(appearance.key, appearance);
      if (appearance.artSet && !byArtSet.has(appearance.artSet)) byArtSet.set(appearance.artSet, appearance);
    }
    return { byKey, byArtSet };
  });
}

function imageAssetsFromAppearance(appearance) {
  if (appearance?.imageAssets?.length) {
    const seen = new Set();
    return appearance.imageAssets
      .map((asset) => ({
        path: asset.path,
        sourcePath: asset.sourcePath || '',
      }))
      .filter((asset) => {
        const path = normalizeImageAssetPath(asset.path);
        if (!path || isDuplicateCharacterFolderPath(path) || seen.has(path)) return false;
        seen.add(path);
        return true;
      });
  }
  const assets = [];
  if (appearance?.portraitImagePath) {
    assets.push({
      path: appearance.portraitImagePath,
      sourcePath: appearance.portraitImageSourcePath || '',
    });
  }
  if (appearance?.cardImagePath && appearance.cardImagePath !== appearance.portraitImagePath) {
    assets.push({
      path: appearance.cardImagePath,
      sourcePath: appearance.cardImageSourcePath || '',
    });
  }
  return assets;
}

function normalizeImageAssetPath(path) {
  return String(path || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
}

function gameImageAssetPath(path) {
  const normalized = normalizeImageAssetPath(path);
  const marker = '/ui/characters/';
  const lower = normalized.toLowerCase();
  const index = lower.indexOf(marker);
  if (index >= 0) return normalized.slice(index + 1);
  return normalized;
}

function isDuplicateCharacterFolderPath(path) {
  const parts = normalizeImageAssetPath(path).split('/').filter(Boolean);
  const index = parts.findIndex((part, i) => part === 'characters' && parts[i - 1] === 'ui');
  return index >= 0
    && parts[index + 1]
    && parts[index + 2]
    && parts[index + 1].toLowerCase() === parts[index + 2].toLowerCase();
}

function imageTokenFromAppearance(appearance) {
  return imageFolderName(appearance) || imageFolderFromValue(appearance?.cardPath) || imageFolderFromValue(appearance?.portraitPath);
}

function imageTokenForAsset(appearance, assetPath) {
  const normalized = normalizeImageAssetPath(assetPath).toLowerCase();
  const value = normalized.includes('/stills/unitcards/')
    ? appearance?.cardPath
    : appearance?.portraitPath;
  return String(value || imageTokenFromAppearance(appearance)).replace(/[\\/]+$/, '').split(/[\\/]/).filter(Boolean).pop() || '';
}

function imageFolderName(appearance) {
  return imageFolderFromValue(appearance?.portraitImagePath)
    || imageFolderFromValue(appearance?.cardImagePath)
    || imageFolderFromValue(appearance?.portraitPath)
    || imageFolderFromValue(appearance?.cardPath);
}

function imageFolderFromValue(value) {
  const path = String(value || '').replace(/\\/g, '/').replace(/[\\/]+$/, '');
  const parts = path.split('/').filter(Boolean);
  if (!parts.length) return '';
  const index = parts.lastIndexOf('characters');
  if (index >= 0 && parts[index + 1]) return parts[index + 1];
  const stillsIndex = parts.lastIndexOf('stills');
  if (stillsIndex > 0) return parts[stillsIndex - 1];
  if (parts.length === 1 && !/\.(png|jpg|jpeg|dds)$/i.test(parts[0])) return parts[0];
  return '';
}

function imageDisplayName(item) {
  const info = imageHeroInfo(item);
  const folder = imageFolderName(item);
  return info?.kr
    || cleanDisplayCandidate(item?.name)
    || cleanDisplayCandidate(item?.imageSetName)
    || displayLabel(folder || item?.portraitPath || item?.cardPath, item?.artSet || item?.key)
    || friendlyKey(item?.artSet || item?.key);
}

function imageHeroInfo(item) {
  const direct = sheetHeroInfoFor(item?.key) || sheetHeroInfoFor(item?.artSet);
  if (direct) return direct;
  for (const candidate of imageSlugCandidates(item)) {
    const byAlias = sheetHeroAliasMap()[candidate];
    if (byAlias) return byAlias;
  }
  return null;
}

function imageSlugCandidates(item) {
  const values = [
    item?.key,
    item?.artSet,
    item?.portraitPath,
    item?.cardPath,
    imageFolderName(item),
  ];
  const candidates = new Set();
  for (const value of values) {
    let text = String(value || '').toLowerCase();
    text = text.split(/[\\/]/).filter(Boolean).pop() || text;
    text = text.replace(/\.(png|jpg|jpeg|dds)$/i, '');
    text = text.replace(/^image_only_/, '');
    text = text.replace(/^(aw|lshz)_/i, '');
    text = text.replace(/^(3k_)?(main|mtu|dlc\d+|ep|cp\d+)_hero_special_(earth|fire|wood|water|metal)_/, '');
    text = text.replace(/^lb_main_hero_special_(earth|fire|wood|water|metal)_/, '');
    text = text.replace(/^mh_hero_special_(earth|fire|wood|water|metal)_/, '');
    text = text.replace(/^lady_/, '');
    text = text.replace(/_(hero|general)_(earth|fire|wood|water|metal).*$/, '');
    text = text.replace(/_(earth|fire|wood|water|metal)$/, '');
    if (text) {
      candidates.add(text);
      candidates.add(text.replace(/_/g, ''));
    }
  }
  return [...candidates];
}

function appearanceSearchText(appearance) {
  return [
    appearance?.key,
    appearance?.name,
    appearance?.imageSetName,
    appearance?.artSet,
    imageFolderName(appearance),
    appearance?.portraitImagePath,
    appearance?.cardImagePath,
    appearance?.referenceSourcePath,
    appearance?.portraitImageSourcePath,
    appearance?.cardImageSourcePath,
  ].filter(Boolean).join(' ');
}

function appearanceOption(appearance) {
  const folder = imageFolderName(appearance);
  const folderText = folder && folder !== appearance.artSet ? ` · ${displayLabel(folder, appearance.key)}` : '';
  const artSetLabel = displayLabel(appearance.artSet, appearance.key);
  return option(
    appearance.key,
    `${sourceLabel(appearance)} ${appearance.hasImage ? '■' : '□'} ${displayNameWithDummyMarker(appearance)} · ${artSetLabel}${folderText}`,
    appearanceSearchText(appearance),
  );
}

function modelOptionLabel(item) {
  const gender = item.isMale === true ? '남성' : item.isMale === false ? '여성' : '성별 미확인';
  const owner = modelOwnerCharacterFor(item);
  const elementKey = owner?.element || item.ownerElement || '';
  const elementText = elementKey ? ` · ${elementMeta(elementKey).label} ${elementMeta(elementKey).name}` : ' · 오행 미확인';
  const name = modelDisplayName(item);
  return `${sourceLabel(item)} ${name}${elementText} · ${gender}`;
}

function modelSearchText(item) {
  const gender = item.isMale === true ? '남성 male' : item.isMale === false ? '여성 female' : '';
  return `${item.key || ''} ${item.name || ''} ${item.modelSetName || ''} ${item.uniform || ''} ${modelDisplayName(item)} ${item.sourceIdentity || ''} ${item.element || ''} ${gender}`;
}

function modelDisplayName(item = {}) {
  const owner = modelOwnerCharacterFor(item);
  if (owner?.name) return `${owner.name} 모델`;
  const sheetInfo = sheetHeroInfoFor(item.key) || sheetHeroInfoFor(item.uniform) || sheetHeroInfoFor(item.artSet);
  if (sheetInfo?.kr) return `${sheetInfo.kr} 모델`;
  const candidates = [
    item.modelSetName,
    item.uniformLabel,
    item.name,
    item.label,
    item.uniform,
    item.key,
  ].map((value) => String(value || '').trim()).filter(Boolean);
  for (const value of candidates) {
    const generic = genericModelDisplayName(value);
    if (generic) return generic;
  }
  const readable = cleanedModelSourceName(candidates[0] || item.key || '');
  if (readable) {
    const readableLabel = koreanLabelFromText(readable, item.key) || readable;
    return readableLabel.endsWith('모델') ? readableLabel : `${readableLabel} 모델`;
  }
  const element = elementMeta(item.element || elementFromSubtype(`${item.key || ''} ${item.uniform || ''}`));
  const gender = item.isMale === true ? '남성' : item.isMale === false ? '여성' : '';
  return [gender, element.name, '모델'].filter(Boolean).join(' ');
}

function modelOwnerCharacterFor(item = {}) {
  const key = String(item.key || item.artSet || '');
  const uniform = String(item.uniform || '');
  const lookup = characterLookup();
  const exactArtSet = lookup.byArtSet.get(key);
  if (exactArtSet) return exactArtSet;
  const exactUniform = uniform ? lookup.byUniform.get(uniform) : null;
  if (exactUniform) return exactUniform;
  const normalizedKey = slugFromKey(key);
  if (!normalizedKey) return null;
  return lookup.bySlug.get(normalizedKey) || null;
}

function genericModelDisplayName(value) {
  const generic = genericDisplayName(value);
  if (!generic) return '';
  return `${generic} 기본 모델`;
}

function cleanedModelSourceName(value) {
  const raw = String(value || '').toLowerCase();
  if (!raw) return '';
  const text = raw
    .replace(/^(my|mtu|data|bfg|lshz|aw)\s+/, '')
    .replace(/^(3k_)?(main|mtu|dlc\d+|ep|cp\d+)_/, '')
    .replace(/^(template|art_set|historical|hero|special|character|lady)_+/g, '')
    .replace(/^(lb|mh)_/, '')
    .replace(/^(lady|lord|queen|empress|king)_/, '$1 ')
    .replace(/_(hero|general)_(earth|fire|wood|water|metal).*$/, '')
    .replace(/_(earth|fire|wood|water|metal)$/, '')
    .replace(/_(model|uniform|body|unique|dummy).*$/, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\b(3k|main|mtu|dlc\d+|ep|cp\d+|template|historical|hero|general|special|art|set|model|uniform|body|unique|dummy|male|female|m|f)\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return text;
}

function primaryArtRowFromAppearance(appearance) {
  const rows = Array.isArray(appearance?.rows) ? appearance.rows : [];
  return rows.find((row) => row?.has_come_of_age === true)
    || rows.find((row) => Number(row?.age) >= 16)
    || rows[0]
    || {};
}

function imageArtOverridesFromAppearance(appearance) {
  return compactObject({
    portrait: appearance?.portraitPath,
    card: appearance?.cardPath,
  });
}

function imageCompositeArtOverridesFromAppearance(appearance, targetAssets = []) {
  const row = primaryArtRowFromAppearance(appearance);
  const hasCompositeAsset = (targetAssets.length ? targetAssets : imageAssetsFromAppearance(appearance))
    .some((asset) => /\/composites\/(?:large_panel|small_panel)\//i.test(asset?.targetPath || asset?.path || ''));
  return compactObject({
    fallback_composite_display: row.fallback_composite_display || (hasCompositeAsset ? 'EMPTY' : ''),
  });
}

function imageCardKeyFromAppearance(appearance) {
  const path = String(appearance?.cardImagePath || '').replace(/\\/g, '/').replace(/[\\/]+$/, '');
  const fileName = path.split('/').filter(Boolean).pop() || '';
  const stem = fileName.replace(/\.(png|jpg|jpeg|dds)$/i, '');
  if (stem) return stem;
  return imageFolderFromValue(appearance?.cardPath);
}

function modelArtOverridesFromAppearance(appearance) {
  const row = primaryArtRowFromAppearance(appearance);
  return compactObject({
    uniform: row.uniform || appearance?.uniform,
    land_animation: row.land_animation,
    sea_uniform: row.sea_uniform,
    sea_animation: row.sea_animation,
    navy_uniform: row.navy_uniform,
    navy_animation: row.navy_animation,
    fallback_composite_display: row.fallback_composite_display,
  });
}

function modelGenderOverridesFromAppearance(appearance, fallbackTemplate = {}) {
  const overrides = templateGenderOverridesFromAppearance(appearance, fallbackTemplate);
  if (Object.prototype.hasOwnProperty.call(overrides, 'is_male')) return overrides;
  return overrides;
}

function templateGenderOverridesFromAppearance(appearance, fallbackTemplate = {}) {
  if (!appearance) return {};
  const isMale = appearance.isMale ?? appearance.is_male;
  const overrides = {};
  if (isMale !== undefined && isMale !== null && isMale !== '') {
    overrides.is_male = parseBoolean(isMale);
  }
  if (appearance.voiceoverActor || appearance.voiceover_actor) {
    overrides.voiceover_actor = appearance.voiceoverActor || appearance.voiceover_actor;
  } else if (Object.prototype.hasOwnProperty.call(overrides, 'is_male')) {
    const subtype = String(fallbackTemplate.subtype || '');
    const element = subtype.includes('water') ? 'water'
      : subtype.includes('wood') ? 'wood'
        : subtype.includes('fire') ? 'fire'
          : subtype.includes('metal') ? 'metal'
            : subtype.includes('earth') ? 'earth'
              : 'metal';
    overrides.voiceover_actor = voiceoverActorForGender(overrides.is_male, subtype);
  }
  return overrides;
}
