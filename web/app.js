const ELEMENTS = {
  earth: { label: '土', name: '토', subtype: '3k_general_earth' },
  fire: { label: '火', name: '화', subtype: '3k_general_fire' },
  wood: { label: '木', name: '목', subtype: '3k_general_wood' },
  water: { label: '水', name: '수', subtype: '3k_general_water' },
  metal: { label: '金', name: '금', subtype: '3k_general_metal' },
};

const SPAWN_EVENTS = [
  { key: 'campaign_start', name: '캠페인 시작 시 등록', note: '시작 시점부터 장수 풀에 포함' },
  { key: 'round_pool', name: '라운드 조건으로 등장', note: '최소/최대 라운드와 가중치 사용' },
  { key: 'faction_join', name: '지정 세력 합류 이벤트', note: '특정 세력 또는 군주에게 지급' },
  { key: 'incident_reward', name: '이벤트 보상으로 영입', note: 'incident/mission 보상 흐름' },
  { key: 'disabled', name: '자동 등장 안 함', note: '직접 배치나 별도 이벤트 전용' },
];

const SAMPLE_CHARACTERS = [
  {
    key: '3k_mtu_template_historical_lady_buyeo_wol_hero_water',
    name: '부여월',
    element: 'water',
    portrait: '月',
    artSet: '3k_mtu_art_set_historical_lady_zou_yuan_general',
    imageSetName: '부여월 이미지 세트',
    modelSetName: '부여월 모델 세트',
    historicalSkill: '손권 기반 전략가 스킬셋',
    romanceSkill: '손권 기반 낭만 스킬셋',
    retinue: '수 속성 전략가',
    attributeSet: 'water strategist',
    combatProfile: '전략가 기본 장비',
    titleName: '부여월 칭호',
    titleKey: '3k_mtu_ceo_node_career_historical_buyeo_wol_01',
    titleStatus: 'read_only_spike',
    baseAttack: 42,
    baseDefense: 28,
    unitProfile: '검 보병 호위대',
    weight: 100,
    minRound: 0,
    maxRound: 999,
    spawnAge: '대교 기반 연령대',
    spawnEvent: 'round_pool',
  },
  {
    key: '3k_mtu_template_historical_chen_jiu_hero_wood',
    name: '진구',
    element: 'wood',
    portrait: '仇',
    artSet: '3k_mtu_art_set_historical_chen_jiu_general',
    imageSetName: '진구 이미지 세트',
    modelSetName: '진구 모델 세트',
    historicalSkill: '방덕 기반 기록 스킬셋',
    romanceSkill: '방덕 기반 낭만 스킬셋',
    retinue: '목 속성 용장',
    attributeSet: 'wood champion',
    combatProfile: '용장 장창 장비',
    titleName: '진구 칭호',
    titleKey: '3k_mtu_ceo_node_career_historical_chen_jiu_01',
    titleStatus: 'read_only_spike',
    baseAttack: 58,
    baseDefense: 46,
    unitProfile: '창 보병 호위대',
    weight: 100,
    minRound: 0,
    maxRound: 290,
    spawnAge: '방덕 기반 연령대',
    spawnEvent: 'round_pool',
  },
  {
    key: '3k_mtu_template_historical_dong_min_hero_earth',
    name: '동민',
    element: 'earth',
    portrait: '旻',
    artSet: '3k_mtu_art_set_historical_dong_min_general',
    imageSetName: '동민 이미지 세트',
    modelSetName: '동민 모델 세트',
    historicalSkill: '동민 기록 스킬셋',
    romanceSkill: '동민 낭만 스킬셋',
    retinue: '토 속성 지휘관',
    attributeSet: 'earth commander',
    combatProfile: '지휘관 균형 장비',
    titleName: '동민 칭호',
    titleKey: '3k_mtu_ceo_node_career_historical_dong_min_01',
    titleStatus: 'read_only_spike',
    baseAttack: 48,
    baseDefense: 52,
    unitProfile: '검기병 호위대',
    weight: 50.5,
    minRound: 0,
    maxRound: 165,
    spawnAge: '동민 연령대',
    spawnEvent: 'faction_join',
  },
  {
    key: '3k_mtu_template_historical_lady_ma_yunlu_hero_metal',
    name: '마운록',
    element: 'metal',
    portrait: '騄',
    artSet: '3k_mtu_art_set_historical_lady_ma_yunlu_general',
    imageSetName: '마운록 이미지 세트',
    modelSetName: '마운록 모델 세트',
    historicalSkill: '마운록 금속 스킬셋',
    romanceSkill: '마운록 낭만 스킬셋',
    retinue: '금 속성 선봉',
    attributeSet: 'metal sentinel',
    combatProfile: '감시자 중갑 장비',
    titleName: '마운록 칭호',
    titleKey: '3k_mtu_ceo_node_career_historical_ma_yunlu_01',
    titleStatus: 'read_only_spike',
    baseAttack: 50,
    baseDefense: 64,
    unitProfile: '도끼 보병 호위대',
    weight: 75.5,
    minRound: 0,
    maxRound: 140,
    spawnAge: '마운록 연령대',
    spawnEvent: 'incident_reward',
  },
  {
    key: '3k_mtu_template_historical_zhang_bao_hero_fire',
    name: '장포',
    element: 'fire',
    portrait: '苞',
    artSet: '3k_mtu_art_set_historical_zhang_bao_general',
    imageSetName: '장포 이미지 세트',
    modelSetName: '장포 모델 세트',
    historicalSkill: '장포 화 속성 스킬셋',
    romanceSkill: '장포 낭만 스킬셋',
    retinue: '화 속성 선봉',
    attributeSet: 'fire vanguard',
    combatProfile: '선봉 돌격 장비',
    titleName: '장포 칭호',
    titleKey: '3k_mtu_ceo_node_career_historical_zhang_bao_01',
    titleStatus: 'read_only_spike',
    baseAttack: 72,
    baseDefense: 34,
    unitProfile: '충격 기병 호위대',
    weight: 100,
    minRound: 0,
    maxRound: 999,
    spawnAge: '장포 연령대',
    spawnEvent: 'campaign_start',
  },
];

const state = {
  characters: SAMPLE_CHARACTERS,
  options: null,
  selectedKey: SAMPLE_CHARACTERS[0].key,
  filter: 'all',
  mode: 'edit',
  queue: [],
  serverMessages: [],
  lastRecipe: null,
};

const $ = (id) => document.getElementById(id);

function selectedCharacter() {
  return state.characters.find((character) => character.key === state.selectedKey) || state.characters[0];
}

function characters() {
  return state.characters;
}

function elementMeta(element) {
  return ELEMENTS[element] || { label: '將', name: '기타', subtype: '' };
}

function spawnEventMeta(key) {
  return SPAWN_EVENTS.find((event) => event.key === key) || SPAWN_EVENTS[0];
}

function hydrateFromPackData(characterData) {
  const summary = characterData?.pack;
  if (!summary?.characters?.length) return;
  state.options = summary;
  state.characters = summary.characters.map((item) => normalizePackCharacter(item, summary));
  state.selectedKey = state.characters[0].key;
  state.queue = [];
}

function normalizePackCharacter(item, summary) {
  const historical = item.details.find((detail) => detail.gameMode === 'historical') || item.details[0] || {};
  const romance = item.details.find((detail) => detail.gameMode === 'romance') || historical;
  const element = elementFromSubtype(item.subtype);
  const artSet = summary.artSets.find((candidate) => candidate.key === item.artSet);
  const combatStats = item.combatStats || {};
  const titleInfo = item.titleInfo || {};
  return {
    key: item.key,
    name: item.label || item.displayName || friendlyKey(item.key),
    element,
    portrait: portraitGlyph(item.label || item.displayName || item.key),
    artSet: item.artSet || '',
    imageSetName: artSet?.label || friendlyKey(item.artSet || item.key),
    modelSetName: item.uniform || artSet?.uniform || friendlyKey(item.artSet || item.key),
    historicalSkill: historical.skillSet || '-',
    romanceSkill: romance.skillSet || historical.skillSet || '-',
    retinue: historical.retinue || romance.retinue || '-',
    attributeSet: historical.attributeSet || romance.attributeSet || '-',
    combatProfile: combatStats.weaponCeo || combatStats.armourCeo || historical.initialCeos || romance.initialCeos || '장비 정보 미확인',
    titleName: titleInfo.label || '칭호 미확인',
    titleKey: titleInfo.ceoNodeKey || '',
    titleInitialCeoKey: titleInfo.initialCeoKey || '',
    titleLocKey: titleInfo.locTitleKey || '',
    titleStatus: titleInfo.status || 'read_only_spike',
    titleNote: titleInfo.note || 'set_title 쓰기는 검증 필요',
    baseAttack: nullableNumber(combatStats.baseAttack),
    baseDefense: nullableNumber(combatStats.baseDefense),
    weaponStatKey: combatStats.weaponStatKey || '',
    weaponDamage: nullableNumber(combatStats.weaponDamage),
    weaponApDamage: nullableNumber(combatStats.weaponApDamage),
    weaponType: combatStats.weaponType || '',
    missileWeaponStatKey: combatStats.missileWeaponStatKey || '',
    projectileStatKey: combatStats.projectileStatKey || '',
    projectileDamage: nullableNumber(combatStats.projectileDamage),
    projectileApDamage: nullableNumber(combatStats.projectileApDamage),
    projectileRange: nullableNumber(combatStats.projectileRange),
    armourCeo: combatStats.armourCeo || '',
    armourStatKey: combatStats.armourStatKey || '',
    armourAudioType: combatStats.armourAudioType || '',
    landUnitKey: combatStats.landUnitKey || '',
    unitMeleeAttack: nullableNumber(combatStats.unitMeleeAttack),
    unitMeleeDefence: nullableNumber(combatStats.unitMeleeDefence),
    unitChargeBonus: nullableNumber(combatStats.unitChargeBonus),
    unitMorale: nullableNumber(combatStats.unitMorale),
    unitPrimaryAmmo: nullableNumber(combatStats.unitPrimaryAmmo),
    unitCategory: combatStats.unitCategory || '',
    unitClass: combatStats.unitClass || '',
    unitFromReference: Boolean(combatStats.unitFromReference),
    unitReferenceSource: combatStats.unitReferenceSource || '',
    unitProfile: historical.retinue || romance.retinue || '-',
    weight: Number(item.weight ?? 0),
    minRound: Number(item.minSpawnRound ?? 0),
    maxRound: Number(item.maxSpawnRound ?? 999),
    spawnAge: item.ageRange || '-',
    spawnEvent: 'round_pool',
    templateRow: item.templateRow || {},
    details: item.details || [],
    portraitPath: item.portrait || artSet?.portrait || '',
    cardPath: item.card || artSet?.card || '',
    portraitImagePath: item.portraitImagePath || artSet?.portraitImagePath || '',
    portraitImageSourcePath: item.portraitImageSourcePath || artSet?.portraitImageSourcePath || '',
    cardImagePath: item.cardImagePath || artSet?.cardImagePath || '',
    cardImageSourcePath: item.cardImageSourcePath || artSet?.cardImageSourcePath || '',
    uniform: item.uniform || artSet?.uniform || '',
    source: item.source || 'pack',
    referenceSourcePath: item.referenceSourcePath || '',
  };
}

function friendlyKey(value) {
  return String(value || '')
    .split('_')
    .filter((word) => word && !['3k', 'main', 'mtu', 'template', 'historical', 'hero', 'general'].includes(word))
    .slice(-4)
    .join(' ') || String(value || '-');
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

function equipmentSummaryMarkup(character, prefix) {
  if (!character) return '<p class="empty">장비 정보를 확인할 수 없습니다.</p>';
  const canEditArmour = Boolean(character.armourCeo && character.armourStatKey);
  const armourWarning = character.armourStatKey?.includes('_unique')
    ? '고유 방어구라 영향 범위가 좁습니다.'
    : '공용 방어구면 같은 key를 쓰는 다른 유닛에도 영향을 줄 수 있습니다.';
  const rows = [
    ['근접 무기', character.weaponStatKey || '미확인'],
    ['근접 피해', character.weaponStatKey ? `${combatValue(character.weaponDamage)} / AP ${combatValue(character.weaponApDamage)}` : '미확인'],
    ['사격 무기', character.missileWeaponStatKey || '없음'],
    ['투사체', character.projectileStatKey || '없음'],
    ['사격 피해', character.projectileStatKey ? `${combatValue(character.projectileDamage)} / AP ${combatValue(character.projectileApDamage)} / 사거리 ${combatValue(character.projectileRange)}` : '없음'],
    ['방어구', character.armourStatKey || '미확인'],
    ['Audio Type', character.armourAudioType || '미확인'],
  ];
  return `
    <div class="equipment-note">무기/투사체 수정은 보류, 방어값은 armour_value로 저장됩니다.</div>
    ${rows.map(([label, value]) => `
      <div class="equipment-row">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>
    `).join('')}
    <label class="armour-edit">
      <span>방어값</span>
      <input id="${prefix}ArmourValue" type="number" min="0" value="${escapeHtml(character.baseDefense ?? '')}" ${canEditArmour ? '' : 'disabled'}>
      <small>${escapeHtml(canEditArmour ? armourWarning : '연결된 방어구 CEO를 찾지 못했습니다.')}</small>
    </label>
  `;
}

function unitBrief(character) {
  if (!character) return '유닛 정보 미확인';
  return `돌격 ${combatValue(character.unitChargeBonus)} · 사기 ${combatValue(character.unitMorale)} · 탄약 ${combatValue(character.unitPrimaryAmmo)}`;
}

function unitSummaryMarkup(character, prefix) {
  if (!character) return '<p class="empty">유닛 정보를 확인할 수 없습니다.</p>';
  const canEdit = Boolean(character.landUnitKey)
    && !character.unitFromReference
    && [character.unitChargeBonus, character.unitMorale, character.unitPrimaryAmmo].some((value) => value !== null);
  const rows = [
    ['land unit', character.landUnitKey || '미확인'],
    ['분류', [character.unitCategory, character.unitClass].filter(Boolean).join(' / ') || '미확인'],
    ['근접 공격', combatValue(character.unitMeleeAttack)],
    ['근접 방어', combatValue(character.unitMeleeDefence)],
  ];
  return `
    <div class="equipment-note">${escapeHtml(character.unitFromReference ? '참조 pack에서 보강된 유닛 row라 현재는 읽기 전용입니다.' : '돌격 보너스/사기/탄약은 새 land_units row로 복제 저장됩니다. 근공/근방은 현재 확인용입니다.')}</div>
    ${rows.map(([label, value]) => `
      <div class="equipment-row">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>
    `).join('')}
    <div class="unit-stat-grid">
      <label>
        <span>돌격 보너스</span>
        <input id="${prefix}ChargeBonus" type="number" min="0" value="${escapeHtml(character.unitChargeBonus ?? '')}" ${canEdit ? '' : 'disabled'}>
      </label>
      <label>
        <span>사기</span>
        <input id="${prefix}Morale" type="number" min="0" value="${escapeHtml(character.unitMorale ?? '')}" ${canEdit ? '' : 'disabled'}>
      </label>
      <label>
        <span>탄약</span>
        <input id="${prefix}PrimaryAmmo" type="number" min="0" value="${escapeHtml(character.unitPrimaryAmmo ?? '')}" ${canEdit ? '' : 'disabled'}>
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

function renderRoster() {
  const query = $('searchInput').value.trim().toLowerCase();
  const list = $('characterList');
  list.innerHTML = '';
  const filtered = characters().filter((character) => {
    const spawnEvent = spawnEventMeta(character.spawnEvent);
    const haystack = `${character.name} ${character.key} ${character.imageSetName} ${character.modelSetName} ${character.combatProfile} ${character.unitProfile} ${spawnEvent.name} ${character.element}`.toLowerCase();
    const matchesQuery = !query || haystack.includes(query);
    const matchesFilter = state.filter === 'all' || character.element === state.filter;
    return matchesQuery && matchesFilter;
  });

  $('rosterCount').textContent = `${filtered.length}명`;

  for (const character of filtered) {
    const meta = elementMeta(character.element);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `character-card ${character.key === state.selectedKey ? 'active' : ''}`;
    button.innerHTML = `
      ${portraitMarkup(character, 'mini-portrait')}
      <div class="card-main">
        <strong>${escapeHtml(character.name)}</strong>
        <span>${meta.name} · ${escapeHtml(character.retinue)}${character.source === 'reference' ? ' · 참조' : ''}</span>
        <small>${escapeHtml(character.key)}</small>
      </div>
      <b>${meta.label}</b>
    `;
    button.addEventListener('click', () => {
      state.selectedKey = character.key;
      renderAll();
    });
    list.appendChild(button);
  }
}

function renderSelected() {
  const character = selectedCharacter();
  const meta = elementMeta(character.element);
  $('portraitFrame').className = `portrait-frame element-${character.element}`;
  $('portraitFrame').innerHTML = portraitMarkup(character, 'portrait-image');
  $('selectedName').textContent = character.name;
  $('selectedKey').textContent = character.key;
  $('elementBadge').className = `element-badge element-${character.element}`;
  $('elementBadge').textContent = `${meta.label} ${meta.name}`;
  $('currentImageSet').textContent = character.imageSetName;
  $('currentModelSet').textContent = character.modelSetName;
  $('currentAttributeSet').textContent = character.attributeSet;
  $('currentCombatProfile').textContent = combatPair(character);
  $('currentUnitProfile').textContent = character.unitProfile;
  $('currentHistSkill').textContent = character.historicalSkill;
  $('currentRomanceSkill').textContent = character.romanceSkill;
  $('currentSpawn').textContent = `${character.minRound}~${character.maxRound} 라운드 · 가중치 ${character.weight}`;
  $('currentSpawnEvent').textContent = spawnEventMeta(character.spawnEvent).name;

  $('selectedChips').innerHTML = `
    <span>${escapeHtml(character.retinue)}</span>
    <span>${escapeHtml(character.attributeSet)}</span>
    <span>${escapeHtml(character.spawnAge)}</span>
  `;

  $('currentCards').innerHTML = [
    infoCard('표시 이름', character.name, 'UI와 loc 표시명 기준'),
    infoCard('이미지 세트', character.imageSetName, '장수 초상화 이미지'),
    infoCard('모델 세트', character.modelSetName, '전장 모델 / 캠페인 모델 / 전체 외형'),
    infoCard('역사 모드', character.historicalSkill, character.retinue),
    infoCard('낭만 모드', character.romanceSkill, character.attributeSet),
    infoCard('능력치 세트', character.attributeSet, '기본 능력치 묶음'),
    infoCard('칭호/직함', titleBrief(character), 'set_title 후보, 저장은 검증 필요'),
    infoCard('장비 정보', equipmentBrief(character), '무기/투사체/방어구 수치 수정 보류'),
    infoCard('병종/부대 타입', character.unitProfile, unitBrief(character)),
    infoCard('등장 조건', `${character.minRound}~${character.maxRound} 라운드`, `등장 가중치 ${character.weight}`),
    infoCard('등장 이벤트', spawnEventMeta(character.spawnEvent).name, spawnEventMeta(character.spawnEvent).note),
    infoCard('데이터 출처', character.source === 'reference' ? '참조 pack' : '현재 pack', character.referenceSourcePath || '수정/저장 가능 대상'),
    infoCard('원본 key', character.key, '저장 시 내부 식별자로 사용'),
  ].join('');

  fillForms(character);
}

function renderAppearanceGallery() {
  $('appearanceGallery').innerHTML = characters().map((character) => `
    <button class="appearance-card ${character.key === selectedCharacter().key ? 'active' : ''}" data-key="${escapeHtml(character.key)}" type="button">
      ${portraitMarkup(character, 'mini-portrait')}
      <strong>${escapeHtml(character.name)}</strong>
      <span>이미지: ${escapeHtml(character.imageSetName)}</span>
      <span>모델: ${escapeHtml(character.modelSetName)}</span>
    </button>
  `).join('');

  for (const card of document.querySelectorAll('.appearance-card')) {
    card.addEventListener('click', () => {
      $('editImageSet').value = card.dataset.key;
      $('editModelSet').value = card.dataset.key;
      $('sourceImageSet').value = card.dataset.key;
      $('sourceModelSet').value = card.dataset.key;
      updateImagePreviews();
      renderValidation();
    });
  }
}

function fillForms(character) {
  $('editName').value = character.name;
  $('editWeight').value = character.weight;
  $('editMinRound').value = character.minRound;
  $('editMaxRound').value = character.maxRound;
  $('createWeight').value = character.weight;

  fillSelect('editImageSet', characters().map((item) => option(item.key, `${item.name} · ${item.imageSetName}`)));
  fillSelect('editModelSet', characters().map((item) => option(item.key, `${item.name} · ${item.modelSetName}`)));
  fillSelect('sourceImageSet', characters().map((item) => option(item.key, `${item.name} · ${item.imageSetName}`)));
  fillSelect('sourceModelSet', characters().map((item) => option(item.key, `${item.name} · ${item.modelSetName}`)));
  fillSelect('sourceBase', characters().map((item) => option(item.key, item.name)));
  fillSelect('sourceSkill', characters().map((item) => option(item.key, `${item.name} · ${item.historicalSkill}`)));
  fillSelect('editAttributeSet', characters().map((item) => option(item.key, `${item.name} · ${item.attributeSet}`)));
  fillSelect('sourceAttributeSet', characters().map((item) => option(item.key, `${item.name} · ${item.attributeSet}`)));
  fillSelect('editCombatProfile', characters().map((item) => option(item.key, `${item.name} · ${equipmentBrief(item)}`)));
  fillSelect('sourceCombatProfile', characters().map((item) => option(item.key, `${item.name} · ${equipmentBrief(item)}`)));
  fillSelect('editUnitProfile', characters().map((item) => option(item.key, `${item.name} · ${item.unitProfile}`)));
  fillSelect('sourceUnitProfile', characters().map((item) => option(item.key, `${item.name} · ${item.unitProfile}`)));
  fillSelect('sourceSpawn', characters().map((item) => option(item.key, `${item.name} · ${item.spawnAge}`)));
  fillSelect('editSpawnEvent', SPAWN_EVENTS.map((item) => option(item.key, `${item.name} · ${item.note}`)));
  fillSelect('sourceSpawnEvent', SPAWN_EVENTS.map((item) => option(item.key, `${item.name} · ${item.note}`)));
  fillSelect('editSubtype', Object.entries(ELEMENTS).map(([key, item]) => option(item.subtype, `${item.label} ${item.name}`)));
  fillSelect('createSubtype', Object.entries(ELEMENTS).map(([key, item]) => option(item.subtype, `${item.label} ${item.name}`)));
  fillSelect('editHistoricalSkill', characters().map((item) => option(item.key, `${item.name} · ${item.historicalSkill}`)));
  fillSelect('editRomanceSkill', characters().map((item) => option(item.key, `${item.name} · ${item.romanceSkill}`)));

  $('editImageSet').value = character.key;
  $('editModelSet').value = character.key;
  $('sourceImageSet').value = character.key;
  $('sourceModelSet').value = character.key;
  $('sourceBase').value = character.key;
  $('sourceSkill').value = character.key;
  $('editAttributeSet').value = character.key;
  $('sourceAttributeSet').value = character.key;
  $('editCombatProfile').value = character.key;
  $('sourceCombatProfile').value = character.key;
  $('editUnitProfile').value = character.key;
  $('sourceUnitProfile').value = character.key;
  $('sourceSpawn').value = character.key;
  $('editSpawnEvent').value = character.spawnEvent;
  $('sourceSpawnEvent').value = character.spawnEvent;
  $('editSubtype').value = elementMeta(character.element).subtype;
  $('createSubtype').value = elementMeta(character.element).subtype;
  $('editHistoricalSkill').value = character.key;
  $('editRomanceSkill').value = character.key;
  $('createName').value = `${character.name} 파생`;
  renderTitleSummary('edit', character);
  renderTitleSummary('source', character);
  syncEquipmentSummary('edit', 'editCombatProfile');
  syncEquipmentSummary('source', 'sourceCombatProfile');
  syncUnitSummary('edit', 'editUnitProfile');
  syncUnitSummary('source', 'sourceUnitProfile');
  updateImagePreviews();
}

function option(value, label) {
  return { value, label };
}

function fillSelect(id, options) {
  const select = $(id);
  select.innerHTML = '';
  for (const item of options) {
    const optionEl = document.createElement('option');
    optionEl.value = item.value;
    optionEl.textContent = item.label;
    select.appendChild(optionEl);
  }
}

function infoCard(title, value, note) {
  return `
    <article class="info-card">
      <span>${escapeHtml(title)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(note)}</small>
    </article>
  `;
}

function titleBrief(character) {
  if (!character?.titleKey) return '칭호 미확인';
  return `${character.titleName || friendlyKey(character.titleKey)} · ${character.titleKey}`;
}

function titleSummaryMarkup(character) {
  if (!character) return '<p class="empty">칭호 정보를 확인할 수 없습니다.</p>';
  const rows = [
    ['현재 칭호', character.titleName || '미확인'],
    ['career CEO', character.titleKey || '미확인'],
    ['initial CEO', character.titleInitialCeoKey || '미확인'],
    ['loc key', character.titleLocKey || '미확인'],
  ];
  return `
    <div class="equipment-note">set_title/칭호는 campaigns/ceo_data.ccd 및 startpos 계층으로 보여서 현재는 읽기 전용입니다.</div>
    ${rows.map(([label, value]) => `
      <div class="equipment-row">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>
    `).join('')}
  `;
}

function renderTitleSummary(prefix, character) {
  const target = $(`${prefix}TitleSummary`);
  if (target) target.innerHTML = titleSummaryMarkup(character);
}

function imagePreviewMarkup(character, modeLabel) {
  if (!character) return '<p class="empty">이미지 세트를 선택하세요.</p>';
  const portraitLabel = character.portraitPath || '초상화 경로 대기';
  const portraitUrl = assetUrl(character.portraitImagePath, character.portraitImageSourcePath);
  return `
    <div class="preview-art portrait-art element-${character.element}">
      ${portraitUrl ? `<img src="${escapeHtml(portraitUrl)}" alt="${escapeHtml(character.name)} 초상화">` : `<span>${escapeHtml(character.portrait)}</span>`}
      <b>초상화</b>
    </div>
    <div class="preview-copy">
      <strong>${escapeHtml(character.name)} 이미지 세트</strong>
      <span>${escapeHtml(character.imageSetName)}</span>
      <small>${escapeHtml(modeLabel)} · ${escapeHtml(character.artSet)}</small>
      <small>portrait: ${escapeHtml(portraitLabel)}</small>
      <small>uniform: ${escapeHtml(character.uniform || character.modelSetName || '-')}</small>
    </div>
  `;
}

function portraitMarkup(character, className) {
  const url = assetUrl(character.portraitImagePath, character.portraitImageSourcePath);
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
  });
  return `/api/asset?${params.toString()}`;
}

function updateImagePreview(containerId, selectId, modeLabel) {
  const character = characters().find((item) => item.key === $(selectId).value);
  $(containerId).innerHTML = imagePreviewMarkup(character, modeLabel);
}

function updateImagePreviews() {
  updateImagePreview('editImagePreview', 'editImageSet', '기존 장수 수정');
  updateImagePreview('sourceImagePreview', 'sourceImageSet', '신규 장수 생성');
}

function setMode(mode) {
  state.mode = mode;
  for (const button of document.querySelectorAll('.mode-btn')) {
    button.classList.toggle('active', button.dataset.mode === mode);
  }
  $('editPanel').classList.toggle('active', mode === 'edit');
  $('createPanel').classList.toggle('active', mode === 'create');
  renderValidation();
}

function setWorkTab(target) {
  const prefix = target.split('-')[0];
  for (const button of document.querySelectorAll(`.tab-bar[data-tabs-for="${prefix}"] .tab-btn`)) {
    button.classList.toggle('active', button.dataset.tabTarget === target);
  }
  for (const section of document.querySelectorAll(`[data-tab-section^="${prefix}-"]`)) {
    section.classList.toggle('active', section.dataset.tabSection === target);
  }
}

function syncEquipmentSummary(prefix, sourceId) {
  const character = characters().find((item) => item.key === $(sourceId).value);
  if (!character) return;
  $(`${prefix}EquipmentSummary`).innerHTML = equipmentSummaryMarkup(character, prefix);
  const armourInput = $(`${prefix}ArmourValue`);
  if (armourInput) {
    armourInput.addEventListener('input', renderValidation);
    armourInput.addEventListener('change', renderValidation);
  }
  renderValidation();
}

function syncUnitSummary(prefix, sourceId) {
  const character = characters().find((item) => item.key === $(sourceId).value);
  if (!character) return;
  $(`${prefix}UnitSummary`).innerHTML = unitSummaryMarkup(character, prefix);
  for (const suffix of ['ChargeBonus', 'Morale', 'PrimaryAmmo']) {
    const input = $(`${prefix}${suffix}`);
    if (input) {
      input.addEventListener('input', renderValidation);
      input.addEventListener('change', renderValidation);
    }
  }
  renderValidation();
}

function armourPatchFrom(prefix, character) {
  const input = $(`${prefix}ArmourValue`);
  if (!input || !character?.armourCeo || !character?.armourStatKey) return null;
  const value = nullableNumber(input.value);
  if (value === null || value < 0 || value === character.baseDefense) return null;
  return {
    equipmentKey: character.armourCeo,
    statTable: 'armour',
    column: 'armour_value',
    value,
    armourKey: character.armourStatKey,
    previousValue: character.baseDefense,
  };
}

function unitStatCloneFrom(prefix, character, slug, index) {
  if (!character?.landUnitKey) return [];
  const fields = [
    ['ChargeBonus', 'charge_bonus', character.unitChargeBonus],
    ['Morale', 'morale', character.unitMorale],
    ['PrimaryAmmo', 'primary_ammo', character.unitPrimaryAmmo],
  ];
  const overrides = {};
  const changes = [];
  for (const [suffix, column, previousValue] of fields) {
    const input = $(`${prefix}${suffix}`);
    if (!input || input.disabled) continue;
    const value = nullableNumber(input.value);
    if (value === null || value < 0 || value === previousValue) continue;
    overrides[column] = value;
    changes.push({ column, value, previousValue });
  }
  if (!changes.length) return null;
  return {
    sourceKey: character.landUnitKey,
    newKey: `hby_land_unit_${slug}_${index}`,
    overrides,
    changes,
  };
}

function unitPatchDescription(clone) {
  if (!clone?.changes?.length) return '';
  const labels = {
    charge_bonus: '돌격',
    morale: '사기',
    primary_ammo: '탄약',
  };
  return ` · 유닛 ${clone.changes.map((patch) => `${labels[patch.column] || patch.column} ${patch.previousValue}→${patch.value}`).join(', ')}`;
}

function stageEdit() {
  const character = selectedCharacter();
  if (character.source === 'reference') {
    state.serverMessages = [validationItem('warning', '참조 장수 수정 보류', '참조 pack 장수는 현재 pack 내부 row가 아니어서 기존 장수 수정 대상에서 제외됩니다. 신규 생성 재료로만 사용하세요.')];
    renderValidation();
    return;
  }
  const imageSet = characters().find((item) => item.key === $('editImageSet').value);
  const modelSet = characters().find((item) => item.key === $('editModelSet').value);
  const hist = characters().find((item) => item.key === $('editHistoricalSkill').value);
  const romance = characters().find((item) => item.key === $('editRomanceSkill').value);
  const attribute = characters().find((item) => item.key === $('editAttributeSet').value);
  const combat = characters().find((item) => item.key === $('editCombatProfile').value);
  const unit = characters().find((item) => item.key === $('editUnitProfile').value);
  const spawnEvent = spawnEventMeta($('editSpawnEvent').value);
  const armourPatch = armourPatchFrom('edit', combat);
  const editSlug = slugify(`${character.key}_${state.queue.length + 1}`);
  const landUnitClone = unitStatCloneFrom('edit', unit, editSlug, state.queue.length + 1);
  const payload = {
    targetKey: character.key,
    displayName: $('editName').value.trim(),
    imageSetKey: imageSet?.key,
    modelSetKey: modelSet?.key,
    attributeSetSourceKey: attribute?.key,
    combatProfileSourceKey: combat?.key,
    armourPatch,
    landUnitClone,
    unitProfileSourceKey: unit?.key,
    subtype: $('editSubtype').value,
    spawn: {
      weight: Number($('editWeight').value),
      minRound: Number($('editMinRound').value),
      maxRound: Number($('editMaxRound').value),
      event: $('editSpawnEvent').value,
    },
    skillSources: {
      historical: hist?.key,
      romance: romance?.key,
    },
  };
  state.queue.push({
    kind: 'patch_character',
    type: '기존 수정',
    title: `${character.name} 수정`,
    description: `${$('editName').value} · 이미지 ${imageSet?.name || '-'} · 모델 ${modelSet?.name || '-'} · 능력치 ${attribute?.name || '-'} · 장비 유지(${equipmentBrief(combat)})${armourPatch ? ` · 방어값 ${armourPatch.previousValue}→${armourPatch.value}` : ''} · 병종 ${unit?.name || '-'}${unitPatchDescription(landUnitClone)} · 등장 이벤트 ${spawnEvent.name} · 역사 ${hist?.name || '-'} · 낭만 ${romance?.name || '-'}`,
    payload,
  });
  renderQueue();
  renderValidation();
}

function stageCreate() {
  const base = characters().find((item) => item.key === $('sourceBase').value);
  const imageSet = characters().find((item) => item.key === $('sourceImageSet').value);
  const modelSet = characters().find((item) => item.key === $('sourceModelSet').value);
  const skill = characters().find((item) => item.key === $('sourceSkill').value);
  const attribute = characters().find((item) => item.key === $('sourceAttributeSet').value);
  const combat = characters().find((item) => item.key === $('sourceCombatProfile').value);
  const unit = characters().find((item) => item.key === $('sourceUnitProfile').value);
  const spawn = characters().find((item) => item.key === $('sourceSpawn').value);
  const spawnEvent = spawnEventMeta($('sourceSpawnEvent').value);
  const armourPatch = armourPatchFrom('source', combat);
  const createSlug = slugify(`${base?.key || $('createName').value.trim() || 'new'}_${state.queue.length + 1}`);
  const landUnitClone = unitStatCloneFrom('source', unit, createSlug, state.queue.length + 1);
  const payload = {
    newName: $('createName').value.trim(),
    sourceKeys: {
      base: base?.key,
      imageSet: imageSet?.key,
      modelSet: modelSet?.key,
      skill: skill?.key,
      attributeSet: attribute?.key,
      combatProfile: combat?.key,
      unitProfile: unit?.key,
      spawn: spawn?.key,
    },
    subtype: $('createSubtype').value,
    armourPatch,
    landUnitClone,
    spawn: {
      weight: Number($('createWeight').value),
      event: $('sourceSpawnEvent').value,
    },
  };
  state.queue.push({
    kind: 'clone_character',
    type: '신규 생성',
    title: `${$('createName').value || '새 장수'} 생성`,
    description: `기본 ${base?.name || '-'} · 이미지 ${imageSet?.name || '-'} · 모델 ${modelSet?.name || '-'} · 능력치 ${attribute?.name || '-'} · 장비 유지(${equipmentBrief(combat)})${armourPatch ? ` · 방어값 ${armourPatch.previousValue}→${armourPatch.value}` : ''} · 병종 ${unit?.name || '-'}${unitPatchDescription(landUnitClone)} · 스킬 ${skill?.name || '-'} · 등장 ${spawn?.name || '-'} · 이벤트 ${spawnEvent.name}`,
    payload,
  });
  renderQueue();
  renderValidation();
}

function renderQueue() {
  $('queueCount').textContent = `${state.queue.length}개`;
  $('workQueue').innerHTML = state.queue.length
    ? state.queue.map((item, index) => `
      <article class="queue-item">
        <b>${index + 1}. ${escapeHtml(item.type)}</b>
        <strong>${escapeHtml(item.title)}</strong>
        <span>${escapeHtml(item.description)}</span>
      </article>
    `).join('')
    : '<p class="empty">아직 추가된 작업이 없습니다.</p>';
}

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

function detailsByMode(character) {
  const details = {};
  for (const detail of character?.details || []) {
    if (detail.gameMode) details[detail.gameMode] = detail;
  }
  return details;
}

function detailOverrideFromSources(attribute, skill, unit, retinueOverride = null) {
  const overrides = {};
  const attributeDetails = detailsByMode(attribute);
  const skillDetails = detailsByMode(skill);
  const unitDetails = detailsByMode(unit);
  for (const mode of ['historical', 'romance']) {
    overrides[mode] = compactObject({
      retinue: retinueOverride || unitDetails[mode]?.retinue || unit?.unitProfile,
      attribute_set: attributeDetails[mode]?.attributeSet || attribute?.attributeSet,
      skill_set_override: skillDetails[mode]?.skillSet || (mode === 'romance' ? skill?.romanceSkill : skill?.historicalSkill),
    });
  }
  return overrides;
}

function recipeFromQueue() {
  const recipe = {
    modName: 'mtu_custom_character_workflow',
    characterPatches: [],
    characterCloneRecipes: [],
    equipmentStatPatches: [],
    landUnitClones: [],
  };

  state.queue.forEach((item, index) => {
    if (item.kind === 'patch_character') {
      const payload = item.payload;
      const imageSet = characters().find((candidate) => candidate.key === payload.imageSetKey);
      const attribute = characters().find((candidate) => candidate.key === payload.attributeSetSourceKey);
      const hist = characters().find((candidate) => candidate.key === payload.skillSources?.historical);
      const romance = characters().find((candidate) => candidate.key === payload.skillSources?.romance);
      const unit = characters().find((candidate) => candidate.key === payload.unitProfileSourceKey);
      const retinueOverride = payload.landUnitClone?.newKey;
      if (payload.landUnitClone) {
        recipe.landUnitClones.push({
          sourceKey: payload.landUnitClone.sourceKey,
          newKey: payload.landUnitClone.newKey,
          overrides: payload.landUnitClone.overrides,
        });
      }
      recipe.characterPatches.push({
        templateKey: payload.targetKey,
        templateOverrides: compactObject({
          weight: payload.spawn?.weight,
          min_spawn_round: payload.spawn?.minRound,
          max_spawn_round: payload.spawn?.maxRound,
          subtype: payload.subtype,
          art_set_override: imageSet?.artSet,
        }),
        detailOverrides: {
          historical: compactObject({
            retinue: retinueOverride || detailsByMode(unit).historical?.retinue || unit?.unitProfile,
            attribute_set: detailsByMode(attribute).historical?.attributeSet || attribute?.attributeSet,
            skill_set_override: detailsByMode(hist).historical?.skillSet || hist?.historicalSkill,
          }),
          romance: compactObject({
            retinue: retinueOverride || detailsByMode(unit).romance?.retinue || unit?.unitProfile,
            attribute_set: detailsByMode(attribute).romance?.attributeSet || attribute?.attributeSet,
            skill_set_override: detailsByMode(romance).romance?.skillSet || romance?.romanceSkill,
          }),
        },
      });
      if (payload.armourPatch) {
        recipe.equipmentStatPatches.push({
          equipmentKey: payload.armourPatch.equipmentKey,
          statTable: payload.armourPatch.statTable,
          column: payload.armourPatch.column,
          value: payload.armourPatch.value,
        });
      }
    }

    if (item.kind === 'clone_character') {
      const payload = item.payload;
      const base = characters().find((candidate) => candidate.key === payload.sourceKeys?.base);
      const imageSet = characters().find((candidate) => candidate.key === payload.sourceKeys?.imageSet);
      const attribute = characters().find((candidate) => candidate.key === payload.sourceKeys?.attributeSet);
      const skill = characters().find((candidate) => candidate.key === payload.sourceKeys?.skill);
      const unit = characters().find((candidate) => candidate.key === payload.sourceKeys?.unitProfile);
      const spawn = characters().find((candidate) => candidate.key === payload.sourceKeys?.spawn);
      const slug = slugify(payload.newName);
      const retinueOverride = payload.landUnitClone?.newKey;
      if (payload.landUnitClone) {
        recipe.landUnitClones.push({
          sourceKey: payload.landUnitClone.sourceKey,
          newKey: payload.landUnitClone.newKey,
          overrides: payload.landUnitClone.overrides,
        });
      }
      recipe.characterCloneRecipes.push({
        newTemplateKey: `hby_template_${slug}_${index + 1}`,
        sourceTemplateKey: base?.key,
        detailSourceTemplateKey: skill?.key || base?.key,
        newArtSetId: `hby_art_set_${slug}_${index + 1}`,
        artSetSourceId: imageSet?.artSet || base?.artSet,
        newAgeRangeKey: `hby_age_${slug}_${index + 1}`,
        ageRangeSourceKey: spawn?.spawnAge || base?.spawnAge,
        newInitialCeoKey: `hby_ceo_initial_data_${slug}_${index + 1}`,
        initialCeoSourceKey: detailsByMode(base).historical?.initialCeos || base?.combatProfile,
        templateOverrides: compactObject({
          weight: payload.spawn?.weight,
          min_spawn_round: spawn?.minRound,
          max_spawn_round: spawn?.maxRound,
          subtype: payload.subtype,
        }),
        detailOverrides: detailOverrideFromSources(attribute, skill, unit, retinueOverride),
      });
      if (payload.armourPatch) {
        recipe.equipmentStatPatches.push({
          equipmentKey: payload.armourPatch.equipmentKey,
          statTable: payload.armourPatch.statTable,
          column: payload.armourPatch.column,
          value: payload.armourPatch.value,
        });
      }
    }
  });

  return recipe;
}

function compactObject(value) {
  return Object.fromEntries(
    Object.entries(value || {}).filter(([, item]) => item !== undefined && item !== null && item !== '')
  );
}

function validationItem(level, title, detail) {
  return { level, title, detail };
}

function renderValidation() {
  const items = [];
  const isCreate = state.mode === 'create';
  const name = isCreate ? $('createName').value.trim() : $('editName').value.trim();
  const minRound = Number($('editMinRound').value);
  const maxRound = Number($('editMaxRound').value);
  const eventKey = isCreate ? $('sourceSpawnEvent').value : $('editSpawnEvent').value;
  const armourInput = isCreate ? $('sourceArmourValue') : $('editArmourValue');
  const armourValue = armourInput ? nullableNumber(armourInput.value) : null;
  const unitPrefix = isCreate ? 'source' : 'edit';
  const unitInputs = ['ChargeBonus', 'Morale', 'PrimaryAmmo']
    .map((suffix) => $(`${unitPrefix}${suffix}`))
    .filter(Boolean);

  if (!name) {
    items.push(validationItem('error', '이름 필요', '저장 전에 표시 이름을 입력해야 합니다.'));
  }
  if (isCreate && characters().some((character) => character.name === name)) {
    items.push(validationItem('warning', '이름 중복 가능성', '기존 장수와 같은 표시 이름입니다. loc 충돌 검증이 필요합니다.'));
  }
  if (armourInput && !armourInput.disabled && (armourValue === null || armourValue < 0)) {
    items.push(validationItem('error', '방어값 확인', '방어값은 0 이상의 숫자여야 합니다.'));
  }
  if (unitInputs.some((input) => !input.disabled && (nullableNumber(input.value) === null || nullableNumber(input.value) < 0))) {
    items.push(validationItem('error', '유닛 수치 확인', '돌격 보너스, 사기, 탄약은 0 이상의 숫자여야 합니다.'));
  }
  if (!isCreate && minRound > maxRound) {
    items.push(validationItem('error', '등장 라운드 확인', '최소 라운드가 최대 라운드보다 클 수 없습니다.'));
  }
  if (['faction_join', 'incident_reward'].includes(eventKey)) {
    items.push(validationItem('warning', '이벤트 매핑 필요', '세력 합류/이벤트 보상은 incident, payload 매핑 검증이 필요합니다.'));
  }
  if (!state.queue.length) {
    items.push(validationItem('info', '작업 없음', '저장할 수정 또는 신규 생성 작업을 먼저 추가하세요.'));
  }

  for (const message of state.serverMessages) {
    const level = message.level === 'error' ? 'error' : message.level === 'warning' ? 'warning' : 'info';
    items.push(validationItem(level, message.title || message.code || 'server_message', message.detail || message.message || String(message)));
  }

  if (!items.length) {
    items.push(validationItem('ok', '저장 가능', '현재 화면 기준으로 막히는 항목은 없습니다.'));
  }

  const blocking = items.filter((item) => item.level === 'error').length;
  $('validationCount').textContent = blocking ? `${blocking}개 막힘` : `${items.length}개`;
  $('validationList').innerHTML = items.map((item) => `
    <article class="validation-item ${item.level}">
      <b>${escapeHtml(item.title)}</b>
      <span>${escapeHtml(item.detail)}</span>
    </article>
  `).join('');
}

function previewRecipe() {
  const actualRecipe = recipeFromQueue();
  state.lastRecipe = actualRecipe;
  const recipe = {
    ...actualRecipe,
    game: 'total_war_three_kingdoms',
    inputPack: $('inputPackPath').value,
    outputMode: $('saveModeSelect').value,
    note: 'UI 프로토타입용 미리보기입니다. 실제 pack 연동은 제외된 상태입니다.',
    operations: state.queue.map((item) => ({
      kind: item.kind,
      title: item.title,
      payload: item.payload,
    })),
  };
  $('recipeText').value = JSON.stringify(recipe, null, 2);
  $('recipeDialog').showModal();
}

function referencePackPaths() {
  return $('referencePackPaths').value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function serverPayload() {
  const saveMode = $('saveModeSelect').value;
  const inPlace = saveMode === 'in_place';
  return {
    adapter: 'rpfm',
    inputPath: $('inputPackPath').value,
    outputPath: inPlace ? '' : $('outputPackPath').value,
    referencePackPaths: referencePackPaths(),
    inPlace,
    delta: saveMode === 'patch_pack',
    recipe: recipeFromQueue(),
  };
}

async function postJson(path, payload) {
  if (location.protocol === 'file:') {
    throw new Error('실제 pack 연동은 로컬 서버에서 열어야 합니다. python3 -m tk_pack_builder.web 로 실행한 URL을 사용하세요.');
  }
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || '서버 요청 실패');
  }
  return data;
}

async function loadPack() {
  state.serverMessages = [validationItem('info', '팩 읽는 중', $('inputPackPath').value)];
  renderValidation();
  try {
    const data = await postJson('/api/open', {
      adapter: 'rpfm',
      inputPath: $('inputPackPath').value,
      referencePackPaths: referencePackPaths(),
      includeVanilla: false,
    });
    hydrateFromPackData(data.characters);
    const cacheText = data.cache?.hit ? 'DB 캐시 사용' : 'DB 캐시 갱신';
    const referenceOk = (data.characters?.referencePacks || []).filter((item) => item.ok).length;
    const referenceTotal = (data.characters?.referencePacks || []).length;
    const referenceText = referenceTotal ? ` · 참조 pack ${referenceOk}/${referenceTotal}` : '';
    state.serverMessages = [validationItem('info', '팩 읽기 완료', `${state.characters.length}명 로드 · ${cacheText}${referenceText}`)];
    renderAll();
  } catch (error) {
    state.serverMessages = [validationItem('error', '팩 읽기 실패', error.message)];
    renderValidation();
  }
}

async function validateServerRecipe() {
  state.serverMessages = [validationItem('info', '서버 검증 중', '현재 작업 큐를 CLI recipe로 변환했습니다.')];
  renderValidation();
  try {
    const data = await postJson('/api/validate', serverPayload());
    state.serverMessages = data.messages.length
      ? data.messages
      : [validationItem('ok', '서버 검증 통과', 'CLI 검증 기준으로 막히는 항목이 없습니다.')];
  } catch (error) {
    state.serverMessages = [validationItem('error', '서버 검증 실패', error.message)];
  }
  renderValidation();
}

async function buildServerPack() {
  const saveMode = $('saveModeSelect').value;
  const saveTarget = saveMode === 'in_place'
    ? '원본 수정'
    : saveMode === 'patch_pack'
      ? `패치 pack: ${$('outputPackPath').value}`
      : `Save As 원본 복사: ${$('outputPackPath').value}`;
  state.serverMessages = [validationItem('info', '저장 중', saveTarget)];
  renderValidation();
  try {
    const data = await postJson('/api/build', serverPayload());
    state.serverMessages = data.messages.length
      ? data.messages.map((message) => ({ level: message.level || 'info', code: message.code, message: message.message }))
      : [validationItem('ok', '저장 완료', 'pack 저장이 완료되었습니다.')];
  } catch (error) {
    state.serverMessages = [validationItem('error', '저장 실패', error.message)];
  }
  renderValidation();
}

function renderAll() {
  renderRoster();
  renderSelected();
  renderAppearanceGallery();
  renderQueue();
  renderValidation();
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

for (const button of document.querySelectorAll('.filter')) {
  button.addEventListener('click', () => {
    state.filter = button.dataset.filter;
    for (const item of document.querySelectorAll('.filter')) item.classList.remove('active');
    button.classList.add('active');
    renderRoster();
  });
}

$('searchInput').addEventListener('input', renderRoster);
$('editModeButton').addEventListener('click', () => setMode('edit'));
$('createModeButton').addEventListener('click', () => setMode('create'));
for (const button of document.querySelectorAll('.tab-btn')) {
  button.addEventListener('click', () => setWorkTab(button.dataset.tabTarget));
}
$('editCombatProfile').addEventListener('change', () => syncEquipmentSummary('edit', 'editCombatProfile'));
$('sourceCombatProfile').addEventListener('change', () => syncEquipmentSummary('source', 'sourceCombatProfile'));
$('editUnitProfile').addEventListener('change', () => syncUnitSummary('edit', 'editUnitProfile'));
$('sourceUnitProfile').addEventListener('change', () => syncUnitSummary('source', 'sourceUnitProfile'));
$('sourceBase').addEventListener('change', () => {
  const character = characters().find((item) => item.key === $('sourceBase').value);
  renderTitleSummary('source', character);
  renderValidation();
});
$('editImageSet').addEventListener('change', updateImagePreviews);
$('sourceImageSet').addEventListener('change', updateImagePreviews);
$('stageEditButton').addEventListener('click', stageEdit);
$('stageCreateButton').addEventListener('click', stageCreate);
$('loadPackButton').addEventListener('click', loadPack);
$('validateButton').addEventListener('click', validateServerRecipe);
$('buildButton').addEventListener('click', buildServerPack);
$('previewRecipeButton').addEventListener('click', previewRecipe);
$('closeRecipeButton').addEventListener('click', () => $('recipeDialog').close());
$('saveModeSelect').addEventListener('change', () => {
  $('outputPackPath').disabled = $('saveModeSelect').value === 'in_place';
  renderValidation();
});
$('saveDraftButton').addEventListener('click', () => {
  state.queue.push({
    kind: 'draft_note',
    type: '초안 저장',
    title: '작업 초안 저장',
    description: '연동 전 UI 흐름 확인용 상태입니다.',
    payload: {
      selectedKey: state.selectedKey,
      mode: state.mode,
    },
  });
  renderQueue();
  renderValidation();
});

for (const control of document.querySelectorAll('input, select')) {
  control.addEventListener('input', renderValidation);
  control.addEventListener('change', renderValidation);
}
$('referencePackPaths').addEventListener('input', renderValidation);
$('referencePackPaths').addEventListener('change', renderValidation);

renderAll();
