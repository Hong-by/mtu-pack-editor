'use strict';

function hydrateFromPackData(characterData, responseEnvelope = {}) {
  const summary = characterData?.pack;
  if (!summary?.characters?.length) return;
  state.options = summary;
  state.dedicatedArmour = responseEnvelope.dedicatedArmour || null;
  state.characters = summary.characters.map((item) => normalizePackCharacter(item, summary));
  for (const character of state.characters) {
    if (!hasKoreaUniquePortrait(character)) continue;
    const artSet = summary.artSets.find(item => item.key === character.artSet);
    const label = `${character.name} 이미지 세트`;
    character.imageSetName = label;
    if (artSet) artSet.label = label;
  }
  bumpDataVersion();
  state.assetCacheVersion = responseEnvelope.assetCacheToken
    || characterData.assetCacheToken
    || summary.assetCacheToken
    || `data-${state.dataVersion}`;
  const firstBrowsable = browsableCharacters()[0] || selectableFallbackCharacters()[0] || state.characters.find(hasRealTemplateRow);
  state.selectedKey = realTemplateKey(firstBrowsable) || '';
  state.editingQueueIndex = null;
  state.skillTreeDrafts = {};
  state.activeSkillNode = null;
}

function normalizePackCharacter(item, summary) {
  const historical = item.details.find((detail) => detail.gameMode === 'historical') || item.details[0] || {};
  const romance = item.details.find((detail) => detail.gameMode === 'romance') || historical;
  const element = elementFromSubtype(item.subtype);
  const artSet = summary.artSets.find((candidate) => candidate.key === item.artSet);
  const combatStats = item.combatStats || {};
  const armourCeo = runtimeArmourCeoKey(combatStats.armourCeo);
  const titleInfo = item.titleInfo || {};
  const sheetHero = sheetHeroInfoForAny(
    item.key,
    item.templateRow?.key,
    item.artSet,
    item.displayName,
    item.label,
  );
  const isImageOnly = Boolean(item.imageOnly || item.virtualImageOnly);
  const imageNameFallback = isImageOnly
    ? (artSet?.label || item.portrait || item.card || item.artSet || item.key)
    : item.key;
  const localizedName = item.label || item.displayName || '';
  const usableLocalizedName = hasHangul(localizedName) || (!sheetHero?.kr && isKoreaRosterCharacter(item) && /[\u3400-\u9fff]/.test(localizedName));
  const displayName = !isImageOnly && usableLocalizedName && !looksLikeInternalKey(localizedName) ? localizedName : (sheetHero?.kr || displayLabel(item.label || item.displayName, imageNameFallback));
  const sheetTitle = sheetTitleInfoFor(titleInfo.ceoNodeKey || titleInfo.initialCeoKey || '', item.key);
  const koreaTitleOverride = koreaTitleOverrideFor(item, titleInfo);
  const resolvedTitleName = koreaTitleOverride || displayTitleLabel(titleInfo.label, titleInfo.ceoNodeKey || titleInfo.initialCeoKey || '', sheetTitle?.krTitle);
  const manualTitle = manualTitleEffectFor(displayName, resolvedTitleName);
  const spawnEvent = 'round_pool';
  const rosterSearchText = normalizeLookupText([
    displayName,
    item.key,
    resolvedTitleName,
    item.artSet,
    artSet?.label,
    item.uniformLabel,
    artSet?.uniformLabel,
    historical.skillSet,
    romance.skillSet,
    historical.retinue,
    romance.retinue,
    historical.attributeSet,
    romance.attributeSet,
    combatStats.weaponCeo,
    armourCeo,
    combatStats.landUnitKey,
    item.subtype,
    element,
    spawnEventMeta(spawnEvent).name,
    item.koreaFactionLabel,
    item.koreaRole,
    item.sourceTag,
    item.sourcePackName,
    item.sourceIdentity,
  ].filter(Boolean).join(' '));
  return {
    key: item.key,
    name: displayName,
    englishName: sheetHero?.en || item.displayName || item.label || '',
    hanjaName: sheetHero?.hanja || '',
    element,
    portrait: portraitGlyph(displayName || item.key),
    artSet: item.artSet || '',
    imageSetName: displayLabel(artSet?.label, item.artSet || item.portrait || item.card || item.key),
    modelSetName: displayLabel(item.uniformLabel || artSet?.uniformLabel || item.uniform || artSet?.uniform, item.artSet || item.key),
    historicalSkill: historical.skillSet || '-',
    romanceSkill: romance.skillSet || historical.skillSet || '-',
    retinue: historical.retinue || romance.retinue || '-',
    attributeSet: historical.attributeSet || romance.attributeSet || '-',
    attributeStats: item.attributeStats || {},
    combatProfile: combatStats.weaponCeo || armourCeo || historical.initialCeos || romance.initialCeos || '장비 정보 미확인',
    titleName: resolvedTitleName || manualTitle?.title || '칭호 미확인',
    titleOwnerName: sheetTitle?.krName || manualTitle?.owner || displayName,
    titleDescription: titleInfo.description || '',
    titleKey: titleInfo.ceoNodeKey || '',
    titleCeoKey: titleInfo.titleCeoKey || '',
    titleCareerCeoKey: titleInfo.titleCeoKey || '',
    titleEffectSummary: titleInfo.effectSummary || '',
    titleInitialCeoKey: titleInfo.initialCeoKey || '',
    titleLocKey: titleInfo.locTitleKey || '',
    titleStatus: titleInfo.status || 'read_only_spike',
    titleNote: titleInfo.note || 'set_title 쓰기는 검증 필요',
    baseAttack: nullableNumber(combatStats.baseAttack),
    baseDefense: nullableNumber(combatStats.baseDefense),
    weaponCeo: combatStats.weaponCeo || '',
    weaponStatKey: combatStats.weaponStatKey || '',
    weaponDamage: nullableNumber(combatStats.weaponDamage),
    weaponApDamage: nullableNumber(combatStats.weaponApDamage),
    weaponType: combatStats.weaponType || '',
    missileWeaponStatKey: combatStats.missileWeaponStatKey || '',
    projectileStatKey: combatStats.projectileStatKey || '',
    projectileDamage: nullableNumber(combatStats.projectileDamage),
    projectileApDamage: nullableNumber(combatStats.projectileApDamage),
    projectileRange: nullableNumber(combatStats.projectileRange),
    armourCeo,
    armourStatKey: combatStats.armourStatKey || '',
    armourAudioType: combatStats.armourAudioType || '',
    armourFromReference: Boolean(combatStats.armourFromReference),
    landUnitKey: combatStats.landUnitKey || '',
    unitMeleeAttack: nullableNumber(combatStats.unitMeleeAttack),
    unitMeleeDefence: nullableNumber(combatStats.unitMeleeDefence),
    unitChargeBonus: nullableNumber(combatStats.unitChargeBonus),
    unitDismountedMeleeAttack: nullableNumber(combatStats.unitDismountedMeleeAttack),
    unitDismountedChargeBonus: nullableNumber(combatStats.unitDismountedChargeBonus),
    unitMorale: nullableNumber(combatStats.unitMorale),
    unitPrimaryAmmo: nullableNumber(combatStats.unitPrimaryAmmo),
    unitCategory: combatStats.unitCategory || '',
    unitClass: combatStats.unitClass || '',
    unitFromReference: Boolean(combatStats.unitFromReference),
    unitReferenceSource: combatStats.unitReferenceSource || '',
    sourceRetinueKey: combatStats.sourceRetinueKey || '',
    unitProfile: historical.retinue || romance.retinue || '-',
    weight: Number(item.weight ?? 0),
    minRound: Number(item.minSpawnRound ?? 0),
    maxRound: Number(item.maxSpawnRound ?? 999),
    spawnAge: item.ageRange || '-',
    birthYear: birthYearForAgeRange(item.ageRange),
    spawnEvent,
    rosterSearchText,
    rosterFactions: item.rosterFactions || [],
    templateRow: item.templateRow || {},
    details: item.details || [],
    portraitPath: item.portrait || artSet?.portrait || '',
    cardPath: item.card || artSet?.card || '',
    portraitImagePath: item.portraitImagePath || artSet?.portraitImagePath || '',
    portraitImageSourcePath: item.portraitImageSourcePath || artSet?.portraitImageSourcePath || '',
    cardImagePath: item.cardImagePath || artSet?.cardImagePath || '',
    cardImageSourcePath: item.cardImageSourcePath || artSet?.cardImageSourcePath || '',
    imageAssets: item.imageAssets || artSet?.imageAssets || [],
    imageCatalogEligible: item.imageCatalogEligible ?? artSet?.imageCatalogEligible,
    imageCatalogIssues: item.imageCatalogIssues || artSet?.imageCatalogIssues || [],
    imageContentSignature: item.imageContentSignature || artSet?.imageContentSignature || '',
    hasImage: Boolean(item.portraitImagePath || item.cardImagePath || artSet?.portraitImagePath || artSet?.cardImagePath),
    uniform: item.uniform || artSet?.uniform || '',
    uniformLabel: item.uniformLabel || artSet?.uniformLabel || '',
    isMale: item.isMale ?? artSet?.isMale ?? item.templateRow?.is_male,
    voiceoverActor: item.voiceoverActor || item.templateRow?.voiceover_actor || '',
    source: item.source || 'pack',
    referenceSourcePath: item.referenceSourcePath || '',
    sourceTag: item.sourceTag || '',
    sourcePackName: item.sourcePackName || '',
    sourceIdentity: item.sourceIdentity || '',
    imageOnly: Boolean(item.imageOnly),
    virtualImageOnly: Boolean(item.virtualImageOnly),
    rosterHidden: Boolean(item.rosterHidden),
    koreaRosterHidden: Boolean(item.koreaRosterHidden),
    koreaHiddenReason: item.koreaHiddenReason || '',
    externalImageSet: Boolean(item.externalImageSet),
    isKoreaAddon: Boolean(item.isKoreaAddon),
    koreaFaction: item.koreaFaction || '',
    koreaFactionKey: item.koreaFactionKey || '',
    koreaFactionLabel: item.koreaFactionLabel || '',
    koreaRole: item.koreaRole || '',
    koreaSubtype: item.koreaSubtype || '',
    koreaSourceScript: item.koreaSourceScript || '',
  };
}

function runtimeArmourCeoKey(value) {
  const key = String(value || '').trim();
  if (!key) return '';
  return key;
}
