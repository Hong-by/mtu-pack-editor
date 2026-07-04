'use strict';

function slugify(value) {
  const ascii = String(value || 'custom')
    .normalize('NFKD')
    .replace(/[^\w\s-]/g, '')
    .trim()
    .replace(/[\s-]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .toLowerCase();
  return ascii || `custom_${Date.now()}`;
}

function shortImageWorkToken(prefix, slug, itemNumber) {
  const stopWords = new Set(['3k', 'main', 'mod', 'mtu', 'dlc', 'ep', 'cp', 'template', 'historical', 'romance', 'hero', 'general', 'character']);
  const words = slugify(slug)
    .split('_')
    .filter((word) => word && !/^\d+$/.test(word) && !stopWords.has(word));
  const meaningful = words.slice(-4).join('_') || 'work';
  const suffix = `_${itemNumber}`;
  const maxLength = 48;
  const baseLimit = Math.max(4, maxLength - prefix.length - suffix.length - 1);
  const base = meaningful.slice(0, baseLimit).replace(/_+$/g, '') || 'work';
  return `${prefix}_${base}${suffix}`;
}

function detailOverrideFromSources(attribute, unit, retinueOverride = null) {
  const overrides = {};
  const attributeDetails = detailsByMode(attribute);
  const unitDetails = detailsByMode(unit);
  const unitRetinue = retinueKeyForCharacter(unit);
  for (const mode of ['historical', 'romance']) {
    overrides[mode] = compactObject({
      retinue: retinueOverride || unitDetails[mode]?.retinue || unitRetinue,
      attribute_set: attributeDetails[mode]?.attributeSet || attribute?.attributeSet,
    });
  }
  return overrides;
}

function skillSetOverridesFromCharacter(character) {
  const details = detailsByMode(character);
  const historical = details.historical?.skillSet || character?.historicalSkill || details.romance?.skillSet || character?.romanceSkill;
  const romance = details.romance?.skillSet || character?.romanceSkill || historical;
  return {
    historical: compactObject({ skill_set_override: historical }),
    romance: compactObject({ skill_set_override: romance }),
  };
}

function mergeSkillSetOverrides(detailOverrides, skillSource) {
  const skillOverrides = skillSetOverridesFromCharacter(skillSource);
  return {
    historical: compactObject({
      ...(detailOverrides?.historical || {}),
      ...skillOverrides.historical,
    }),
    romance: compactObject({
      ...(detailOverrides?.romance || {}),
      ...skillOverrides.romance,
    }),
  };
}

function skillSetCloneFromPayload(recipe, snapshot, ownerKey, index, options = {}) {
  const replacements = Object.entries(snapshot?.replacements || {})
    .filter(([, skillKey]) => skillKey);
  if (!snapshot?.sourceSetKey || !replacements.length) return '';
  const newSetKey = options.keepSourceKey
    ? snapshot.sourceSetKey
    : `hby_skillset_romance_${slugify(ownerKey)}_${index}`;
  recipe.skillSetClones.push({
    sourceSetKey: snapshot.sourceSetKey,
    newSetKey,
    replacements: replacements.map(([nodeKey, skillKey]) => ({ nodeKey, skillKey })),
  });
  return newSetKey;
}

function ceoSetRecipeFields(payload) {
  const fields = {};
  if (payload?.traitSet?.addCeos?.length) {
    fields.traitSetKey = payload.traitSet.setKey;
    fields.traitCeoKeys = payload.traitSet.addCeos;
    fields.removableTraitCeoKeys = payload.traitSet.removeCeos || [];
  }
  if (payload?.equipmentSet?.addCeos?.length) {
    fields.equipmentSetKey = payload.equipmentSet.setKey;
    fields.equipmentCeoKeys = payload.equipmentSet.addCeos;
    fields.removableEquipmentCeoKeys = payload.equipmentSet.removeCeos || [];
  }
  return fields;
}

function pushEquipmentStatPatch(recipe, patch) {
  if (!patch?.equipmentKey || !patch?.statTable || !patch?.column) return;
  const item = {
    equipmentKey: patch.equipmentKey,
    statTable: patch.statTable,
    column: patch.column,
    value: patch.value,
  };
  const existing = recipe.equipmentStatPatches.find((candidate) => (
    candidate.equipmentKey === item.equipmentKey
    && candidate.statTable === item.statTable
    && candidate.column === item.column
    && (candidate.gameMode || '') === (item.gameMode || '')
  ));
  if (existing) {
    existing.value = item.value;
    return;
  }
  recipe.equipmentStatPatches.push(item);
}

function cleanTitleCeoLikeKey(value) {
  return String(value || '').trim()
    .replace(/^ceo_nodes_title_/, '')
    .replace(/^ceo_nodes_description_/, '');
}

function titleCareerCeoKeyFromValue(value) {
  const clean = cleanTitleCeoLikeKey(value);
  if (!clean) return '';
  const key = clean
    .replace('_ceo_node_career_', '_ceo_career_')
    .replace('_ceo_initial_data_character_historical_', '_ceo_career_historical_')
    .replace('_ceo_initial_data_character_romance_', '_ceo_career_historical_')
    .replace('_ceo_initial_data_character_', '_ceo_career_historical_')
    .replace(/_\d\d$/, '');
  if (isBackgroundTitleCeoKey(key)) return key;
  if (!/_ceo_career_/i.test(key)) return '';
  return key;
}

function isBackgroundTitleCeoKey(key) {
  return /^bg_/i.test(String(key || '')) && /character_background/i.test(String(key || ''));
}

function titleCeoKeyFromChoice(titleSource) {
  const candidates = [
    titleSource?.titleCareerCeoKey,
    titleSource?.titleKey,
    titleSource?.ceoNodeKey,
    titleSource?.titleCeoKey,
    titleSource?.ceoKey,
    titleSource?.titleInitialCeoKey,
  ];
  return candidates.map(titleCareerCeoKeyFromValue).find(Boolean) || '';
}

function knownInitialCeoKeys() {
  return cachedDerived('knownInitialCeoKeys', () => new Set((state.options?.initialCeos || [])
    .map((item) => String(item?.key || '').trim())
    .filter(Boolean)));
}

function titleInitialCeoAliasCandidates(initialCeoKey) {
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

function historicalInitialCeoToken(initialCeoKey) {
  const key = String(initialCeoKey || '').trim();
  const marker = '_ceo_initial_data_character_historical_';
  const index = key.indexOf(marker);
  return index >= 0 ? key.slice(index + marker.length).replace(/^_+|_+$/g, '').toLowerCase() : '';
}

function stripInitialCeoTokenNoise(token) {
  return String(token || '').replace(/^non_deployable_/i, '').replace(/^deployable_/i, '').toLowerCase();
}

function stripInitialCeoElementSuffix(token) {
  return String(token || '').replace(/_(earth|fire|metal|water|wood)$/i, '').toLowerCase();
}

function initialCeoTokenMatchScore(requestedToken, candidateToken) {
  const requested = stripInitialCeoTokenNoise(requestedToken);
  const candidate = stripInitialCeoTokenNoise(candidateToken);
  if (!requested || !candidate) return 0;
  if (requested === candidate) return 100;
  if (candidate.endsWith(`_${requested}`) || candidate === requested) return 92;
  if (requested.endsWith(`_${candidate}`) && candidate.split('_').length >= 2) return 82;
  const requestedWithoutElement = stripInitialCeoElementSuffix(requested);
  const candidateWithoutElement = stripInitialCeoElementSuffix(candidate);
  if (requestedWithoutElement && requestedWithoutElement === candidateWithoutElement) return 78;
  if (requestedWithoutElement && candidateWithoutElement.endsWith(`_${requestedWithoutElement}`)) return 74;
  if (candidateWithoutElement && requestedWithoutElement.endsWith(`_${candidateWithoutElement}`) && candidateWithoutElement.split('_').length >= 2) return 68;
  return 0;
}

function closestKnownTitleInitialCeoKey(initialCeoKey) {
  const requestedToken = historicalInitialCeoToken(initialCeoKey);
  if (!requestedToken) return '';
  let bestScore = 0;
  let bestKeys = [];
  for (const key of knownInitialCeoKeys()) {
    const score = initialCeoTokenMatchScore(requestedToken, historicalInitialCeoToken(key));
    if (score > bestScore) {
      bestScore = score;
      bestKeys = [key];
    } else if (score && score === bestScore) {
      bestKeys.push(key);
    }
  }
  return bestKeys.length === 1 ? bestKeys[0] : '';
}

function knownTitleInitialCeoKey(initialCeoKey) {
  const candidates = titleInitialCeoAliasCandidates(initialCeoKey);
  if (!candidates.length) return '';
  const known = knownInitialCeoKeys();
  if (!known.size) return candidates[0];
  return candidates.find((candidate) => known.has(candidate))
    || closestKnownTitleInitialCeoKey(initialCeoKey)
    || '';
}

function titleInitialCeoKeyFromCareerCeoKey(titleCeoKey) {
  const key = String(titleCeoKey || '').trim();
  if (!/_ceo_career_historical_/i.test(key)) return '';
  return knownTitleInitialCeoKey(key.replace('_ceo_career_historical_', '_ceo_initial_data_character_historical_'));
}

function titleInitialCeoKeyFromValue(value) {
  const key = cleanTitleCeoLikeKey(value);
  if (!key || isBackgroundTitleCeoKey(key)) return '';
  if (/_ceo_initial_data_character_/i.test(key)) return knownTitleInitialCeoKey(key);
  return titleInitialCeoKeyFromCareerCeoKey(titleCareerCeoKeyFromValue(key));
}

function titleCeoRecipeFields(titleSource, currentTitleSource = null) {
  const titleCeoKey = titleCeoKeyFromChoice(titleSource);
  if (!titleCeoKey) return {};
  const currentTitleCeoKey = titleCeoKeyFromChoice(currentTitleSource);
  if (currentTitleCeoKey && currentTitleCeoKey === titleCeoKey) return {};
  return compactObject({
    titleCeoKey,
    removableTitleCeoKeys: currentTitleCeoKey && currentTitleCeoKey !== titleCeoKey
      ? [currentTitleCeoKey]
      : [],
  });
}

function titleInitialCeoForModeFromChoice(titleSource, mode) {
  const titleCeoKey = titleCeoKeyFromChoice(titleSource);
  if (isBackgroundTitleCeoKey(titleCeoKey)) return null;
  return titleInitialCeoKeyFromValue(titleSource?.details?.find((detail) => detail.gameMode === mode && detail.initialCeos)?.initialCeos)
    || titleInitialCeoKeyFromValue(titleSource?.titleInitialCeoKey)
    || titleInitialCeoKeyFromValue(titleSource?.details?.find((detail) => detail.initialCeos)?.initialCeos)
    || titleInitialCeoKeyFromCareerCeoKey(titleCeoKey)
    || null;
}

function defaultTitleChoiceForCharacter(character) {
  if (!character) return null;
  return allTitleChoices().find((item) => item.key === character.key)
    || allTitleChoices().find((item) => item.key === realTemplateKey(character))
    || character;
}

function titleChoiceChanged(titleSource, defaultTitleSource) {
  const selected = titleCeoKeyFromChoice(titleSource)
    || titleInitialCeoForModeFromChoice(titleSource, 'historical')
    || titleInitialCeoForModeFromChoice(titleSource, 'romance');
  const baseline = titleCeoKeyFromChoice(defaultTitleSource)
    || titleInitialCeoForModeFromChoice(defaultTitleSource, 'historical')
    || titleInitialCeoForModeFromChoice(defaultTitleSource, 'romance');
  return Boolean(selected && baseline && selected !== baseline);
}

function recipeFromQueue() {
  const recipe = {
    modName: 'mtu_custom_character_workflow',
    workItems: [],
    characterPatches: [],
    characterCloneRecipes: [],
    equipmentStatPatches: [],
    armourTypeClones: [],
    landUnitClones: [],
    skillSetClones: [],
    attributeSetClones: [],
    ageRangeClones: [],
  };

  state.queue.forEach((item, index) => {
    const before = recipeSliceCursor(recipe);
    if (item.kind === 'patch_character') {
      const payload = item.payload;
      const itemNumber = queueWorkNumber(item, index);
      const workSlug = queueWorkSlug(item, index, payload.targetKey);
      const targetCharacter = characters().find((candidate) => realTemplateKey(candidate) === payload.targetKey || candidate.key === payload.targetKey);
      const imageSet = appearanceByKey(payload.imageSetKey);
      const hasAppearanceOverride = Boolean(imageSet);
      const patchArtSetId = '';
      const attribute = resolveAttributeChoice(payload.attributeSetSourceKey);
      const titleSource = resolveTitleChoice(payload.titleSourceKey);
      const skillSource = characters().find((candidate) => candidate.key === payload.skillSourceKey)
        || targetCharacter;
      const unit = characters().find((candidate) => candidate.key === payload.unitProfileSourceKey)
        || targetCharacter;
      const retinueOverride = payload.unitStatClone?.newRetinueKey || null;
      const patchImageToken = shortImageWorkToken('hby_patch', workSlug, itemNumber);
      const targetImageToken = imageSet
        ? patchImageToken
        : (payload.targetImageToken || imageTokenFromAppearance(appearanceFromCharacter(targetCharacter)));
      const targetCardToken = imageSet
        ? patchImageToken
        : (imageCardKeyFromAppearance(appearanceFromCharacter(targetCharacter)) || targetImageToken);
      const patchImageAssets = imageSet
        ? customImageAssetsFromAppearance(imageSet, targetImageToken, targetCardToken)
        : [];
      const patchImageArtKeys = imageSet
        ? artImageKeysFromTargetAssets(patchImageAssets, targetImageToken)
        : {};
      if (payload.attributeSetClone) {
        recipe.attributeSetClones.push({
          sourceSetKey: payload.attributeSetClone.sourceSetKey,
          newSetKey: payload.attributeSetClone.newSetKey,
          overrides: payload.attributeSetClone.overrides,
        });
      }
      if (payload.ageRangeClone) {
        recipe.ageRangeClones.push({
          sourceKey: payload.ageRangeClone.sourceKey,
          newKey: payload.ageRangeClone.newKey,
          overrides: payload.ageRangeClone.overrides,
        });
      }
      if (payload.unitStatClone) {
        recipe.landUnitClones.push({
          sourceKey: payload.unitStatClone.sourceKey,
          newKey: payload.unitStatClone.newKey,
          sourceRetinueKey: payload.unitStatClone.sourceRetinueKey,
          newRetinueKey: payload.unitStatClone.newRetinueKey,
          overrides: payload.unitStatClone.overrides,
        });
      }
      const attributeSetOverride = payload.attributeSetClone?.newSetKey;
      const defaultTitleSource = defaultTitleChoiceForCharacter(targetCharacter);
      const detailOverrides = mergeSkillSetOverrides({
        historical: compactObject({
          retinue: retinueOverride || detailsByMode(unit).historical?.retinue || unit?.unitProfile,
          attribute_set: attributeSetOverride || detailsByMode(attribute).historical?.attributeSet || attribute?.attributeSet,
        }),
        romance: compactObject({
          retinue: retinueOverride || detailsByMode(unit).romance?.retinue || unit?.unitProfile,
          attribute_set: attributeSetOverride || detailsByMode(attribute).romance?.attributeSet || attribute?.attributeSet,
        }),
      }, skillSource);
      const patchSkillSetOverride = skillSetCloneFromPayload(recipe, payload.skillTree, payload.targetKey, itemNumber);
      if (patchSkillSetOverride) {
        detailOverrides.romance = compactObject({
          ...detailOverrides.romance,
          skill_set_override: patchSkillSetOverride,
        });
      }
      if (titleChoiceChanged(titleSource, defaultTitleSource)) {
        for (const mode of ['historical', 'romance']) {
          const titleInitial = titleInitialCeoForModeFromChoice(titleSource, mode);
          if (titleInitial) {
            detailOverrides[mode] = compactObject({
              ...detailOverrides[mode],
              initial_ceos: titleInitial,
            });
          }
        }
      }
      recipe.characterPatches.push({
        templateKey: payload.targetKey,
        displayName: payload.displayName,
        templateOverrides: compactObject({
          weight: payload.spawn?.weight,
          spawn_age_range: payload.spawn?.ageRange,
          min_spawn_round: payload.spawn?.minRound,
          max_spawn_round: payload.spawn?.maxRound,
          subtype: payload.subtype,
          art_set_override: patchArtSetId || undefined,
        }),
        imageAssets: patchImageAssets,
        artSetOverrides: {},
        artOverrides: hasAppearanceOverride ? patchImageArtKeys : {},
        detailOverrides,
        ...titleCeoRecipeFields(titleSource, targetCharacter),
        ...ceoSetRecipeFields(payload),
      });
    }

    if (item.kind === 'clone_character') {
      const payload = item.payload;
      const itemNumber = queueWorkNumber(item, index);
      const slug = queueWorkSlug(item, index, payload.sourceKeys?.base || payload.newName);
      const appearanceBase = characterByAppearanceKey(payload.sourceKeys?.imageSet);
      const selectedBase = characters().find((candidate) => candidate.key === payload.sourceKeys?.base);
      const base = selectedBase || appearanceBase;
      const packBase = firstCharacterWithDetails(base);
      const baseTemplate = base?.templateRow || {};
      const baseDetails = detailsByMode(base);
      const imageSet = appearanceByKey(payload.sourceKeys?.imageSet);
      const skillSource = characters().find((candidate) => candidate.key === payload.sourceKeys?.skill)
        || base;
      const attribute = resolveAttributeChoice(payload.sourceKeys?.attributeSet);
      const titleSource = resolveTitleChoice(payload.sourceKeys?.title);
      const combat = characters().find((candidate) => candidate.key === payload.sourceKeys?.combatProfile);
      const unitSource = characters().find((candidate) => candidate.key === payload.sourceKeys?.unitProfile);
      const detailSource = firstCharacterWithDetails(packBase, selectedBase, appearanceBase);
      const unit = firstCharacterWithDetails(unitSource, detailSource);
      const spawn = characters().find((candidate) => candidate.key === payload.sourceKeys?.spawn);
      const selectedAgeRange = payload.spawn?.ageRange || spawn?.spawnAge || base?.spawnAge || baseTemplate.spawn_age_range;
      const spawnPlan = generatedSpawnPlan(payload.spawn || {});
      const retinueOverride = payload.unitStatClone?.newRetinueKey || null;
      const attributeSetOverride = payload.attributeSetClone?.newSetKey;
      const defaultTitleSource = defaultTitleChoiceForCharacter(base);
      if (payload.attributeSetClone) {
        recipe.attributeSetClones.push({
          sourceSetKey: payload.attributeSetClone.sourceSetKey,
          newSetKey: payload.attributeSetClone.newSetKey,
          overrides: payload.attributeSetClone.overrides,
        });
      }
      if (payload.ageRangeClone) {
        recipe.ageRangeClones.push({
          sourceKey: payload.ageRangeClone.sourceKey,
          newKey: payload.ageRangeClone.newKey,
          overrides: payload.ageRangeClone.overrides,
        });
      }
      if (payload.unitStatClone) {
        recipe.landUnitClones.push({
          sourceKey: payload.unitStatClone.sourceKey,
          newKey: payload.unitStatClone.newKey,
          sourceRetinueKey: payload.unitStatClone.sourceRetinueKey,
          newRetinueKey: payload.unitStatClone.newRetinueKey,
          overrides: payload.unitStatClone.overrides,
        });
      }
      const detailOverrides = detailOverrideFromSources(attribute, unit, retinueOverride);
      const detailOverridesWithSkill = mergeSkillSetOverrides(detailOverrides, skillSource);
      if (attributeSetOverride) {
        detailOverridesWithSkill.historical = compactObject({
          ...detailOverridesWithSkill.historical,
          attribute_set: attributeSetOverride,
        });
        detailOverridesWithSkill.romance = compactObject({
          ...detailOverridesWithSkill.romance,
          attribute_set: attributeSetOverride,
        });
      }
      const customTemplateKey = `hby_template_${slug}_${itemNumber}`;
      const customArtSetId = `hby_art_set_${slug}_${itemNumber}`;
      const customImageToken = shortImageWorkToken('hby_clone', slug, itemNumber);
      const customImageAssets = imageSet
        ? customImageAssetsFromAppearance(imageSet, customImageToken)
        : [];
      const customImageArtKeys = imageSet
        ? artImageKeysFromTargetAssets(customImageAssets, customImageToken, customImageToken)
        : {};
      const finalTemplateGender = baseTemplate.is_male;
      const cloneInitialCeoForMode = (mode) => {
        if (titleChoiceChanged(titleSource, defaultTitleSource)) {
          const titleInitial = titleInitialCeoForModeFromChoice(titleSource, mode);
          if (titleInitial) return titleInitial;
        }
        const rawInitialCeo = baseDetails[mode]?.initialCeos
          || baseDetails.historical?.initialCeos
          || baseDetails.romance?.initialCeos
          || null;
        return genderCompatibleInitialCeoKey(rawInitialCeo, finalTemplateGender, payload.subtype);
      };
      for (const mode of ['historical', 'romance']) {
        detailOverridesWithSkill[mode] = compactObject({
          ...detailOverridesWithSkill[mode],
          initial_ceos: cloneInitialCeoForMode(mode),
        });
      }
      const clonedSkillSetOverride = skillSetCloneFromPayload(recipe, payload.skillTree, customTemplateKey, itemNumber);
      if (clonedSkillSetOverride) {
        detailOverridesWithSkill.romance = compactObject({
          ...detailOverridesWithSkill.romance,
          skill_set_override: clonedSkillSetOverride,
        });
      }
      recipe.characterCloneRecipes.push({
        newTemplateKey: customTemplateKey,
        sourceTemplateKey: packBase?.key,
        detailSourceTemplateKey: detailSource?.key,
        newArtSetId: customArtSetId,
        artSetSourceId: modelArtSetKeyForRecipe(null, packBase),
        newAgeRangeKey: null,
        ageRangeSourceKey: null,
        newInitialCeoKey: null,
        initialCeoSourceKey: null,
        spawnEvent: spawnPlan.event,
        displayName: payload.newName,
        imageAssets: customImageAssets,
        artOverrides: compactObject(customImageArtKeys),
        ...titleCeoRecipeFields(titleSource, base),
        ...ceoSetRecipeFields(payload),
        templateOverrides: compactObject({
          forename: baseTemplate.forename,
          family_name: baseTemplate.family_name,
          clan_name: baseTemplate.clan_name,
          other_name: baseTemplate.other_name,
          can_be_born: baseTemplate.can_be_born,
          ai_skill_generation: baseTemplate.ai_skill_generation,
          min_rounds_to_stay_in_a_pool: baseTemplate.min_rounds_to_stay_in_a_pool,
          max_rounds_to_stay_in_a_pool: baseTemplate.max_rounds_to_stay_in_a_pool,
          max_rounds_in_all_pools_before_destroyed: baseTemplate.max_rounds_in_all_pools_before_destroyed,
          spawn_age_range: selectedAgeRange,
          weight: payload.spawn?.weight,
          min_spawn_round: spawnPlan.minRound,
          max_spawn_round: 999,
          subtype: payload.subtype,
          art_set_override: customArtSetId,
        }),
        detailOverrides: detailOverridesWithSkill,
      });
    }
    recipe.workItems.push({
      kind: item.kind,
      type: item.type,
      title: item.title,
      workNumber: item.payload?.workNumber || index + 1,
      workSlug: item.payload?.workSlug || '',
      recipe: recipeSlice(recipe, before),
    });
  });

  return recipe;
}

function recipeSliceCursor(recipe) {
  return {
    characterPatches: recipe.characterPatches.length,
    characterCloneRecipes: recipe.characterCloneRecipes.length,
    equipmentStatPatches: recipe.equipmentStatPatches.length,
    armourTypeClones: recipe.armourTypeClones.length,
    landUnitClones: recipe.landUnitClones.length,
    skillSetClones: recipe.skillSetClones.length,
    attributeSetClones: recipe.attributeSetClones.length,
    ageRangeClones: recipe.ageRangeClones.length,
  };
}

function recipeSlice(recipe, before) {
  return {
    characterPatches: recipe.characterPatches.slice(before.characterPatches),
    characterCloneRecipes: recipe.characterCloneRecipes.slice(before.characterCloneRecipes),
    equipmentStatPatches: recipe.equipmentStatPatches.slice(before.equipmentStatPatches),
    armourTypeClones: recipe.armourTypeClones.slice(before.armourTypeClones),
    landUnitClones: recipe.landUnitClones.slice(before.landUnitClones),
    skillSetClones: recipe.skillSetClones.slice(before.skillSetClones),
    attributeSetClones: recipe.attributeSetClones.slice(before.attributeSetClones),
    ageRangeClones: recipe.ageRangeClones.slice(before.ageRangeClones),
  };
}

function compactObject(value) {
  return Object.fromEntries(
    Object.entries(value || {}).filter(([, item]) => item !== undefined && item !== null && item !== '')
  );
}
