'use strict';

const SEARCHABLE_SELECT_IDS = new Set([
  'editImageSet',
  'sourceImageSet',
  'sourceBase',
  'editSkill',
  'sourceSkill',
  'editTitle',
  'sourceTitle',
  'editTraitSet',
  'sourceTraitSet',
  'editAttributeSet',
  'sourceAttributeSet',
  'editEquipmentSet',
  'sourceEquipmentSet',
  'editCombatProfile',
  'sourceCombatProfile',
  'editUnitProfile',
  'sourceUnitProfile',
  'sourceSpawn',
]);

const CEO_SET_BASE_VALUE = '__base__';
const TRAIT_CEO_REMOVAL_EXTRAS = [
  '3k_main_ceo_trait_personality_disloyal',
];

function ceoSetCatalog(kind) {
  return kind === 'equipment'
    ? (state.options?.equipmentSets || [])
    : (state.options?.traitSets || []);
}

function ceoSetBaseLabel(kind) {
  return kind === 'equipment' ? '기준 장수 장비 유지' : '기준 장수 트레잇 유지';
}

function ceoSetChoices(kind) {
  return [
    { key: CEO_SET_BASE_VALUE, label: ceoSetBaseLabel(kind), items: [], ceoKeys: [], missingItems: [], available: true },
    ...ceoSetCatalog(kind),
  ];
}

function traitSetChoices() {
  return ceoSetChoices('trait');
}

function equipmentSetChoices() {
  return ceoSetChoices('equipment');
}

function ceoSetByKey(kind, key) {
  const value = String(key || CEO_SET_BASE_VALUE);
  if (!value || value === CEO_SET_BASE_VALUE) return null;
  return ceoSetCatalog(kind).find((item) => item.key === value) || null;
}

function ceoKeyFromValue(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') {
    return String(value.key || value.ceoKey || value.ceoNodeKey || '').trim();
  }
  const key = String(value || '').trim();
  return key === '[object Object]' ? '' : key;
}

function uniqueCeoKeys(values) {
  return uniqueStrings((values || []).map(ceoKeyFromValue));
}

function ceoSetRuntimeKeys(kind, values) {
  return uniqueCeoKeys(values);
}

function ceoSetNodeKeys(kind, key) {
  const set = ceoSetByKey(kind, key);
  if (!set) return [];
  const explicit = Array.isArray(set.ceoKeys) ? ceoSetRuntimeKeys(kind, set.ceoKeys) : [];
  const fromItems = ceoSetRuntimeKeys(kind, set.items || []);
  return explicit.length ? explicit : fromItems;
}

function ceoSetKnownNodeKeys(kind) {
  const keys = [];
  for (const set of ceoSetCatalog(kind)) {
    keys.push(...uniqueCeoKeys(set.ceoKeys || []));
    keys.push(...uniqueCeoKeys(set.items || []));
  }
  if (kind === 'trait') {
    keys.push(...TRAIT_CEO_REMOVAL_EXTRAS);
  }
  return ceoSetRuntimeKeys(kind, keys);
}

function ceoSetSelection(kind, key) {
  const set = ceoSetByKey(kind, key);
  const addCeos = ceoSetNodeKeys(kind, key);
  if (!set || !addCeos.length) return null;
  return {
    kind,
    setKey: set.key,
    label: set.label,
    addCeos,
    removeCeos: kind === 'equipment' ? [] : ceoSetKnownNodeKeys(kind),
  };
}

function defaultCharacterEquipmentCeos(character, equipmentSet = null) {
  return uniqueCeoKeys([character?.weaponCeo, character?.missileWeaponCeo, character?.armourCeo]);
}

function ceoSetOptionLabel(set) {
  if (!set || set.key === CEO_SET_BASE_VALUE) return set?.label || '';
  const total = (set.items || []).length;
  const resolved = (set.ceoKeys || []).length || (set.items || []).filter((item) => item.key).length;
  const suffix = total ? ` · ${resolved}/${total}` : '';
  return `${set.label}${suffix}`;
}

function ceoSetOptionSearch(set) {
  return [
    set?.label,
    set?.key,
    ...(set?.items || []).map((item) => `${item.label || ''} ${item.key || ''}`),
  ].join(' ');
}

function ceoSetSummaryMarkup(kind, key) {
  const set = ceoSetByKey(kind, key);
  if (!set) {
    return `<p class="empty">${escapeHtml(ceoSetBaseLabel(kind))}</p>`;
  }
  const missing = set.missingItems || [];
  const rows = (set.items || []).map((item) => `
    <div class="equipment-row">
      <span>${escapeHtml(item.label || '-')}</span>
      <strong>${escapeHtml(item.key || 'CEO key 미확인')}</strong>
    </div>
  `).join('');
  return `
    <div class="equipment-note">${escapeHtml(set.label || '-')} 전체를 CEO 세트로 적용합니다. 기존 프리셋 후보는 제거한 뒤 선택 세트를 다시 넣습니다.</div>
    ${rows}
    ${missing.length ? `<small>미확인: ${escapeHtml(missing.join(', '))}</small>` : ''}
  `;
}

function syncCeoSetSummary(prefix, kind, selectId) {
  const suffix = kind === 'equipment' ? 'EquipmentSetSummary' : 'TraitSetSummary';
  const target = $(`${prefix}${suffix}`);
  if (!target) return;
  target.innerHTML = ceoSetSummaryMarkup(kind, $(selectId).value);
  renderValidation();
}

function uniqueStrings(values) {
  return [...new Set((values || []).map((value) => String(value || '').trim()).filter(Boolean))];
}

function ageRangeOptions() {
  const rows = state.options?.ageRanges || [];
  return rows
    .filter((item) => item.key)
    .map((item) => {
      const years = [item.birthYear, item.minSpawnYearRound, item.maxSpawnYearRound]
        .filter((value) => value !== undefined && value !== null && value !== '')
        .join(' / ');
      return option(item.key, years ? `${friendlyKey(item.key)} · ${years}` : friendlyKey(item.key));
    });
}

function ageRangeByKey(key) {
  return (state.options?.ageRanges || []).find((item) => item.key === key);
}

function birthYearForAgeRange(key) {
  const row = ageRangeByKey(key);
  const value = row?.birthYear;
  return value === undefined || value === null || value === '' ? '' : Number(value);
}

function birthYearFromInput(id, fallback = '') {
  const raw = String($(id).value || '').trim();
  if (!raw) return fallback === undefined || fallback === null ? '' : fallback;
  const value = Number(raw);
  if (!Number.isFinite(value)) return fallback === undefined || fallback === null ? '' : fallback;
  return Math.max(0, Math.min(999, Math.trunc(value)));
}

function ageRangePatch(baseKey, birthYear, slug, itemNumber) {
  if (birthYear === '' || birthYear === undefined || birthYear === null) return null;
  const sourceKey = baseKey && baseKey !== '-' ? baseKey : ((state.options?.ageRanges || [])[0]?.key || '');
  if (!sourceKey) return null;
  const year = Math.max(0, Math.min(999, Math.trunc(Number(birthYear))));
  const baseRow = ageRangeByKey(sourceKey) || {};
  if (Number(baseRow.birthYear) === year) {
    return { sourceKey, newKey: sourceKey, overrides: {}, changed: false };
  }
  return {
    sourceKey,
    newKey: `hby_age_${slug}_${itemNumber}`,
    overrides: {
      birth_year: year,
      min_spawn_year: year,
      max_spawn_year: 999,
      min_spawn_year_round: 0,
      max_spawn_year_round: 999,
    },
    changed: true,
  };
}

function friendlyKey(value) {
  const text = String(value || '');
  const translated = koreanLabelFromText(text);
  if (translated) return translated;
  const genericLabel = genericDisplayName(text);
  if (genericLabel) return genericLabel;
  return text
    .split('_')
    .filter((word) => word && !['3k', 'main', 'mtu', 'template', 'historical', 'hero', 'general'].includes(word))
    .slice(-4)
    .join(' ') || String(value || '-');
}

function genericDisplayName(value) {
  const normalized = String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
  if (!normalized.includes('generic')) return '';
  const elementLabels = {
    earth: '토',
    fire: '화',
    metal: '금',
    water: '수',
    wood: '목',
  };
  const roleLabels = {
    agent: '첩보원',
    commander: '지휘관',
    envoy: '사절',
    general: '장군',
    governor: '태수',
    legendary: '전설',
    minister: '관료',
    strategist: '책사',
    villager: '향촌 인물',
  };
  const genderLabel = normalized.includes('generic_f') || normalized.includes('female') ? '여성'
    : normalized.includes('generic_m') || normalized.includes('male') ? '남성'
      : '';
  const elementKey = Object.keys(elementLabels).find((item) => normalized.includes(`_${item}_`) || normalized.endsWith(`_${item}`));
  const roleKey = Object.keys(roleLabels).find((item) => normalized.includes(`_${item}`) || normalized.endsWith(`_${item}`) || normalized.endsWith(item));
  const label = [genderLabel, elementLabels[elementKey], roleLabels[roleKey]].filter(Boolean).join(' ');
  return label || '';
}

function attributeSetDisplayName(key, fallback = '') {
  const text = String(`${key || ''} ${fallback || ''}`).toLowerCase();
  const elementKey = Object.keys(ELEMENTS).find((item) => text.includes(`_${item}_`) || text.includes(` ${item} `));
  const base = elementKey ? `${ELEMENTS[elementKey].name} 기본 능력치` : '';
  if (base && /attribute[_\s-]*set|records|general/.test(text)) return base;
  const fallbackText = String(fallback || '').trim();
  if (fallbackText && !/attribute[_\s-]*set|records/.test(fallbackText.toLowerCase())) return fallbackText;
  return base || friendlyKey(key);
}

function nullableNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function combatValue(value) {
  return value === null || value === undefined ? '미확인' : String(value);
}

function combatPair(character) {
  return `근접 ${combatValue(character.weaponDamage)}+${combatValue(character.weaponApDamage)} / 방어구 ${combatValue(character.baseDefense)}`;
}

function equipmentBrief(character) {
  if (!character) return '장비 정보 미확인';
  const melee = character.weaponStatKey
    ? `근접 ${combatValue(character.weaponDamage)}+${combatValue(character.weaponApDamage)}`
    : '근접 무기 미확인';
  const missile = character.missileWeaponStatKey
    ? `사격 ${combatValue(character.projectileDamage)}+${combatValue(character.projectileApDamage)}`
    : '사격 무기 없음';
  const armour = character.armourStatKey
    ? `방어구 ${combatValue(character.baseDefense)}`
    : '방어구 미확인';
  return `${melee} · ${missile} · ${armour}`;
}

function armourAudioTypeOptions(currentValue = '') {
  const defaults = ['Cloth', 'Leather', 'Segmented_Light', 'Segmented_Medium', 'Segmented_Heavy'];
  const values = new Set(defaults);
  for (const character of characters()) {
    if (character.armourAudioType) values.add(character.armourAudioType);
  }
  if (currentValue) values.add(currentValue);
  return [...values].sort((a, b) => a.localeCompare(b));
}

function equipmentSummaryMarkup(character, prefix) {
  return '';
}

function unitBrief(character) {
  if (!character) return '유닛 정보 미확인';
  return `근공 ${combatValue(character.unitMeleeAttack)} · 근방 ${combatValue(character.unitMeleeDefence)} · 돌격 ${combatValue(character.unitChargeBonus)} · 사기 ${combatValue(character.unitMorale)} · 탄약 ${combatValue(character.unitPrimaryAmmo)}`;
}

function unitSummaryMarkup(character, prefix) {
  if (!character) return '<p class="empty">유닛 정보를 확인할 수 없습니다.</p>';
  const readOnlyRows = [
    ['land unit', character.landUnitKey || '미확인'],
    ['분류', [character.unitCategory, character.unitClass].filter(Boolean).join(' / ') || '미확인'],
    ['근접 공격', combatValue(character.unitMeleeAttack)],
    ['근접 방어', combatValue(character.unitMeleeDefence)],
    ['돌격 보너스', combatValue(character.unitChargeBonus)],
    ['사기', combatValue(character.unitMorale)],
    ['탄약', combatValue(character.unitPrimaryAmmo)],
  ];
  return `
    <div class="group-title compact">
      <strong>읽기 전용 부대 프로필</strong>
      <span>read-only</span>
    </div>
    ${readOnlyRows.map(([label, value]) => `
      <div class="equipment-row">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>
    `).join('')}
  `;
  const canCloneUnit = Boolean(character.landUnitKey)
    && [
      character.unitMeleeAttack,
      character.unitMeleeDefence,
      character.unitChargeBonus,
      character.unitDismountedMeleeAttack,
      character.unitDismountedChargeBonus,
      character.unitMorale,
      character.unitPrimaryAmmo,
    ].some((value) => value !== null);
  const unitNote = canCloneUnit
    ? '값을 변경하면 land_units row와 retinue 체인을 복제해 역사/낭만 detail에 함께 적용합니다.'
    : '연결된 land_units row를 찾지 못했습니다. 저장 시 병종 수치 패치는 제외됩니다.';
  const rows = [
    ['land unit', character.landUnitKey || '미확인'],
    ['분류', [character.unitCategory, character.unitClass].filter(Boolean).join(' / ') || '미확인'],
  ];
  return `
    <div class="equipment-note">${escapeHtml(unitNote)}</div>
    <div class="group-title compact">
      <strong>읽기 전용 부대 프로필</strong>
      <span>land_units row 연결 상태를 확인합니다.</span>
    </div>
    ${rows.map(([label, value]) => `
      <div class="equipment-row">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>
    `).join('')}
    <div class="group-title compact">
      <strong>기준 장수 부대 값</strong>
      <span>변경 시 새 retinue 체인으로 저장합니다</span>
    </div>
    <div class="unit-stat-grid">
      <label>
        <span>근접 공격</span>
        <input id="${prefix}MeleeAttack" type="number" min="0" value="${escapeHtml(character.unitMeleeAttack ?? '')}">
      </label>
      <label>
        <span>근접 방어</span>
        <input id="${prefix}MeleeDefence" type="number" min="0" value="${escapeHtml(character.unitMeleeDefence ?? '')}">
      </label>
      <label>
        <span>돌격 보너스</span>
        <input id="${prefix}ChargeBonus" type="number" min="0" value="${escapeHtml(character.unitChargeBonus ?? '')}">
      </label>
      <label>
        <span>말 내림 근공</span>
        <input id="${prefix}DismountedMeleeAttack" type="number" min="0" value="${escapeHtml(character.unitDismountedMeleeAttack ?? '')}">
      </label>
      <label>
        <span>말 내림 돌격</span>
        <input id="${prefix}DismountedChargeBonus" type="number" min="0" value="${escapeHtml(character.unitDismountedChargeBonus ?? '')}">
      </label>
      <label>
        <span>사기</span>
        <input id="${prefix}Morale" type="number" min="0" value="${escapeHtml(character.unitMorale ?? '')}">
      </label>
      <label>
        <span>탄약</span>
        <input id="${prefix}PrimaryAmmo" type="number" min="0" value="${escapeHtml(character.unitPrimaryAmmo ?? '')}">
      </label>
    </div>
  `;
}

function elementFromSubtype(subtype) {
  const value = String(subtype || '').toLowerCase();
  return ['earth', 'fire', 'wood', 'water', 'metal'].find((element) => value.includes(element)) || 'earth';
}

function portraitGlyph(value) {
  const text = String(value || '將').trim();
  return [...text][Math.max(0, [...text].length - 1)] || '將';
}

function rosterTitleLabel(character) {
  const title = displayLabel(character?.titleName, character?.titleKey || character?.titleInitialCeoKey || '');
  return title && title !== '-' ? title : '칭호 미확인';
}

function rosterTitleTooltip(character) {
  const effect = titleEffectFor(character);
  if (effect?.effects) return `${effect.owner} - ${effect.title}\n${effect.effects}`;
  const description = String(character?.titleDescription || '').trim();
  if (description) return description;
  return `${character?.titleOwnerName || character?.name || '미확인'} - ${rosterTitleLabel(character)}`;
}
