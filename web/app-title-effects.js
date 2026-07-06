'use strict';

const heroNameCache = new Map();
let titleEffectCacheVersion = -1;
let titleEffectObjectCache = new WeakMap();
const titleEffectKeyCache = new Map();
const catalogTitleEffectLookupCache = new Map();

function resetTitleEffectCachesIfNeeded() {
  const version = state?.dataVersion ?? 0;
  if (titleEffectCacheVersion === version) return;
  titleEffectCacheVersion = version;
  titleEffectObjectCache = new WeakMap();
  titleEffectKeyCache.clear();
  catalogTitleEffectLookupCache.clear();
}

function sheetHeroMap() {
  return window.SHEET_HERO_NAME_MAP || {};
}

function sheetHeroAliasMap() {
  return window.SHEET_HERO_ALIAS_MAP || {};
}

function sheetTitleMap() {
  return window.SHEET_TITLE_NAME_MAP || {};
}

function titleKeyVariants(value) {
  const raw = String(value || '').trim();
  if (!raw) return [];
  const variants = new Set([raw]);
  const clean = raw.replace(/^ceo_nodes_title_/, '').replace(/^ceo_nodes_description_/, '');
  variants.add(clean);
  const withoutNode = clean
    .replace('_ceo_node_career_', '_ceo_career_')
    .replace(/_\d\d$/, '');
  variants.add(withoutNode);
  variants.add(withoutNode.replace('_ceo_career_historical_', '_ceo_career_historical_lady_'));
  variants.add(clean.replace(/_\d\d$/, ''));
  return [...variants].filter(Boolean);
}

function normalizedSheetTitleSlug(value) {
  return slugFromKey(value)
    .replace(/^lady_/, '')
    .replace(/_wenji$/, '')
    .replace(/_bojie$/, '')
    .replace(/_early$/, '');
}

function slugFromKey(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/^3k_[^_]+_template_historical_/, '')
    .replace(/^3k_[^_]+_template_/, '')
    .replace(/^3k_[^_]+_art_set_historical_/, '')
    .replace(/^3k_[^_]+_ceo_(node_)?career_historical_/, '')
    .replace(/_(hero|general)_(earth|fire|wood|water|metal).*$/, '')
    .replace(/_(earth|fire|wood|water|metal)$/, '')
    .replace(/_(0\d|1\d|2\d)$/, '');
}

function sheetHeroInfoFor(key) {
  const cacheKey = String(key || '');
  if (heroNameCache.has(cacheKey)) return heroNameCache.get(cacheKey);
  const byKey = sheetHeroMap()[cacheKey];
  if (byKey) {
    heroNameCache.set(cacheKey, byKey);
    return byKey;
  }
  const slug = slugFromKey(cacheKey);
  const bySlug = sheetHeroAliasMap()[slug];
  if (bySlug) {
    heroNameCache.set(cacheKey, bySlug);
    return bySlug;
  }
  heroNameCache.set(cacheKey, null);
  return null;
}

function sheetHeroInfoForAny(...keys) {
  const candidates = [];
  for (const key of keys) {
    const text = String(key || '').trim();
    if (!text) continue;
    const slug = slugFromKey(text);
    candidates.push(text, slug);
    if (slug.startsWith('lady_')) candidates.push(slug.replace(/^lady_/, ''));
    if (text.includes('lady_')) candidates.push(text.replace(/lady_/g, ''));
  }
  for (const candidate of candidates) {
    const info = sheetHeroInfoFor(candidate);
    if (info) return info;
  }
  for (const candidate of candidates) {
    const tokens = labelTokens(candidate);
    const joined = longestCharacterToken(tokens);
    if (joined && KOREAN_CHARACTER_TOKEN_MAP[joined]) {
      return { kr: KOREAN_CHARACTER_TOKEN_MAP[joined], slug: joined };
    }
    if (joined?.startsWith('lady_')) {
      const withoutLady = joined.replace(/^lady_/, '');
      if (KOREAN_CHARACTER_TOKEN_MAP[withoutLady]) {
        return { kr: KOREAN_CHARACTER_TOKEN_MAP[withoutLady], slug: withoutLady };
      }
    }
  }
  return null;
}

function sheetTitleInfoFor(titleKey, characterKey = '') {
  const titles = sheetTitleMap();
  for (const key of titleKeyVariants(titleKey)) {
    if (titles[key]) return titles[key];
  }
  const slugCandidates = [
    normalizedSheetTitleSlug(characterKey),
    normalizedSheetTitleSlug(titleKey),
    ...titleKeyVariants(titleKey).map(normalizedSheetTitleSlug),
  ].filter(Boolean);
  return Object.values(titles).find((item) => {
    const itemSlug = normalizedSheetTitleSlug(item.slug || '');
    return slugCandidates.some((slug) => itemSlug === slug);
  }) || null;
}

function normalizeKoreanText(value) {
  return String(value || '').replace(/\s+/g, '').replace(/[·:;.,]/g, '').toLowerCase();
}

function normalizeLookupText(value) {
  return String(value || '').replace(/[^0-9a-zA-Z가-힣]+/g, '').toLowerCase();
}

function manualTitleEffectFor(ownerName = '', titleName = '') {
  const owner = normalizeKoreanText(ownerName);
  const title = normalizeKoreanText(titleName);
  const ownerMatches = MANUAL_TITLE_EFFECTS.filter((item) => normalizeKoreanText(item.owner) === owner);
  const titleMatches = MANUAL_TITLE_EFFECTS.filter((item) => {
    const itemTitle = normalizeKoreanText(item.title);
    return itemTitle && title && (itemTitle === title || itemTitle.includes(title) || title.includes(itemTitle));
  });
  if (!ownerMatches.length) return titleMatches.length === 1 ? titleMatches[0] : null;
  const exact = ownerMatches.find((item) => {
    const itemTitle = normalizeKoreanText(item.title);
    return itemTitle && title && (itemTitle === title || itemTitle.includes(title) || title.includes(itemTitle));
  });
  if (exact) return exact;
  const titleMissing = !title || title.includes('미확인');
  return titleMissing && ownerMatches.length === 1 ? ownerMatches[0] : null;
}

function catalogTitleEffectFor(titleName = '') {
  const title = normalizeKoreanText(titleName);
  if (!title) return null;
  resetTitleEffectCachesIfNeeded();
  if (catalogTitleEffectLookupCache.has(title)) return catalogTitleEffectLookupCache.get(title);
  const index = titleCatalogEffectIndex();
  const exact = index.byTitle.get(title);
  if (exact) {
    catalogTitleEffectLookupCache.set(title, exact);
    return exact;
  }
  const matched = index.entries.find((item) => item.title && (item.title.includes(title) || title.includes(item.title)));
  const effect = matched?.effect || null;
  catalogTitleEffectLookupCache.set(title, effect);
  return effect;
}

function titleCatalogEffectIndex() {
  return cachedDerived('titleCatalogEffectIndex', () => {
    const byTitle = new Map();
    const entries = [];
    for (const item of state.options?.titleCatalog || []) {
      const title = normalizeKoreanText(item.label || '');
      const effectSummary = item.effectSummary || (Array.isArray(item.effects) ? item.effects.join(' / ') : '');
      if (!title || !effectSummary) continue;
      const effect = {
        owner: '',
        title: item.label || '',
        effects: effectSummary,
      };
      if (!byTitle.has(title)) byTitle.set(title, effect);
      entries.push({ title, effect });
    }
    return { byTitle, entries };
  });
}

function titleEffectFor(character) {
  if (!character || typeof character !== 'object') return null;
  resetTitleEffectCachesIfNeeded();
  if (titleEffectObjectCache.has(character)) return titleEffectObjectCache.get(character);
  const cacheKey = titleEffectCacheKey(character);
  if (cacheKey && titleEffectKeyCache.has(cacheKey)) {
    const cached = titleEffectKeyCache.get(cacheKey);
    titleEffectObjectCache.set(character, cached);
    return cached;
  }
  const effect = computeTitleEffectFor(character);
  const result = effect || null;
  titleEffectObjectCache.set(character, result);
  if (cacheKey) titleEffectKeyCache.set(cacheKey, result);
  return result;
}

function titleEffectCacheKey(character) {
  return [
    character?.titleChoiceKey,
    character?.key,
    character?.titleName,
    character?.titleOwnerName || character?.name,
    character?.titleEffectTitle,
    character?.titleEffectSummary,
    Array.isArray(character?.titleEffects) ? character.titleEffects.join('|') : '',
    character?.titleCeoKey,
    character?.titleCareerCeoKey,
    character?.titleInitialCeoKey,
    character?.titleKey,
    character?.manualTitleEffect ? `${character.manualTitleEffect.title || ''}:${character.manualTitleEffect.effects || ''}` : '',
  ].filter(Boolean).join('::');
}

function computeTitleEffectFor(character) {
  const embeddedSummary = character?.titleEffectSummary || (Array.isArray(character?.titleEffects) ? character.titleEffects.join(' / ') : '');
  if (embeddedSummary) {
    return {
      owner: character?.titleOwnerName || character?.name || '',
      title: character?.titleName || '칭호',
      effects: embeddedSummary,
    };
  }
  if (character?.manualTitleEffect) return character.manualTitleEffect;
  const manual = manualTitleEffectFor(character?.titleOwnerName || character?.name, character?.titleName);
  if (manual) return manual;
  return catalogTitleEffectFor(character?.titleName);
}

const TITLE_STAT_FILTERS = {
  all: { label: '전체', aliases: [] },
  authority: { label: '권위', aliases: ['권위'] },
  instinct: { label: '본능', aliases: ['본능'] },
  cunning: { label: '책략', aliases: ['책략', '지략'] },
  expertise: { label: '전문성', aliases: ['전문성'] },
  resolve: { label: '결의', aliases: ['결의'] },
};

const TITLE_ELEMENT_TO_STAT_FILTER = {
  earth: 'authority',
  fire: 'instinct',
  water: 'cunning',
  metal: 'expertise',
  wood: 'resolve',
};

function normalizeTitleStatFilter(filter) {
  const key = String(filter || 'all').trim();
  return TITLE_STAT_FILTERS[key] ? key : 'all';
}

function titleEffectTextForChoice(character, effect = titleEffectFor(character)) {
  return String(
    effect?.effects
    || character?.titleEffectSummary
    || (Array.isArray(character?.titleEffects) ? character.titleEffects.join(' / ') : '')
    || '',
  ).trim();
}

function splitTitleEffectText(effectText = '') {
  const pieces = String(effectText || '')
    .replace(/\s*[·]\s*/g, ' / ')
    .split(/\s*\/\s*/)
    .map((item) => item.trim())
    .filter(Boolean);
  const statPattern = /(권위|본능|책략|지략|전문성|결의)\s*[+-]?\s*\d+/;
  const statParts = pieces.filter((item) => statPattern.test(item));
  const coreParts = pieces.filter((item) => !statPattern.test(item));
  return {
    stats: statParts.length ? statParts.join(', ') : (pieces[0] || ''),
    core: statParts.length ? coreParts.join(' / ') : pieces.slice(1).join(' / '),
  };
}

function looksLikeGenericTitleDisplay(value) {
  const text = String(value || '').trim();
  if (!text || text === '칭호 미확인') return true;
  if (/기본\s*칭호/.test(text)) return true;
  if (looksLikeInternalKey(text) || looksLikeSlugLabel(text)) return true;
  return false;
}

function titleDisplayNameForChoice(character, effect = titleEffectFor(character)) {
  const key = character?.titleKey || character?.titleInitialCeoKey || character?.titleCeoKey || character?.key || '';
  const translatedTitle = character?.titleName && character.titleName !== '칭호 미확인'
    ? displayTitleLabel(character.titleName, key)
    : displayTitleLabel('', key);
  const candidates = [
    character?.titleEffectTitle,
    effect?.title,
    character?.manualTitleEffect?.title,
    translatedTitle,
    character?.titleName,
  ];
  for (const candidate of candidates) {
    const text = String(candidate || '').trim();
    if (text && !looksLikeGenericTitleDisplay(text)) return text;
  }
  return fallbackTitleDisplayName(translatedTitle, key, character?.titleOwnerName || character?.name);
}

function titleEffectDisplayParts(character) {
  const effect = titleEffectFor(character);
  const title = titleDisplayNameForChoice(character, effect);
  const { stats, core } = splitTitleEffectText(titleEffectTextForChoice(character, effect));
  return {
    title,
    stats,
    core,
    detail: [stats, core].filter(Boolean).join(' / '),
  };
}

function titleDisplayDedupeKey(character) {
  const parts = titleEffectDisplayParts(character);
  const title = normalizeKoreanText(parts.title);
  const stats = normalizeKoreanText(parts.stats);
  const core = normalizeKoreanText(parts.core);
  return [title, stats, core].filter(Boolean).join('|');
}

function titleChoiceMatchesStatFilter(character, filter = 'all') {
  const filterKey = normalizeTitleStatFilter(filter);
  if (filterKey === 'all') return true;
  const aliases = TITLE_STAT_FILTERS[filterKey].aliases;
  const effectText = titleEffectTextForChoice(character);
  const { stats } = splitTitleEffectText(effectText);
  const hasStatBonus = aliases.some((alias) => new RegExp(`${alias}\\s*[+-]?\\s*\\d+`).test(effectText));
  if (hasStatBonus || aliases.some((alias) => stats.includes(alias))) return true;
  return titleElementsForChoice(character).some((element) => TITLE_ELEMENT_TO_STAT_FILTER[element] === filterKey);
}

function escapeTitleStatAlias(value) {
  return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function titleStatValueForFilter(character, filter = 'all') {
  const filterKey = normalizeTitleStatFilter(filter);
  if (filterKey === 'all') return 0;
  const aliases = TITLE_STAT_FILTERS[filterKey]?.aliases || [];
  const effectText = titleEffectTextForChoice(character);
  let best = null;
  aliases.forEach((alias) => {
    const pattern = new RegExp(`${escapeTitleStatAlias(alias)}\\s*([+-]?\\s*\\d+)`, 'g');
    let match = pattern.exec(effectText);
    while (match) {
      const value = Number(String(match[1] || '').replace(/\s+/g, ''));
      if (Number.isFinite(value)) best = best === null ? value : Math.max(best, value);
      match = pattern.exec(effectText);
    }
  });
  if (best !== null) return best;
  return titleChoiceMatchesStatFilter(character, filterKey) ? 0 : Number.NEGATIVE_INFINITY;
}

function manualSkillEffectFor(infoOrKey = '') {
  const key = typeof infoOrKey === 'string' ? infoOrKey : infoOrKey?.key;
  const name = typeof infoOrKey === 'string' ? '' : infoOrKey?.name;
  const haystack = normalizeLookupText(`${name || ''} ${friendlyKey(key || '')} ${key || ''}`);
  if (!haystack) return null;
  return MANUAL_SKILL_EFFECTS.find((item) => {
    const needles = [item.name, ...(item.aliases || [])].map((value) => normalizeLookupText(value)).filter(Boolean);
    return needles.some((needle) => haystack.includes(needle) || needle.includes(haystack));
  }) || null;
}

function needsManualSkillEffect(info) {
  const text = `${info?.description || ''} ${info?.effectSummary || ''}`;
  if (!text.trim()) return true;
  if (text.includes('효과 정보')) return true;
  if (/[a-z]{3,}[_ ][a-z]{3,}/i.test(text)) return true;
  return false;
}

function enrichedSkillInfo(infoOrKey) {
  const base = typeof infoOrKey === 'string'
    ? (skillTreesData().skillIndex?.[infoOrKey] || {
        key: infoOrKey,
        name: friendlyKey(infoOrKey),
        description: '',
        effectSummary: '',
        element: '',
      })
    : (infoOrKey || {});
  const manual = manualSkillEffectFor(base);
  if (!manual) return base;
  return {
    ...base,
    name: base.name && !String(base.name).includes('_') ? base.name : manual.name,
    effectSummary: needsManualSkillEffect(base) ? manual.effects : (base.effectSummary || manual.effects),
    manualEffect: manual.effects,
  };
}

function titleOptionLabel(character) {
  const { title, detail } = titleEffectDisplayParts(character);
  return [title, detail].filter(Boolean).join(' - ');
}

function sortTitleCandidates(items) {
  return titleCandidateSortRows(items)
    .sort((a, b) => {
      if (a.hasEffect !== b.hasEffect) return b.hasEffect - a.hasEffect;
      if (a.hasTranslated !== b.hasTranslated) return b.hasTranslated - a.hasTranslated;
      return a.name.localeCompare(b.name, 'ko');
    })
    .map((row) => row.item);
}

function titleCandidateSortRows(items) {
  return (items || []).map((item) => ({
    item,
    hasEffect: Number(Boolean(titleEffectFor(item))),
    hasTranslated: Number(Boolean(item.titleName && item.titleName !== '칭호 미확인')),
    name: String(item.name || item.titleName || ''),
  }));
}

function sortTitleCandidatesForFilter(items, filter = 'all') {
  const filterKey = normalizeTitleStatFilter(filter);
  if (filterKey === 'all') return sortTitleCandidates(items);
  const baseOrder = new Map(sortTitleCandidates(items).map((item, index) => [item, index]));
  const statScores = new Map((items || []).map((item) => [item, titleStatValueForFilter(item, filterKey)]));
  return [...items].sort((a, b) => {
    const aScore = statScores.get(a) ?? Number.NEGATIVE_INFINITY;
    const bScore = statScores.get(b) ?? Number.NEGATIVE_INFINITY;
    if (aScore !== bScore) return bScore - aScore;
    return (baseOrder.get(a) ?? 0) - (baseOrder.get(b) ?? 0);
  });
}
