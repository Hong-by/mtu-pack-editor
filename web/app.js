const ELEMENTS = {
  earth: { label: '土', name: '토', subtype: '3k_general_earth' },
  fire: { label: '火', name: '화', subtype: '3k_general_fire' },
  wood: { label: '木', name: '목', subtype: '3k_general_wood' },
  water: { label: '水', name: '수', subtype: '3k_general_water' },
  metal: { label: '金', name: '금', subtype: '3k_general_metal' },
};

const SPAWN_EVENTS = [
  {
    key: 'campaign_start',
    name: '캠페인 시작 시 등록',
    note: '시작 시점부터 장수 풀에 포함',
    helpTitle: '새 캠페인 시작 때 바로 등록',
    helpText: '생성한 장수를 캠페인 시작 직후 플레이어 세력에 한 번 지급합니다. 테스트나 즉시 사용 장수에 맞습니다.',
    fields: ['등장 가중치/라운드 값은 DB에도 남지만, 실제 지급은 Lua가 한 번 처리합니다.'],
  },
  {
    key: 'delayed_join',
    name: '몇 턴 뒤 플레이어 세력에 합류',
    note: '최소 등장 턴부터 인간 플레이어 턴 시작에 1회 합류',
    helpTitle: '지정 턴부터 플레이어 세력에 합류',
    helpText: '플레이어 합류 턴에 입력한 턴부터 인간 플레이어 턴 시작 때 한 번 지급합니다. 예: 5면 5턴부터 지급됩니다.',
    fields: ['플레이어 합류 턴만 사용합니다.', '최대 턴은 이 이벤트에서 무시됩니다.'],
  },
  {
    key: 'round_pool',
    name: '라운드 조건으로 등장',
    note: '최소/최대 라운드와 가중치 사용',
    helpTitle: '게임의 장수 풀 조건만 설정',
    helpText: 'character_generation_templates의 가중치와 최소/최대 등장 라운드를 저장합니다. 플레이어 세력에 직접 지급하지는 않습니다.',
    fields: ['가중치가 높을수록 풀에서 뽑힐 가능성이 커집니다.', '최소/최대 등장 턴 범위 안에서만 후보가 됩니다.'],
  },
  {
    key: 'disabled',
    name: '자동 등장 안 함',
    note: '직접 배치나 별도 이벤트 전용',
    helpTitle: '등장 로직을 추가하지 않음',
    helpText: '장수 DB와 선택한 구성요소만 만들고, 자동 합류 Lua나 풀 등장 의도는 넣지 않습니다.',
    fields: ['나중에 직접 스크립트나 다른 모드에서 호출할 때 사용합니다.'],
  },
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
  loadingPack: false,
  editingQueueIndex: null,
  skillTreeDrafts: {},
  activeSkillNode: null,
};

const MANUAL_TITLE_EFFECTS = [
  ['사마예', '철학 있는 통치자', '전문성 +20, 결의 +50, 본능 +30, 회복력 +1, 방어할 때 사기 +10, 모든 부대에 화살 및 탄환 +25%(세력 전체)(상국, 세력지도자, 후계자일 때)'],
  ['사마영', '사랑받는 통치자', '책략 +20, 권위 +25, 회복력 +1, 만족도 +10, 귀족들의 지지 +5, 농업 수입 +50%(세력 전체 / 상국 세력지도자, 후계자일 때)'],
  ['사마위', '분노를 품은 장군', '전문성 +30, 본능 +50, 권위 +20, 회복력 +1, 근접 피해 +10%, 캠페인 상 이동거리 +15%, 충원률 +10%(세력전체)(상국, 세력지도자, 후계자일 때)'],
  ['사마월', '황실 감독관', '전문성 +50, 책략 +50, 권위 +20, 회복력 +1, 전투 후 군관 포획 확률 +25%(아군), 근접 보병의 근접 회피 +15, 대부분의 세력 우호도 +10(세력전체)(상국, 세력지도자, 후계자일 때)'],
  ['사마경', '황실 섭정', '전문성 +20, 결의 +30, 권위 +50, 회복력 +1, 부여 효과: 섬뜩함 유발(아군 수행원), 공격할 때 사기 +10(세력 전체 / 상국, 지도자, 후계자일 때)'],
  ['사마옹', '기민한 방어자', '결의 +30, 본능 +50, 권위 +20, 회복력 +1, 지원군 적용 범위 +50%(세력 전체 / 상국, 지도자, 후계자일 때), 캠페인 지도상 이동거리 +15%(세력 전체 / 상국, 지도자, 후계자일 때), 속도 +20%(아군)'],
  ['사마륜', '찬탈자', '전문성 +20, 책략 +65, 권위 +50, 음모 +2, 회복력 +1, 은밀한 이동(아군 수행원), 유격 배치(해당 군단), 대부분 세력에 대한 외교 불이익 -10(세력전체)(상국, 세력지도자, 후계자일 때)'],
  ['사마량', '정당한 섭정', '결의 +50, 본능 +20, 권위 +30, 회복력 +1, 병력 동원 턴 -1, 수행원 유지비 -10%(세력전체)(책사, 세력 지도자, 후계자일 때)'],
  ['유굉', '한나라의 위대한 천자', '결의 +50, 본능 +50, 권위 +20, 회복력 +1, 만족도 +25(세력 전체 / 상국, 세력지도자, 후계자일 때), 사기 +15(세력 전체 / 상국, 세력지도자, 후계자일 때), 가문 영지의 수입 +200%(상국, 세력지도자, 후계자일 때)'],
  ['유굉', '우유부단한 황제', '결의 +30, 본능 +10, 권위 +20, 회복력 +1, 사기 +6(세력 전체 / 상국, 세력지도자, 후계자일 때), 가문 영지의 수입 +200%(상국, 세력지도자, 후계자일 때)'],
  ['손책', '소패왕', '전문성 +10, 본능 +20, 권위 +30, 회복력 +1, 기병 돌격 부가효과 +100%, 충격기병 피해 +15%(세력전체)(상국, 세력지도자, 후계자일 때)'],
  ['노숙', '너그러운 사절', '전문성 +5, 결의 +10, 책략 +15, 파견임무 잉여자원 분배 해금, 건설시간 -2(세력전체)(상국, 세력지도자, 후계자일 때)'],
  ['장굉', '엄격한 책사', '책략 +25, 권위 +30, 회복력 +1, 만족도 +15(세력 전체 / 상국, 지도자, 후계자일 때)'],
  ['공손찬', '철권 장군', '전문성 +10, 본능 +20, 권위 +30, 회복력 +1, 지원군 적용 범위 +50%, 모든 충격 기병의 갑옷 +12%(세력전체)(상국, 세력지도자, 후계자일 때)'],
  ['원소', '탁월한 사령관', '결의 +30, 본능 +10, 권위 +20, 회복력 +1, 가문 영토 수입 +50%, 사기 +6, 대장 수행원 모집 비용 및 유지비 -50%(세력전체)(상국, 세력지도자, 후계자일 때)'],
  ['마초', '현명한 전사', '전문성 +30, 결의 +10, 본능 +20, 회복력 +1, 강족 부대 유지비 -15%, 모든 충격 기병 갑옷 +15%, 모든 충격 기병 근접 피해 +15%(세력전체)(상국, 세력지도자, 후계자일 때)'],
  ['이각', '포악한 호걸', '결의 +7, 본능 +15, 권위 +8, 회복력 +1, 모든 인물들의 만족도 -10, 수행원 유지비 -10%, 충원 +5%(세력 전체 / 상국, 지도자, 후계자일 때)'],
  ['장패', '교활한 수완가', '결의 +20, 책략 +10, 회복력 +1, 전투 후 전리품 수입 +15%(통솔할 때), 대장 수행원들의 모집 및 유지비 -25%(상국, 세력지도자, 후계자일 때)'],
  ['유총', '진왕', '전문성 +15, 결의 +40, 권위 +25, 회복력 +1, 공포 유발, 연노 원거리 피해 +10%(세력전체)(상국, 세력지도자, 후계자일 때), 새로 모집한 모든 원거리 부대의 등급 +2(세력전체)(상국, 세력지도자, 후계자일 때)'],
  ['낙준', '백성들의 수호자', '결의 +25, 책략 +25, 권위 +15, 모든 수입원으로부터 얻는 수입 +10%(세력전체)(상국, 세력지도자, 후계자일 때)'],
  ['하의', '백성의 군주', '결의 +20, 본능 +20, 권위 +20, 회복력 +1, 원거리 부대 유지비 -15%, 사기 +6(세력 전체 / 세력 지도자이거나 인공장군일 때)'],
  ['유장', '평화 지지자', '책략 +10, 본능 +5, 권위 +15, 식량생산 +50%(세력 승상, 지도자, 후계자일 때)'],
  ['장로', '칭호명 미확인', '전문성 +10, 결의 +15, 권위 +5, 식량생산 +100%(세력전체)(상국, 세력지도자, 후계자일 때)'],
].map(([owner, title, effects]) => ({ owner, title, effects }));

const $ = (id) => document.getElementById(id);

function selectedCharacter() {
  return state.characters.find((character) => character.key === state.selectedKey) || state.characters[0];
}

function characters() {
  return state.characters;
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
  return characters().filter(hasUniqueImageSet);
}

function cloneBaseCharacters() {
  return browsableCharacters();
}

function titleSourceCharacters() {
  return characters().filter((character) => character.titleInitialCeoKey || character.titleKey);
}

function titleChoiceValue(character) {
  return character?.titleChoiceKey || character?.key || '';
}

function manualTitleChoices() {
  return MANUAL_TITLE_EFFECTS.map((effect, index) => {
    const ownerKey = normalizeKoreanText(effect.owner);
    const matchedCharacter = characters().find((character) => {
      const names = [
        character.name,
        character.titleOwnerName,
        sheetHeroInfoFor(character.key)?.kr,
      ];
      return names.some((name) => normalizeKoreanText(name) === ownerKey);
    });
    return {
      ...(matchedCharacter || {}),
      key: matchedCharacter?.key || `manual_title_effect_${index}`,
      titleChoiceKey: `${matchedCharacter?.key || 'manual'}::manual_title::${index}`,
      name: effect.owner,
      titleOwnerName: effect.owner,
      titleName: effect.title,
      titleKey: matchedCharacter?.titleKey || '효과 정리 전용',
      titleInitialCeoKey: matchedCharacter?.titleInitialCeoKey || '',
      titleLocKey: matchedCharacter?.titleLocKey || '',
      manualTitleEffect: effect,
      manualTitleOnly: !matchedCharacter,
    };
  });
}

function allTitleChoices() {
  const manual = manualTitleChoices();
  const regular = titleSourceCharacters().filter((character) => {
    const owner = normalizeKoreanText(character.titleOwnerName || character.name);
    const title = normalizeKoreanText(character.titleName);
    return !manual.some((item) => (
      normalizeKoreanText(item.titleOwnerName || item.name) === owner
      && normalizeKoreanText(item.titleName) === title
    ));
  });
  return sortTitleCandidates([...manual, ...regular]);
}

function resolveTitleChoice(value) {
  const key = String(value || '');
  return allTitleChoices().find((item) => titleChoiceValue(item) === key)
    || characters().find((item) => item.key === key)
    || null;
}

function packTemplateCharacters() {
  return characters().filter((character) => {
    if (character.source === 'reference') return false;
    const details = detailsByMode(character);
    return Boolean(details.historical || details.romance);
  });
}

function appearanceSets() {
  const artSets = (state.options?.artSets || [])
    .filter((item) => item?.key)
    .map((item) => ({
      key: item.key,
      name: item.label || friendlyKey(item.key),
      element: elementFromSubtype(`${item.key} ${item.uniform || ''}`),
      portrait: portraitGlyph(item.label || item.key),
      artSet: item.key,
      imageSetName: item.label || friendlyKey(item.key),
      modelSetName: item.uniformLabel || item.uniform || friendlyKey(item.key),
      portraitPath: item.portrait || '',
      cardPath: item.card || '',
      portraitImagePath: item.portraitImagePath || '',
      portraitImageSourcePath: item.portraitImageSourcePath || '',
      cardImagePath: item.cardImagePath || '',
      cardImageSourcePath: item.cardImageSourcePath || '',
      imageAssets: item.imageAssets || [],
      uniform: item.uniform || '',
      uniformLabel: item.uniformLabel || '',
      referenceSourcePath: item.referenceSourcePath || '',
      externalImageSet: Boolean(item.externalImageSet),
      hasImage: Boolean(item.portraitImagePath || item.cardImagePath),
    }));
  if (artSets.length) {
    return artSets.sort((a, b) => Number(b.hasImage) - Number(a.hasImage) || a.name.localeCompare(b.name));
  }
  return characters().map((item) => appearanceFromCharacter(item));
}

function appearanceFromCharacter(character) {
  return {
    key: character?.artSet || character?.key || '',
    name: character?.imageSetName || character?.name || '-',
    element: character?.element || 'earth',
    portrait: character?.portrait || '將',
    artSet: character?.artSet || '',
    imageSetName: character?.imageSetName || '-',
    modelSetName: character?.modelSetName || '-',
    portraitPath: character?.portraitPath || '',
    cardPath: character?.cardPath || '',
    portraitImagePath: character?.portraitImagePath || '',
    portraitImageSourcePath: character?.portraitImageSourcePath || '',
    cardImagePath: character?.cardImagePath || '',
    cardImageSourcePath: character?.cardImageSourcePath || '',
    imageAssets: character?.imageAssets || [],
    uniform: character?.uniform || '',
    hasImage: Boolean(character?.portraitImagePath || character?.cardImagePath),
  };
}

function appearanceByKey(key) {
  return appearanceSets().find((item) => item.key === key)
    || appearanceFromCharacter(characters().find((item) => item.key === key || item.artSet === key));
}

function imageAssetsFromAppearance(appearance) {
  if (appearance?.externalImageSet) {
    return [];
  }
  if (appearance?.imageAssets?.length) {
    return appearance.imageAssets.map((asset) => ({
      path: asset.path,
      sourcePath: asset.sourcePath || '',
    }));
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

function characterByAppearanceKey(key) {
  if (!key) return null;
  const candidates = characters().filter((item) => item.key === key || item.artSet === key);
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

const SEARCHABLE_SELECT_IDS = new Set([
  'editImageSet',
  'editModelSet',
  'sourceImageSet',
  'sourceModelSet',
  'sourceBase',
  'sourceSkill',
  'sourceTitle',
  'editAttributeSet',
  'sourceAttributeSet',
  'editCombatProfile',
  'sourceCombatProfile',
  'editUnitProfile',
  'sourceUnitProfile',
  'sourceSpawn',
  'editHistoricalSkill',
  'editRomanceSkill',
]);

const heroNameCache = new Map();

function sheetHeroMap() {
  return window.SHEET_HERO_NAME_MAP || {};
}

function sheetHeroAliasMap() {
  return window.SHEET_HERO_ALIAS_MAP || {};
}

function sheetTitleMap() {
  return window.SHEET_TITLE_NAME_MAP || {};
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

function sheetTitleInfoFor(titleKey, characterKey = '') {
  const titles = sheetTitleMap();
  if (titles[titleKey]) return titles[titleKey];
  const slug = slugFromKey(characterKey || titleKey);
  return Object.values(titles).find((item) => item.slug === slug) || null;
}

function normalizeKoreanText(value) {
  return String(value || '').replace(/\s+/g, '').replace(/[·:;.,]/g, '').toLowerCase();
}

function manualTitleEffectFor(ownerName = '', titleName = '') {
  const owner = normalizeKoreanText(ownerName);
  const title = normalizeKoreanText(titleName);
  const ownerMatches = MANUAL_TITLE_EFFECTS.filter((item) => normalizeKoreanText(item.owner) === owner);
  if (!ownerMatches.length) return null;
  const exact = ownerMatches.find((item) => {
    const itemTitle = normalizeKoreanText(item.title);
    return itemTitle && title && (itemTitle === title || itemTitle.includes(title) || title.includes(itemTitle));
  });
  if (exact) return exact;
  const titleMissing = !title || title.includes('미확인');
  return titleMissing && ownerMatches.length === 1 ? ownerMatches[0] : null;
}

function titleEffectFor(character) {
  if (character?.manualTitleEffect) return character.manualTitleEffect;
  return manualTitleEffectFor(character?.titleOwnerName || character?.name, character?.titleName);
}

function titleOptionLabel(character) {
  const effect = titleEffectFor(character);
  const translatedTitle = character.titleName && character.titleName !== '칭호 미확인'
    ? character.titleName
    : friendlyKey(character.titleKey || character.titleInitialCeoKey);
  const effectText = effect ? ` · ${effect.effects}` : '';
  return `${character.name} · ${translatedTitle}${effectText}`;
}

function sortTitleCandidates(items) {
  return [...items].sort((a, b) => {
    const aEffect = Number(Boolean(titleEffectFor(a)));
    const bEffect = Number(Boolean(titleEffectFor(b)));
    if (aEffect !== bEffect) return bEffect - aEffect;
    const aTranslated = Number(Boolean(a.titleName && a.titleName !== '칭호 미확인'));
    const bTranslated = Number(Boolean(b.titleName && b.titleName !== '칭호 미확인'));
    if (aTranslated !== bTranslated) return bTranslated - aTranslated;
    return a.name.localeCompare(b.name, 'ko');
  });
}

function hydrateFromPackData(characterData) {
  const summary = characterData?.pack;
  if (!summary?.characters?.length) return;
  state.options = summary;
  state.characters = summary.characters.map((item) => normalizePackCharacter(item, summary));
  state.selectedKey = (browsableCharacters()[0] || state.characters[0]).key;
  state.queue = [];
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
  const titleInfo = item.titleInfo || {};
  const sheetHero = sheetHeroInfoFor(item.key);
  const displayName = sheetHero?.kr || item.label || item.displayName || friendlyKey(item.key);
  const sheetTitle = sheetTitleInfoFor(titleInfo.ceoNodeKey || titleInfo.initialCeoKey || '', item.key);
  const manualTitle = manualTitleEffectFor(displayName, sheetTitle?.krTitle || titleInfo.label);
  return {
    key: item.key,
    name: displayName,
    englishName: sheetHero?.en || item.displayName || item.label || '',
    hanjaName: sheetHero?.hanja || '',
    element,
    portrait: portraitGlyph(displayName || item.key),
    artSet: item.artSet || '',
    imageSetName: artSet?.label || friendlyKey(item.artSet || item.key),
    modelSetName: item.uniformLabel || artSet?.uniformLabel || item.uniform || artSet?.uniform || friendlyKey(item.artSet || item.key),
    historicalSkill: historical.skillSet || '-',
    romanceSkill: romance.skillSet || historical.skillSet || '-',
    retinue: historical.retinue || romance.retinue || '-',
    attributeSet: historical.attributeSet || romance.attributeSet || '-',
    combatProfile: combatStats.weaponCeo || combatStats.armourCeo || historical.initialCeos || romance.initialCeos || '장비 정보 미확인',
    titleName: sheetTitle?.krTitle || manualTitle?.title || titleInfo.label || '칭호 미확인',
    titleOwnerName: sheetTitle?.krName || manualTitle?.owner || displayName,
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
    armourFromReference: Boolean(combatStats.armourFromReference),
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
    imageAssets: item.imageAssets || artSet?.imageAssets || [],
    hasImage: Boolean(item.portraitImagePath || item.cardImagePath || artSet?.portraitImagePath || artSet?.cardImagePath),
    uniform: item.uniform || artSet?.uniform || '',
    uniformLabel: item.uniformLabel || artSet?.uniformLabel || '',
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
  const canPatchArmour = Boolean(character.source !== 'reference' && !character.armourFromReference && character.armourCeo && character.armourStatKey);
  const armourWarning = character.armourStatKey?.includes('_unique')
    ? '고유 방어구라 영향 범위가 좁습니다.'
    : '공용 방어구면 같은 key를 쓰는 다른 유닛에도 영향을 줄 수 있습니다.';
  const armourNote = canPatchArmour
    ? armourWarning
    : '연결된 방어구 CEO를 찾지 못했습니다. 값은 입력할 수 있지만 저장 시 방어구 패치는 제외됩니다.';
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
      <input id="${prefix}ArmourValue" type="number" min="0" value="${escapeHtml(character.baseDefense ?? '')}">
      <small>${escapeHtml(armourNote)}</small>
    </label>
  `;
}

function unitBrief(character) {
  if (!character) return '유닛 정보 미확인';
  return `돌격 ${combatValue(character.unitChargeBonus)} · 사기 ${combatValue(character.unitMorale)} · 탄약 ${combatValue(character.unitPrimaryAmmo)}`;
}

function unitSummaryMarkup(character, prefix) {
  if (!character) return '<p class="empty">유닛 정보를 확인할 수 없습니다.</p>';
  const canCloneUnit = Boolean(character.landUnitKey)
    && !character.unitFromReference
    && [character.unitChargeBonus, character.unitMorale, character.unitPrimaryAmmo].some((value) => value !== null);
  const unitNote = canCloneUnit
    ? '돌격 보너스/사기/탄약은 새 land_units row로 복제 저장됩니다. 근공/근방은 현재 확인용입니다.'
    : '연결된 land_units row를 찾지 못했습니다. 값은 입력할 수 있지만 저장 시 병종 수치 패치는 제외됩니다.';
  const rows = [
    ['land unit', character.landUnitKey || '미확인'],
    ['분류', [character.unitCategory, character.unitClass].filter(Boolean).join(' / ') || '미확인'],
    ['근접 공격', combatValue(character.unitMeleeAttack)],
    ['근접 방어', combatValue(character.unitMeleeDefence)],
  ];
  return `
    <div class="equipment-note">${escapeHtml(unitNote)}</div>
    ${rows.map(([label, value]) => `
      <div class="equipment-row">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>
    `).join('')}
    <div class="unit-stat-grid">
      <label>
        <span>돌격 보너스</span>
        <input id="${prefix}ChargeBonus" type="number" min="0" value="${escapeHtml(character.unitChargeBonus ?? '')}">
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

function renderRoster() {
  const query = $('searchInput').value.trim().toLowerCase();
  const list = $('characterList');
  list.innerHTML = '';
  const visibleCharacters = browsableCharacters();
  if (!visibleCharacters.some((character) => character.key === state.selectedKey) && visibleCharacters.length) {
    state.selectedKey = visibleCharacters[0].key;
  }
  const filtered = visibleCharacters.filter((character) => {
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
      state.editingQueueIndex = null;
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
  $('appearanceGallery').innerHTML = browsableCharacters().map((character) => `
    <button class="appearance-card ${character.key === selectedCharacter().key ? 'active' : ''}" data-key="${escapeHtml(character.artSet || character.key)}" type="button">
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
  $('createMinRound').value = character.minRound;
  $('createMaxRound').value = character.maxRound;

  const selectableCharacters = browsableCharacters().length ? browsableCharacters() : characters();
  const baseCandidates = cloneBaseCharacters();
  const selectedBase = packTemplateCharacters()[0] || baseCandidates[0] || character;
  const titleCandidates = allTitleChoices();
  const appearances = appearanceSets().filter((item) => {
    const combined = `${item.artSet || ''} ${item.imageSetName || ''} ${item.portraitPath || ''} ${item.cardPath || ''}`.toLowerCase();
    const referenceSource = String(item.referenceSourcePath || '').toLowerCase();
    const isBfg = item.externalImageSet || referenceSource.includes('bfg_');
    return isBfg || (item.hasImage && !combined.includes('generic') && !combined.includes('scripted'));
  });
  fillSelect('editImageSet', appearances.map((item) => option(item.key, `${item.hasImage ? '■' : '□'} ${item.name} · ${item.artSet}`)));
  fillSelect('editModelSet', appearances.map((item) => option(item.key, `${item.name} · ${item.modelSetName}`)));
  fillSelect('sourceImageSet', appearances.map((item) => option(item.key, `${item.hasImage ? '■' : '□'} ${item.name} · ${item.artSet}`)));
  fillSelect('sourceModelSet', appearances.map((item) => option(item.key, `${item.name} · ${item.modelSetName}`)));
  fillSelect('sourceBase', baseCandidates.map((item) => option(item.key, item.name)));
  fillSelect('sourceSkill', selectableCharacters.map((item) => option(item.key, `${item.name} · ${item.historicalSkill}`)));
  fillSelect('sourceTitle', titleCandidates.map((item) => option(titleChoiceValue(item), titleOptionLabel(item))));
  fillSelect('editAttributeSet', selectableCharacters.map((item) => option(item.key, `${item.name} · ${item.attributeSet}`)));
  fillSelect('sourceAttributeSet', selectableCharacters.map((item) => option(item.key, `${item.name} · ${item.attributeSet}`)));
  fillSelect('editCombatProfile', selectableCharacters.map((item) => option(item.key, `${item.name} · ${equipmentBrief(item)}`)));
  fillSelect('sourceCombatProfile', selectableCharacters.map((item) => option(item.key, `${item.name} · ${equipmentBrief(item)}`)));
  fillSelect('editUnitProfile', selectableCharacters.map((item) => option(item.key, `${item.name} · ${item.unitProfile}`)));
  fillSelect('sourceUnitProfile', selectableCharacters.map((item) => option(item.key, `${item.name} · ${item.unitProfile}`)));
  fillSelect('sourceSpawn', selectableCharacters.map((item) => option(item.key, `${item.name} · ${item.spawnAge}`)));
  fillSelect('editSpawnEvent', SPAWN_EVENTS.map((item) => option(item.key, `${item.name} · ${item.note}`)));
  fillSelect('sourceSpawnEvent', SPAWN_EVENTS.map((item) => option(item.key, `${item.name} · ${item.note}`)));
  fillSelect('editSubtype', Object.entries(ELEMENTS).map(([key, item]) => option(item.subtype, `${item.label} ${item.name}`)));
  fillSelect('createSubtype', Object.entries(ELEMENTS).map(([key, item]) => option(item.subtype, `${item.label} ${item.name}`)));
  fillSelect('editHistoricalSkill', selectableCharacters.map((item) => option(item.key, `${item.name} · ${item.historicalSkill}`)));
  fillSelect('editRomanceSkill', selectableCharacters.map((item) => option(item.key, `${item.name} · ${item.romanceSkill}`)));

  $('editImageSet').value = character.artSet || character.key;
  $('editModelSet').value = character.artSet || character.key;
  $('sourceImageSet').value = character.artSet || character.key;
  $('sourceModelSet').value = character.artSet || character.key;
  $('sourceBase').value = selectedBase.key;
  $('sourceSkill').value = character.key;
  const selectedTitleChoice = titleCandidates.find((item) => item.key === character.key) || titleCandidates[0];
  $('sourceTitle').value = titleChoiceValue(selectedTitleChoice);
  $('editAttributeSet').value = character.key;
  $('sourceAttributeSet').value = character.key;
  $('editCombatProfile').value = character.key;
  $('sourceCombatProfile').value = character.key;
  $('editUnitProfile').value = character.key;
  $('sourceUnitProfile').value = character.key;
  $('sourceSpawn').value = character.key;
  $('editSpawnEvent').value = character.spawnEvent;
  $('sourceSpawnEvent').value = 'campaign_start';
  $('editSubtype').value = elementMeta(character.element).subtype;
  $('createSubtype').value = elementMeta(character.element).subtype;
  $('editHistoricalSkill').value = character.key;
  $('editRomanceSkill').value = character.key;
  $('createName').value = `${character.name} 파생`;
  renderTitleSummary('edit', character);
  renderTitleSummary('source', resolveTitleChoice($('sourceTitle').value) || selectedBase);
  syncEquipmentSummary('edit', 'editCombatProfile');
  syncEquipmentSummary('source', 'sourceCombatProfile');
  syncUnitSummary('edit', 'editUnitProfile');
  syncUnitSummary('source', 'sourceUnitProfile');
  updateImagePreviews();
  updateAllSpawnFieldLabels();
  renderSkillTreeEditors();
}

function option(value, label) {
  return { value, label };
}

function fillSelect(id, options) {
  const select = $(id);
  select._allOptions = options;
  renderSelectOptions(select, options, select.value);
  enhanceSearchableSelect(select);
  const input = select.parentNode.querySelector(`[data-search-for="${select.id}"]`);
  if (input) input.value = '';
}

function renderSelectOptions(select, options, selectedValue = select.value) {
  const previousValue = String(selectedValue || '');
  select.innerHTML = '';
  for (const item of options) {
    const optionEl = document.createElement('option');
    optionEl.value = item.value;
    optionEl.textContent = item.label;
    select.appendChild(optionEl);
  }
  if (previousValue && [...select.options].some((item) => item.value === previousValue)) {
    select.value = previousValue;
  }
}

function setSelectValue(id, value) {
  const select = $(id);
  if (!select) return;
  const stringValue = String(value ?? '');
  if (select._allOptions?.length && ![...select.options].some((item) => item.value === stringValue)) {
    renderSelectOptions(select, select._allOptions, stringValue);
  }
  if ([...select.options].some((item) => item.value === stringValue)) {
    select.value = stringValue;
  }
}

function enhanceSearchableSelect(select) {
  if (!SEARCHABLE_SELECT_IDS.has(select.id) || select.dataset.searchReady === '1') return;
  const input = document.createElement('input');
  input.className = 'select-search';
  input.type = 'search';
  input.placeholder = '검색해서 목록 줄이기';
  input.autocomplete = 'off';
  input.dataset.searchFor = select.id;
  select.parentNode.insertBefore(input, select);
  input.addEventListener('input', () => filterSelectOptions(select));
  input.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      select.focus();
    }
  });
  select.dataset.searchReady = '1';
}

function filterSelectOptions(select) {
  const input = select.parentNode.querySelector(`[data-search-for="${select.id}"]`);
  const query = String(input?.value || '').trim().toLowerCase();
  const allOptions = select._allOptions || [];
  const selectedValue = select.value;
  const filtered = query
    ? allOptions.filter((item) => `${item.label} ${item.value}`.toLowerCase().includes(query))
    : allOptions;
  const selectedOption = allOptions.find((item) => item.value === selectedValue);
  const nextOptions = selectedOption && !filtered.some((item) => item.value === selectedValue)
    ? [selectedOption, ...filtered]
    : filtered;
  renderSelectOptions(select, nextOptions, selectedValue);
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
  const effect = titleEffectFor(character);
  return character.titleName || friendlyKey(character.titleKey);
}

function titleSummaryMarkup(character) {
  if (!character) return '<p class="empty">칭호 정보를 확인할 수 없습니다.</p>';
  const effect = titleEffectFor(character);
  const rows = [
    ['칭호 주인', character.titleOwnerName || character.name || '미확인'],
    ['현재 칭호', character.titleName || '미확인'],
  ];
  return `
    ${effect ? `
      <div class="title-effect">
        <strong>${escapeHtml(effect.owner)} - ${escapeHtml(effect.title)}</strong>
        <span>${escapeHtml(effect.effects)}</span>
      </div>
    ` : ''}
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
  const imagePath = character.portraitImagePath || character.cardImagePath;
  const imageSourcePath = character.portraitImagePath ? character.portraitImageSourcePath : character.cardImageSourcePath;
  const portraitUrl = assetUrl(imagePath, imageSourcePath);
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
  const imagePath = character.portraitImagePath || character.cardImagePath;
  const imageSourcePath = character.portraitImagePath ? character.portraitImageSourcePath : character.cardImageSourcePath;
  const url = assetUrl(imagePath, imageSourcePath);
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
  const appearance = appearanceByKey($(selectId).value);
  $(containerId).innerHTML = imagePreviewMarkup(appearance, modeLabel);
}

function updateImagePreviews() {
  updateImagePreview('editImagePreview', 'editImageSet', '기존 장수 수정');
  updateImagePreview('sourceImagePreview', 'sourceImageSet', '신규 장수 생성');
}

function updateSpawnFieldLabels(prefix) {
  const isCreate = prefix === 'create';
  const eventSelect = $(isCreate ? 'sourceSpawnEvent' : 'editSpawnEvent');
  const minLabel = $(`${prefix}MinRoundLabel`);
  const maxLabel = $(`${prefix}MaxRoundLabel`);
  const minNote = $(`${prefix}MinRoundNote`);
  const maxNote = $(`${prefix}MaxRoundNote`);
  if (!eventSelect || !minLabel || !maxLabel) return;
  const delayed = eventSelect.value === 'delayed_join';
  minLabel.textContent = delayed ? '플레이어 합류 턴' : (isCreate ? '최소 등장 턴' : '최소 라운드');
  maxLabel.textContent = delayed ? '최대 턴(사용 안 함)' : (isCreate ? '최대 등장 턴' : '최대 라운드');
  if (minNote) minNote.textContent = delayed ? '예: 5 입력 시 5턴부터 인간 플레이어 턴 시작에 1회 합류합니다.' : '';
  if (maxNote) maxNote.textContent = delayed ? '이 이벤트는 합류 턴만 사용하고 최대 턴은 무시됩니다.' : '';
  renderSpawnHelp(prefix);
}

function updateAllSpawnFieldLabels() {
  updateSpawnFieldLabels('edit');
  updateSpawnFieldLabels('create');
}

function renderSpawnHelp(prefix) {
  const isCreate = prefix === 'create';
  const eventSelect = $(isCreate ? 'sourceSpawnEvent' : 'editSpawnEvent');
  const target = $(`${prefix}SpawnHelp`);
  if (!eventSelect || !target) return;
  const meta = spawnEventMeta(eventSelect.value);
  target.innerHTML = `
    <strong>${escapeHtml(meta.helpTitle || meta.name)}</strong>
    <p>${escapeHtml(meta.helpText || meta.note)}</p>
    <ul>
      ${(meta.fields || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('')}
    </ul>
  `;
}

function setMode(mode) {
  state.mode = mode;
  for (const button of document.querySelectorAll('.mode-btn')) {
    button.classList.toggle('active', button.dataset.mode === mode);
  }
  $('editPanel').classList.toggle('active', mode === 'edit');
  $('createPanel').classList.toggle('active', mode === 'create');
  refreshStageButtons();
  updateAllSpawnFieldLabels();
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
  if (!input || character?.source === 'reference' || character?.armourFromReference || !character?.armourCeo || !character?.armourStatKey) return null;
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
  if (!character?.landUnitKey || character?.unitFromReference) return null;
  const fields = [
    ['ChargeBonus', 'charge_bonus', character.unitChargeBonus],
    ['Morale', 'morale', character.unitMorale],
    ['PrimaryAmmo', 'primary_ammo', character.unitPrimaryAmmo],
  ];
  const overrides = {};
  const changes = [];
  for (const [suffix, column, previousValue] of fields) {
    const input = $(`${prefix}${suffix}`);
    if (!input) continue;
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

function currentQueueEditKind() {
  const item = state.queue[state.editingQueueIndex];
  if (!item) return null;
  return item.kind;
}

function queueItemNumberFor(kind) {
  return currentQueueEditKind() === kind ? state.editingQueueIndex + 1 : state.queue.length + 1;
}

function commitQueueItem(item) {
  const editingKind = currentQueueEditKind();
  if (editingKind === item.kind) {
    state.queue[state.editingQueueIndex] = item;
  } else {
    state.queue.push(item);
    state.editingQueueIndex = state.queue.length - 1;
  }
  renderQueue();
  refreshStageButtons();
  renderValidation();
}

function refreshStageButtons() {
  const editingKind = currentQueueEditKind();
  $('stageEditButton').textContent = editingKind === 'patch_character' ? '선택 작업 수정 반영' : '수정 작업에 추가';
  $('stageCreateButton').textContent = editingKind === 'clone_character' ? '선택 작업 수정 반영' : '신규 생성 작업에 추가';
}

function stageEdit() {
  const character = selectedCharacter();
  if (character.source === 'reference') {
    state.serverMessages = [validationItem('warning', '참조 장수 수정 보류', '참조 pack 장수는 현재 pack 내부 row가 아니어서 기존 장수 수정 대상에서 제외됩니다. 신규 생성 재료로만 사용하세요.')];
    renderValidation();
    return;
  }
  const imageSet = appearanceByKey($('editImageSet').value);
  const modelSet = appearanceByKey($('editModelSet').value);
  const hist = characters().find((item) => item.key === $('editHistoricalSkill').value);
  const romance = characters().find((item) => item.key === $('editRomanceSkill').value);
  const attribute = characters().find((item) => item.key === $('editAttributeSet').value);
  const combat = characters().find((item) => item.key === $('editCombatProfile').value);
  const unit = characters().find((item) => item.key === $('editUnitProfile').value);
  const spawnEvent = spawnEventMeta($('editSpawnEvent').value);
  const armourPatch = armourPatchFrom('edit', combat);
  const itemNumber = queueItemNumberFor('patch_character');
  const editSlug = slugify(`${character.key}_${itemNumber}`);
  const landUnitClone = unitStatCloneFrom('edit', unit, editSlug, itemNumber);
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
    skillTree: skillTreeSnapshot('edit'),
  };
  commitQueueItem({
    kind: 'patch_character',
    type: '기존 수정',
    title: `${character.name} 수정`,
    description: `${$('editName').value} · 이미지 ${imageSet?.name || '-'} · 모델 ${modelSet?.name || '-'} · 능력치 ${attribute?.name || '-'} · 장비 유지(${equipmentBrief(combat)})${armourPatch ? ` · 방어값 ${armourPatch.previousValue}→${armourPatch.value}` : ''} · 병종 ${unit?.name || '-'}${unitPatchDescription(landUnitClone)} · 등장 이벤트 ${spawnEvent.name} · 역사 ${hist?.name || '-'} · 낭만 ${romance?.name || '-'}`,
    payload,
  });
}

function stageCreate() {
  const imageSet = appearanceByKey($('sourceImageSet').value);
  const appearanceBase = characterByAppearanceKey(imageSet?.key || $('sourceImageSet').value);
  const base = appearanceBase || characters().find((item) => item.key === $('sourceBase').value);
  if (!base) {
    state.serverMessages = [validationItem('error', '신규 생성 준비 실패', '새 장수를 만들 기본 템플릿을 자동 선택하지 못했습니다. pack을 다시 읽어주세요.')];
    renderValidation();
    return;
  }
  const modelSet = appearanceByKey($('sourceModelSet').value);
  const skill = characters().find((item) => item.key === $('sourceSkill').value);
  const titleSource = resolveTitleChoice($('sourceTitle').value);
  const attribute = characters().find((item) => item.key === $('sourceAttributeSet').value);
  const combat = characters().find((item) => item.key === $('sourceCombatProfile').value);
  const unit = characters().find((item) => item.key === $('sourceUnitProfile').value);
  const spawn = characters().find((item) => item.key === $('sourceSpawn').value);
  const spawnEvent = spawnEventMeta($('sourceSpawnEvent').value);
  const armourPatch = armourPatchFrom('source', combat);
  const itemNumber = queueItemNumberFor('clone_character');
  const createSlug = slugify(`${base?.key || $('createName').value.trim() || 'new'}_${itemNumber}`);
  const landUnitClone = unitStatCloneFrom('source', unit, createSlug, itemNumber);
  const payload = {
    newName: $('createName').value.trim(),
    sourceKeys: {
      base: base?.key,
      imageSet: imageSet?.key,
      modelSet: modelSet?.key,
      skill: skill?.key,
      title: titleChoiceValue(titleSource),
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
      minRound: Number($('createMinRound').value),
      maxRound: Number($('createMaxRound').value),
      event: $('sourceSpawnEvent').value,
    },
    skillTree: skillTreeSnapshot('source'),
  };
  commitQueueItem({
    kind: 'clone_character',
    type: '신규 생성',
    title: `${$('createName').value || '새 장수'} 생성`,
    description: `기본 ${base?.name || '-'} · 칭호 ${titleSource?.titleName || titleSource?.name || '-'} · 이미지 ${imageSet?.name || '-'} · 모델 ${modelSet?.name || '-'} · 능력치 ${attribute?.name || '-'} · 장비 유지(${equipmentBrief(combat)})${armourPatch ? ` · 방어값 ${armourPatch.previousValue}→${armourPatch.value}` : ''} · 병종 ${unit?.name || '-'}${unitPatchDescription(landUnitClone)} · 스킬 ${skill?.name || '-'} · 등장 ${spawn?.name || '-'} · 이벤트 ${spawnEvent.name}`,
    payload,
  });
}

function renderQueue() {
  $('queueCount').textContent = `${state.queue.length}개`;
  $('workQueue').innerHTML = state.queue.length
    ? state.queue.map((item, index) => `
      <article class="queue-item ${index === state.editingQueueIndex ? 'active' : ''}" data-load-queue="${index}" tabindex="0" role="button" aria-label="작업 불러오기">
        <div class="queue-item-head">
          <b>${index + 1}. ${escapeHtml(item.type)}</b>
          <button class="queue-delete-btn" type="button" data-remove-queue="${index}" aria-label="작업 삭제">삭제</button>
        </div>
        <strong>${escapeHtml(item.title)}</strong>
        <span>${escapeHtml(item.description)}</span>
      </article>
    `).join('')
    : '<p class="empty">아직 추가된 작업이 없습니다.</p>';
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
  refreshStageButtons();
  renderValidation();
}

function loadPatchQueueItem(item) {
  const payload = item.payload;
  if (payload.targetKey) {
    state.selectedKey = payload.targetKey;
    renderRoster();
    renderSelected();
  }
  setMode('edit');
  $('editName').value = payload.displayName || $('editName').value;
  setSelectValue('editImageSet', payload.imageSetKey);
  setSelectValue('editModelSet', payload.modelSetKey);
  setSelectValue('editAttributeSet', payload.attributeSetSourceKey);
  setSelectValue('editCombatProfile', payload.combatProfileSourceKey);
  syncEquipmentSummary('edit', 'editCombatProfile');
  if (payload.armourPatch && $('editArmourValue')) $('editArmourValue').value = payload.armourPatch.value;
  setSelectValue('editUnitProfile', payload.unitProfileSourceKey);
  syncUnitSummary('edit', 'editUnitProfile');
  applyLandUnitCloneToInputs('edit', payload.landUnitClone);
  setSelectValue('editSubtype', payload.subtype);
  $('editWeight').value = payload.spawn?.weight ?? $('editWeight').value;
  $('editMinRound').value = payload.spawn?.minRound ?? $('editMinRound').value;
  $('editMaxRound').value = payload.spawn?.maxRound ?? $('editMaxRound').value;
  setSelectValue('editSpawnEvent', payload.spawn?.event);
  setSelectValue('editHistoricalSkill', payload.skillSources?.historical);
  setSelectValue('editRomanceSkill', payload.skillSources?.romance);
  restoreSkillTreeDraft('edit', payload.skillTree);
  updateImagePreviews();
  updateAllSpawnFieldLabels();
  renderSkillTreeEditors();
}

function loadCloneQueueItem(item) {
  const payload = item.payload;
  setMode('create');
  $('createName').value = payload.newName || $('createName').value;
  setSelectValue('sourceBase', payload.sourceKeys?.base);
  setSelectValue('sourceImageSet', payload.sourceKeys?.imageSet);
  setSelectValue('sourceModelSet', payload.sourceKeys?.modelSet);
  setSelectValue('sourceSkill', payload.sourceKeys?.skill);
  setSelectValue('sourceTitle', payload.sourceKeys?.title);
  renderTitleSummary('source', resolveTitleChoice($('sourceTitle').value));
  setSelectValue('sourceAttributeSet', payload.sourceKeys?.attributeSet);
  setSelectValue('sourceCombatProfile', payload.sourceKeys?.combatProfile);
  syncEquipmentSummary('source', 'sourceCombatProfile');
  if (payload.armourPatch && $('sourceArmourValue')) $('sourceArmourValue').value = payload.armourPatch.value;
  setSelectValue('sourceUnitProfile', payload.sourceKeys?.unitProfile);
  syncUnitSummary('source', 'sourceUnitProfile');
  applyLandUnitCloneToInputs('source', payload.landUnitClone);
  setSelectValue('sourceSpawn', payload.sourceKeys?.spawn);
  setSelectValue('createSubtype', payload.subtype);
  $('createWeight').value = payload.spawn?.weight ?? $('createWeight').value;
  $('createMinRound').value = payload.spawn?.minRound ?? $('createMinRound').value;
  $('createMaxRound').value = payload.spawn?.maxRound ?? $('createMaxRound').value;
  setSelectValue('sourceSpawnEvent', payload.spawn?.event);
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
    charge_bonus: 'ChargeBonus',
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

function skillTreesData() {
  return state.options?.skillTrees || {};
}

function skillIndexList() {
  return Object.values(skillTreesData().skillIndex || {});
}

function skillTreeBySet(setKey) {
  return (skillTreesData().romance || []).find((tree) => tree.key === setKey) || null;
}

function selectedSkillCharacter(prefix) {
  const selectId = prefix === 'edit' ? 'editRomanceSkill' : 'sourceSkill';
  return characters().find((item) => item.key === $(selectId)?.value) || selectedCharacter();
}

function selectedSkillSetKey(prefix) {
  return selectedSkillCharacter(prefix)?.romanceSkill || '';
}

function skillDraftKey(prefix, setKey = selectedSkillSetKey(prefix)) {
  return `${prefix}:${setKey || 'none'}`;
}

function skillTreeDraft(prefix, setKey = selectedSkillSetKey(prefix)) {
  const key = skillDraftKey(prefix, setKey);
  if (!state.skillTreeDrafts[key]) {
    state.skillTreeDrafts[key] = { sourceSetKey: setKey, replacements: {} };
  }
  return state.skillTreeDrafts[key];
}

function skillTreeSnapshot(prefix) {
  const setKey = selectedSkillSetKey(prefix);
  const draft = skillTreeDraft(prefix, setKey);
  return {
    sourceSetKey: setKey,
    replacements: { ...draft.replacements },
  };
}

function skillInfo(skillKey) {
  return skillTreesData().skillIndex?.[skillKey] || {
    key: skillKey,
    name: friendlyKey(skillKey),
    description: '',
    effectSummary: '',
    element: '',
  };
}

function skillNodeLabel(node, draft) {
  const replacement = draft?.replacements?.[node.key];
  const info = skillInfo(replacement || node.skillKey);
  return replacement ? `${info.name} *` : info.name;
}

function renderSkillTreeEditors() {
  renderSkillTreeEditor('edit');
  renderSkillTreeEditor('source');
}

function renderSkillTreeEditor(prefix) {
  const container = $(`${prefix}SkillTreeEditor`);
  if (!container) return;
  const setKey = selectedSkillSetKey(prefix);
  const tree = skillTreeBySet(setKey);
  if (!tree) {
    container.innerHTML = '<p class="skill-tree-empty">낭만 스킬트리 데이터를 찾지 못했습니다. 참조 pack을 다시 읽어주세요.</p>';
    return;
  }
  const draft = skillTreeDraft(prefix, setKey);
  const activeNodeKey = state.activeSkillNode?.prefix === prefix ? state.activeSkillNode.nodeKey : '';
  const xs = [...new Set(tree.nodes.map((node) => Number(node.position?.x ?? 0)))].sort((a, b) => a - b);
  const ys = [...new Set(tree.nodes.map((node) => Number(node.position?.y ?? 0)))].sort((a, b) => a - b);
  const gridStyle = `--skill-cols:${Math.max(xs.length, 1)};--skill-rows:${Math.max(ys.length, 1)}`;
  const activeNode = tree.nodes.find((node) => node.key === activeNodeKey) || tree.nodes[0];
  const activeInfo = activeNode ? skillInfo(draft.replacements[activeNode.key] || activeNode.skillKey) : null;
  container.innerHTML = `
    <div class="skill-tree-head">
      <div>
        <strong>낭만 스킬트리</strong>
        <span>${escapeHtml(tree.name)} · ${tree.nodes.length}개 노드</span>
      </div>
      <button type="button" class="ghost-btn mini" data-skill-reset="${prefix}">초기화</button>
    </div>
    <div class="skill-tree-board" style="${gridStyle}">
      ${tree.nodes.map((node) => {
        const x = xs.indexOf(Number(node.position?.x ?? 0)) + 1;
        const y = ys.indexOf(Number(node.position?.y ?? 0)) + 1;
        const info = skillInfo(draft.replacements[node.key] || node.skillKey);
        const element = info.element || 'none';
        return `
          <button
            type="button"
            class="skill-node element-${element} ${node.key === activeNodeKey ? 'active' : ''} ${draft.replacements[node.key] ? 'changed' : ''}"
            data-skill-node="${escapeHtml(node.key)}"
            data-skill-prefix="${prefix}"
            style="grid-column:${x};grid-row:${y}"
            title="${escapeHtml(`${info.name}\n${info.description || info.effectSummary || '효과 정보 미확인'}`)}"
          >
            <b>${escapeHtml(skillNodeLabel(node, draft))}</b>
            <small>${escapeHtml(info.effectSummary || info.description || '효과 정보 미확인')}</small>
          </button>
        `;
      }).join('')}
    </div>
    <div class="skill-picker">
      <div class="skill-picker-title">
        <strong>${escapeHtml(activeInfo?.name || '노드 선택')}</strong>
        <span>${escapeHtml(activeInfo?.description || activeInfo?.effectSummary || '교체할 노드를 클릭하세요.')}</span>
      </div>
      <input class="skill-search" data-skill-search="${prefix}" placeholder="스킬 이름/효과 검색">
      <div class="skill-candidates" data-skill-candidates="${prefix}">
        ${renderSkillCandidates(prefix, '')}
      </div>
    </div>
  `;
}

function renderSkillCandidates(prefix, query) {
  const setKey = selectedSkillSetKey(prefix);
  const tree = skillTreeBySet(setKey);
  const activeNodeKey = state.activeSkillNode?.prefix === prefix ? state.activeSkillNode.nodeKey : tree?.nodes?.[0]?.key;
  const q = String(query || '').trim().toLowerCase();
  const candidates = skillIndexList()
    .filter((item) => {
      const haystack = `${item.name} ${item.description} ${item.effectSummary} ${item.key}`.toLowerCase();
      return !q || haystack.includes(q);
    })
    .slice(0, 80);
  if (!activeNodeKey) return '<p class="skill-tree-empty">교체할 노드를 먼저 선택하세요.</p>';
  return candidates.map((item) => `
    <button
      type="button"
      class="skill-candidate element-${item.element || 'none'}"
      data-skill-candidate="${escapeHtml(item.key)}"
      data-skill-prefix="${prefix}"
      data-skill-target="${escapeHtml(activeNodeKey)}"
      title="${escapeHtml(item.description || item.effectSummary || item.key)}"
    >
      <b>${escapeHtml(item.name)}</b>
      <span>${escapeHtml(item.description || item.effectSummary || '효과 정보 미확인')}</span>
    </button>
  `).join('') || '<p class="skill-tree-empty">검색 결과가 없습니다.</p>';
}

function skillEffectText(info) {
  return info?.effectSummary || info?.description || '효과 정보 없음';
}

function skillTreeOwnerName(prefix) {
  const character = selectedCharacter();
  return character?.name || '선택 장수';
}

function renderSkillTreeEditor(prefix) {
  const container = $(`${prefix}SkillTreeEditor`);
  if (!container) return;
  const setKey = selectedSkillSetKey(prefix);
  const tree = skillTreeBySet(setKey);
  if (!tree) {
    container.innerHTML = '<p class="skill-tree-empty">낭만 스킬트리 데이터를 찾지 못했습니다. 참조 pack을 다시 읽어주세요.</p>';
    return;
  }
  const draft = skillTreeDraft(prefix, setKey);
  const activeNodeKey = state.activeSkillNode?.prefix === prefix ? state.activeSkillNode.nodeKey : '';
  const xs = [...new Set(tree.nodes.map((node) => Number(node.position?.x ?? 0)))].sort((a, b) => a - b);
  const ys = [...new Set(tree.nodes.map((node) => Number(node.position?.y ?? 0)))].sort((a, b) => a - b);
  const gridStyle = `--skill-cols:${Math.max(xs.length, 1)};--skill-rows:${Math.max(ys.length, 1)}`;
  const activeNode = tree.nodes.find((node) => node.key === activeNodeKey) || tree.nodes[0];
  const activeInfo = activeNode ? skillInfo(draft.replacements[activeNode.key] || activeNode.skillKey) : null;
  container.innerHTML = `
    <div class="skill-tree-head">
      <div>
        <strong>${escapeHtml(skillTreeOwnerName(prefix))} 낭만 스킬트리</strong>
        <span>${tree.nodes.length}개 노드 · 바꿀 노드를 클릭한 뒤 아래 후보를 선택하세요.</span>
      </div>
      <button type="button" class="ghost-btn mini" data-skill-reset="${prefix}">초기화</button>
    </div>
    <div class="skill-tree-board" style="${gridStyle}">
      ${tree.nodes.map((node) => {
        const x = xs.indexOf(Number(node.position?.x ?? 0)) + 1;
        const y = ys.indexOf(Number(node.position?.y ?? 0)) + 1;
        const replaced = draft.replacements[node.key];
        const info = skillInfo(replaced || node.skillKey);
        const element = info.element || 'none';
        return `
          <button
            type="button"
            class="skill-node element-${element} ${node.key === activeNode?.key ? 'active' : ''} ${replaced ? 'changed' : ''}"
            data-skill-node="${escapeHtml(node.key)}"
            data-skill-prefix="${prefix}"
            style="grid-column:${x};grid-row:${y}"
            title="${escapeHtml(`${info.name}\n${skillEffectText(info)}`)}"
          >
            <b>${escapeHtml(info.name)}${replaced ? ' *' : ''}</b>
            <small>${escapeHtml(skillEffectText(info))}</small>
          </button>
        `;
      }).join('')}
    </div>
    <div class="skill-picker">
      <div class="skill-picker-title">
        <strong>교체할 노드: ${escapeHtml(activeInfo?.name || '노드 선택')}</strong>
        <span>${escapeHtml(skillEffectText(activeInfo))}</span>
      </div>
      <input class="skill-search" data-skill-search="${prefix}" placeholder="스킬 이름이나 효과 검색">
      <div class="skill-candidates" data-skill-candidates="${prefix}">
        ${renderSkillCandidates(prefix, '')}
      </div>
    </div>
  `;
}

function renderSkillCandidates(prefix, query) {
  const setKey = selectedSkillSetKey(prefix);
  const tree = skillTreeBySet(setKey);
  const activeNodeKey = state.activeSkillNode?.prefix === prefix ? state.activeSkillNode.nodeKey : tree?.nodes?.[0]?.key;
  if (!activeNodeKey) return '<p class="skill-tree-empty">교체할 노드를 먼저 선택하세요.</p>';
  const activeNode = tree?.nodes?.find((node) => node.key === activeNodeKey);
  const activeInfo = activeNode ? skillInfo(activeNode.skillKey) : null;
  const q = String(query || '').trim().toLowerCase();
  const candidates = skillIndexList()
    .filter((item) => {
      const haystack = `${item.name} ${item.description} ${item.effectSummary} ${item.key}`.toLowerCase();
      return !q || haystack.includes(q);
    })
    .sort((a, b) => {
      const aSame = a.element && a.element === activeInfo?.element ? 1 : 0;
      const bSame = b.element && b.element === activeInfo?.element ? 1 : 0;
      if (aSame !== bSame) return bSame - aSame;
      return String(a.name || '').localeCompare(String(b.name || ''), 'ko');
    })
    .slice(0, 80);
  return candidates.map((item) => `
    <button
      type="button"
      class="skill-candidate element-${item.element || 'none'}"
      data-skill-candidate="${escapeHtml(item.key)}"
      data-skill-prefix="${prefix}"
      data-skill-target="${escapeHtml(activeNodeKey)}"
      title="${escapeHtml(`${item.name}\n${skillEffectText(item)}`)}"
    >
      <b>${escapeHtml(item.name)}</b>
      <span>${escapeHtml(skillEffectText(item))}</span>
    </button>
  `).join('') || '<p class="skill-tree-empty">검색 결과가 없습니다.</p>';
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
      skill_set_override: mode === 'romance' ? (skillDetails[mode]?.skillSet || skill?.romanceSkill) : undefined,
    });
  }
  return overrides;
}

function skillSetCloneFromPayload(recipe, snapshot, ownerKey, index) {
  const replacements = Object.entries(snapshot?.replacements || {})
    .filter(([, skillKey]) => skillKey);
  if (!snapshot?.sourceSetKey || !replacements.length) return '';
  const newSetKey = `hby_skillset_romance_${slugify(ownerKey)}_${index}`;
  recipe.skillSetClones.push({
    sourceSetKey: snapshot.sourceSetKey,
    newSetKey,
    replacements: replacements.map(([nodeKey, skillKey]) => ({ nodeKey, skillKey })),
  });
  return newSetKey;
}

function recipeFromQueue() {
  const recipe = {
    modName: 'mtu_custom_character_workflow',
    characterPatches: [],
    characterCloneRecipes: [],
    equipmentStatPatches: [],
    landUnitClones: [],
    skillSetClones: [],
  };

  state.queue.forEach((item, index) => {
    if (item.kind === 'patch_character') {
      const payload = item.payload;
      const imageSet = appearanceByKey(payload.imageSetKey);
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
      const customRomanceSkillSet = skillSetCloneFromPayload(recipe, payload.skillTree, payload.targetKey, index + 1);
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
          }),
          romance: compactObject({
            retinue: retinueOverride || detailsByMode(unit).romance?.retinue || unit?.unitProfile,
            attribute_set: detailsByMode(attribute).romance?.attributeSet || attribute?.attributeSet,
            skill_set_override: customRomanceSkillSet || detailsByMode(romance).romance?.skillSet || romance?.romanceSkill,
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
      const appearanceBase = characterByAppearanceKey(payload.sourceKeys?.imageSet);
      const base = appearanceBase || characters().find((candidate) => candidate.key === payload.sourceKeys?.base);
      const packBase = base?.source === 'reference'
        ? (packTemplateCharacters()[0] || base)
        : base;
      const baseTemplate = base?.templateRow || {};
      const baseDetails = detailsByMode(base);
      const imageSet = appearanceByKey(payload.sourceKeys?.imageSet);
      const attribute = characters().find((candidate) => candidate.key === payload.sourceKeys?.attributeSet);
      const skill = characters().find((candidate) => candidate.key === payload.sourceKeys?.skill);
      const titleSource = resolveTitleChoice(payload.sourceKeys?.title);
      const detailSource = skill?.source === 'reference' ? packBase : (skill || packBase);
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
      const titleInitialCeo = titleSource?.titleInitialCeoKey || titleSource?.details?.find((detail) => detail.initialCeos)?.initialCeos;
      const newInitialCeoKey = titleInitialCeo ? `hby_initial_ceo_${slug}_${index + 1}` : null;
      const detailOverrides = detailOverrideFromSources(attribute, skill, unit, retinueOverride);
      const customRomanceSkillSet = skillSetCloneFromPayload(recipe, payload.skillTree, payload.newName || slug, index + 1);
      if (customRomanceSkillSet) {
        detailOverrides.romance = compactObject({
          ...detailOverrides.romance,
          skill_set_override: customRomanceSkillSet,
        });
      }
      for (const mode of ['historical', 'romance']) {
        detailOverrides[mode] = compactObject({
          ...detailOverrides[mode],
          initial_ceos: newInitialCeoKey || baseDetails[mode]?.initialCeos,
        });
      }
      recipe.characterCloneRecipes.push({
        newTemplateKey: `hby_template_${slug}_${index + 1}`,
        sourceTemplateKey: packBase?.key,
        detailSourceTemplateKey: detailSource?.key,
        newArtSetId: null,
        artSetSourceId: null,
        newAgeRangeKey: spawn?.source === 'reference' ? null : `hby_age_${slug}_${index + 1}`,
        ageRangeSourceKey: spawn?.source === 'reference' ? null : (spawn?.spawnAge || packBase?.spawnAge),
        newInitialCeoKey,
        initialCeoSourceKey: titleInitialCeo || null,
        spawnEvent: payload.spawn?.event,
        displayName: payload.newName,
        imageAssets: imageAssetsFromAppearance(imageSet),
        templateOverrides: compactObject({
          forename: baseTemplate.forename,
          family_name: baseTemplate.family_name,
          clan_name: baseTemplate.clan_name,
          other_name: baseTemplate.other_name,
          is_male: baseTemplate.is_male,
          voiceover_actor: baseTemplate.voiceover_actor,
          can_be_born: baseTemplate.can_be_born,
          ai_skill_generation: baseTemplate.ai_skill_generation,
          min_rounds_to_stay_in_a_pool: baseTemplate.min_rounds_to_stay_in_a_pool,
          max_rounds_to_stay_in_a_pool: baseTemplate.max_rounds_to_stay_in_a_pool,
          max_rounds_in_all_pools_before_destroyed: baseTemplate.max_rounds_in_all_pools_before_destroyed,
          spawn_age_range: spawn?.spawnAge || base?.spawnAge || baseTemplate.spawn_age_range,
          weight: payload.spawn?.weight,
          min_spawn_round: payload.spawn?.minRound ?? spawn?.minRound,
          max_spawn_round: payload.spawn?.maxRound ?? spawn?.maxRound,
          subtype: payload.subtype,
          art_set_override: imageSet?.artSet || packBase?.artSet,
        }),
        detailOverrides,
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
  const minRound = Number((isCreate ? $('createMinRound') : $('editMinRound')).value);
  const maxRound = Number((isCreate ? $('createMaxRound') : $('editMaxRound')).value);
  const eventKey = isCreate ? $('sourceSpawnEvent').value : $('editSpawnEvent').value;
  const armourInput = isCreate ? $('sourceArmourValue') : $('editArmourValue');
  const armourValue = armourInput ? nullableNumber(armourInput.value) : null;
  const combatKey = isCreate ? $('sourceCombatProfile')?.value : $('editCombatProfile')?.value;
  const combatCharacter = characters().find((item) => item.key === combatKey);
  const canPatchArmour = Boolean(
    combatCharacter
    && combatCharacter.source !== 'reference'
    && !combatCharacter.armourFromReference
    && combatCharacter.armourCeo
    && combatCharacter.armourStatKey
  );
  const unitPrefix = isCreate ? 'source' : 'edit';
  const unitKey = isCreate ? $('sourceUnitProfile')?.value : $('editUnitProfile')?.value;
  const unitCharacter = characters().find((item) => item.key === unitKey);
  const canCloneUnit = Boolean(unitCharacter?.landUnitKey && !unitCharacter?.unitFromReference);
  const unitInputs = ['ChargeBonus', 'Morale', 'PrimaryAmmo']
    .map((suffix) => $(`${unitPrefix}${suffix}`))
    .filter(Boolean);

  if (!name) {
    items.push(validationItem('error', '이름 필요', '저장 전에 표시 이름을 입력해야 합니다.'));
  }
  if (isCreate && characters().some((character) => character.name === name)) {
    items.push(validationItem('warning', '이름 중복 가능성', '기존 장수와 같은 표시 이름입니다. loc 충돌 검증이 필요합니다.'));
  }
  if (armourInput && canPatchArmour && (armourValue === null || armourValue < 0)) {
    items.push(validationItem('error', '방어값 확인', '방어값은 0 이상의 숫자여야 합니다.'));
  }
  if (canCloneUnit && unitInputs.some((input) => nullableNumber(input.value) === null || nullableNumber(input.value) < 0)) {
    items.push(validationItem('error', '유닛 수치 확인', '돌격 보너스, 사기, 탄약은 0 이상의 숫자여야 합니다.'));
  }
  if (minRound > maxRound) {
    items.push(validationItem('error', '등장 라운드 확인', '최소 라운드가 최대 라운드보다 클 수 없습니다.'));
  }
  if (eventKey === 'delayed_join' && (!Number.isFinite(minRound) || minRound < 1)) {
    items.push(validationItem('error', '합류 턴 확인', '몇 턴 뒤 합류는 플레이어 합류 턴을 1 이상으로 입력해야 합니다.'));
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

const OFFICIAL_GAME_PACK_NAMES = new Set([
  'database.pack',
  'data_mh.pack',
  'data_ep.pack',
  'data_dlc07.pack',
  'data_dlc06.pack',
  'data_bl.pack',
  'data.pack',
]);

function basenameFromPath(path) {
  return String(path || '').replaceAll('\\', '/').split('/').pop().toLowerCase();
}

function mergeReferencePackPaths(existingPaths, officialPaths) {
  const customPaths = existingPaths.filter((path) => !OFFICIAL_GAME_PACK_NAMES.has(basenameFromPath(path)));
  const seen = new Set();
  return [...customPaths, ...officialPaths].filter((path) => {
    const key = String(path || '').toLowerCase();
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

async function applyGamePath() {
  const input = $('gameDataPath');
  const gamePath = input.value.trim();
  if (!gamePath) {
    state.serverMessages = [validationItem('warning', '게임 경로 필요', '삼탈워 설치 폴더 또는 data 폴더 경로를 입력하세요.')];
    renderValidation();
    return;
  }
  state.serverMessages = [validationItem('info', '게임 경로 확인 중', gamePath)];
  renderValidation();
  try {
    const data = await postJson('/api/game-path/resolve', { gamePath });
    const merged = mergeReferencePackPaths(referencePackPaths(), data.referencePackPaths || []);
    $('referencePackPaths').value = merged.join('\n');
    localStorage.setItem('mtuEditor.gameDataPath', data.dataDir || gamePath);
    input.value = data.dataDir || gamePath;
    const missingText = data.missing?.length ? ` · 누락: ${data.missing.join(', ')}` : '';
    state.serverMessages = [validationItem('ok', '게임 경로 적용 완료', `${data.message}${missingText}`)];
  } catch (error) {
    state.serverMessages = [validationItem('error', '게임 경로 적용 실패', error.message)];
  }
  renderValidation();
}

async function suggestGamePath() {
  const input = $('gameDataPath');
  const saved = localStorage.getItem('mtuEditor.gameDataPath');
  if (saved) {
    input.value = saved;
    return;
  }
  try {
    const response = await fetch('/api/game-path/suggest');
    const data = await response.json();
    if (data.bestPath && !input.value.trim()) {
      input.value = data.bestPath;
    }
  } catch {
    // Best-effort convenience only. Manual entry still works.
  }
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
  if (state.loadingPack) return;
  state.loadingPack = true;
  state.serverMessages = [validationItem('info', '팩 읽는 중', $('inputPackPath').value)];
  renderValidation();
  try {
    const data = await postJson('/api/open', {
      adapter: 'auto',
      inputPath: $('inputPackPath').value,
      referencePackPaths: referencePackPaths(),
      includeVanilla: false,
    });
    hydrateFromPackData(data.characters);
    const cacheText = data.cache?.hit ? 'DB 캐시 사용' : 'DB 캐시 갱신';
    const referenceOk = (data.characters?.referencePacks || []).filter((item) => item.ok).length;
    const referenceTotal = (data.characters?.referencePacks || []).length;
    const referenceText = referenceTotal ? ` · 참조 pack ${referenceOk}/${referenceTotal}` : '';
    const timings = data.timings || {};
    const detailTimings = data.characters?.timings || {};
    const timingText = timings.total
      ? ` · ${timings.total}s(open ${timings.openSession || 0}s / read ${timings.readCharacterData || 0}s / merge ${detailTimings.mergeReferences || 0}s / summarize ${detailTimings.summarizePack || 0}s)`
      : '';
    state.serverMessages = [validationItem('info', '팩 읽기 완료', `${state.characters.length}명 로드 · ${cacheText}${referenceText}${timingText}`)];
    renderAll();
  } catch (error) {
    state.serverMessages = [validationItem('error', '팩 읽기 실패', error.message)];
    renderValidation();
  } finally {
    state.loadingPack = false;
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
  refreshStageButtons();
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
$('sourceBase').addEventListener('change', renderValidation);
$('editRomanceSkill').addEventListener('change', () => {
  state.activeSkillNode = null;
  renderSkillTreeEditors();
  renderValidation();
});
$('sourceSkill').addEventListener('change', () => {
  state.activeSkillNode = null;
  renderSkillTreeEditors();
  renderValidation();
});
$('sourceTitle').addEventListener('change', () => {
  renderTitleSummary('source', resolveTitleChoice($('sourceTitle').value));
  renderValidation();
});
$('editImageSet').addEventListener('change', updateImagePreviews);
$('sourceImageSet').addEventListener('change', updateImagePreviews);
$('editSpawnEvent').addEventListener('change', () => {
  updateSpawnFieldLabels('edit');
  renderValidation();
});
$('sourceSpawnEvent').addEventListener('change', () => {
  updateSpawnFieldLabels('create');
  renderValidation();
});
$('stageEditButton').addEventListener('click', stageEdit);
$('stageCreateButton').addEventListener('click', stageCreate);
$('workQueue').addEventListener('click', (event) => {
  const deleteButton = event.target.closest('[data-remove-queue]');
  if (deleteButton) {
    removeQueueItem(Number(deleteButton.dataset.removeQueue));
    return;
  }
  const item = event.target.closest('[data-load-queue]');
  if (item) loadQueueItem(Number(item.dataset.loadQueue));
});
$('workQueue').addEventListener('keydown', (event) => {
  if (!['Enter', ' '].includes(event.key)) return;
  const item = event.target.closest('[data-load-queue]');
  if (!item) return;
  event.preventDefault();
  loadQueueItem(Number(item.dataset.loadQueue));
});
document.addEventListener('click', (event) => {
  const reset = event.target.closest('[data-skill-reset]');
  if (reset) {
    const prefix = reset.dataset.skillReset;
    const draft = skillTreeDraft(prefix);
    draft.replacements = {};
    state.activeSkillNode = null;
    renderSkillTreeEditor(prefix);
    renderValidation();
    return;
  }
  const node = event.target.closest('[data-skill-node]');
  if (node) {
    state.activeSkillNode = {
      prefix: node.dataset.skillPrefix,
      nodeKey: node.dataset.skillNode,
    };
    renderSkillTreeEditor(node.dataset.skillPrefix);
    return;
  }
  const candidate = event.target.closest('[data-skill-candidate]');
  if (candidate) {
    const prefix = candidate.dataset.skillPrefix;
    const target = candidate.dataset.skillTarget;
    const draft = skillTreeDraft(prefix);
    draft.replacements[target] = candidate.dataset.skillCandidate;
    renderSkillTreeEditor(prefix);
    renderValidation();
  }
});
document.addEventListener('input', (event) => {
  const search = event.target.closest('[data-skill-search]');
  if (!search) return;
  const prefix = search.dataset.skillSearch;
  const target = document.querySelector(`[data-skill-candidates="${prefix}"]`);
  if (target) target.innerHTML = renderSkillCandidates(prefix, search.value);
});
$('loadPackButton').addEventListener('click', loadPack);
$('applyGamePathButton').addEventListener('click', applyGamePath);
$('gameDataPath').addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    applyGamePath();
  }
});
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

suggestGamePath();
renderAll();
