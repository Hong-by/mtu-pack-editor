'use strict';

// Text-based discovery only: retain the original description, including penalties
// and conditions. Missing scope/activation data must never imply self or passive.
const EFFECT_FACETS = {
  role: [
    ['leader', '세력 지도자일 때', /세력 지도자일 경우|세력 지도자일 때/],
    ['commanding', '통솔 장수일 때', /통솔할 때|통솔 장수일|군대를 통솔/],
    ['governor', '태수일 때', /태수가 있는 군|태수일 경우|태수일 때/],
    ['position', '해당 지역에 위치할 때', /위치할 경우/],
  ],
  purpose: [
    ['attack', '공격', /피해|공격|돌격|관통|사격|탄약/],
    ['survival', '생존·방어', /방어(?!하는)|갑옷(?!\s*관통)|장갑(?!\s*관통)|회피|저항|피해 감소|생명|체력(?!\s*비용)/],
    ['movement', '이동', /이동|속도|행군|기동/],
    ['healing', '회복', /회복|치유|재생|충원/],
    ['morale', '사기', /사기|불굴|공포|규율/],
    ['economy', '내정', /수입|수익|공공질서|공공 질서|건설|식량|만족도|부패|상업|농업|산업|태수/],
    ['stats', '능력치', /본능|결의|전문성|권위|책략/],
  ],
  target: [
    ['self', '장수 본인', /해당 인물|해당 장수|자신|본인/],
    ['retinue', '소속 부대·수행원', /수행|휘하|소속 부대|해당 부대/],
    ['army', '소속 군대 전체', /해당 군대|소속 군대/],
    ['ally', '아군', /아군|동맹/],
    ['enemy', '적군', /적군|적 부대|적의|적 장수/],
    ['faction', '세력 전체', /세력 전체|세력 전역|세력 전반/],
    ['province', '현지 군·지역', /태수가 있는 군|현지 군|현지 지역/],
  ],
  activation: [
    ['active', '사용 능력', /재사용|재충전|사용 횟수|사용횟수|활성화 능력|발동 능력|발동 시/],
    ['conditional', '조건부', /일 때|할 때|일 경우|동안|상태에서|통솔 장수|태수일|승상일/],
    ['passive', '상시 명시', /상시|지속 능력|지속 효과/],
  ],
};

function discoveryText(value) {
  return String(value || '').normalize('NFKC').toLocaleLowerCase().replace(/\s+/g, ' ').trim();
}

function discoveryMatches(text, query) {
  const haystack = discoveryText(text).replace(/\s/g, '');
  const aliases = {
    본인: ['해당인물', '해당장수', '자신'],
    자신: ['해당인물', '해당장수', '본인'],
    생존: ['방어', '회피', '저항', '생명력', '피해감소'],
    회복: ['치유', '재생', '충원'],
    내정: ['수입', '수익', '공공질서', '건설', '식량', '만족도', '부패'],
    이동: ['행군', '기동'],
  };
  return discoveryText(query).split(/\s+/).filter(Boolean)
    .every((word) => [word, ...(aliases[word] || [])].some((term) => haystack.includes(term)));
}

function effectTags(text, group) {
  let description = String(text || '');
  // '(해당 인물)' after an ability describes who receives it, not its battle target.
  if (group === 'target' && /능력:/.test(description)) {
    description = description.replace(/\([^)]*\)\s*$/, '');
  } else if (group === 'target' || group === 'role') {
    // "수행원 유지비 (세력 전체)" is faction-wide, not retinue-scoped.
    const scopes = [...description.matchAll(/\(([^()]*)\)/g)];
    if (scopes.length) description = scopes[scopes.length - 1][1];
  }
  return EFFECT_FACETS[group].filter(([, , pattern]) => pattern.test(description)).map(([key]) => key);
}

function selectedEffectValues(value) {
  return [...new Set((Array.isArray(value) ? value : value ? [value] : []).filter(Boolean))];
}

function effectMatches(text, filters = {}) {
  const groups = Object.keys(EFFECT_FACETS).filter((group) => selectedEffectValues(filters[group]).length);
  if (!groups.length) return true;
  const clauses = String(text || '').split(/(?<=\))\s*·\s*/);
  return clauses.some((clause) => groups.some((group) => {
    const selected = selectedEffectValues(filters[group]);
    return selected.some((value) => value === 'unknown'
      ? (group === 'role' ? !effectTags(clause, group).length : !clauses.some((part) => effectTags(part, group).length))
      : effectTags(clause, group).includes(value));
  }));
}

function effectFilterLabel(group, key) {
  return EFFECT_FACETS[group].find(([value]) => value === key)?.[1]
    || (group === 'role' ? '직위 조건 표기 없음' : '미분류·설명 확인');
}

function effectFilterSummary(group, value) {
  const selected = selectedEffectValues(value);
  return selected.length ? selected.map((key) => effectFilterLabel(group, key)).join(' 또는 ') : '전체';
}

function updateEffectCheckbox(control, filters) {
  const group = control.dataset.effectGroup;
  const selected = new Set(selectedEffectValues(filters[group]));
  if (control.value === '') selected.clear();
  else if (control.checked) selected.add(control.value);
  else selected.delete(control.value);
  filters[group] = [...selected];
  const dropdown = control.closest('[data-effect-dropdown]');
  dropdown.querySelectorAll('[data-effect-group]').forEach((input) => { input.checked = input.value ? selected.has(input.value) : !selected.size; });
  dropdown.querySelector('[data-effect-summary]').textContent = effectFilterSummary(group, [...selected]);
}

function discoveryOptionLabel(select, item) {
  if (/Title$/.test(select.id)) return String(item.label || '').split(' - ')[0];
  return item.label;
}

function dedupePickerOptions(select, items, selectedValue = select.value) {
  const groups = new Map();
  for (const item of items) {
    let identity = String(item.value);
    if (/Title$/.test(select.id)) {
      const title = resolveTitleChoice(item.value);
      if (title?.titleCeoKey) identity = JSON.stringify([title.titleCeoKey, title.titleEffectSummary || '']);
    } else if (/AttributeSet$/.test(select.id)) {
      identity = attributeChoiceValueFor(item.value);
    } else if (/ImageSet$/.test(select.id)) {
      const appearance = appearanceByKey(item.value);
      if (appearance) identity = imageChoiceIdentity(appearance);
    }
    if (!groups.has(identity) || String(item.value) === String(selectedValue)) groups.set(identity, item);
  }
  return [...groups.values()];
}

function effectDescriptionMarkup(text, filters = {}) {
  const filtering = Object.values(filters).some((value) => selectedEffectValues(value).length);
  return String(text || '').split(/(?<=\))\s*·\s*/)
    .map((clause, index) => ({clause, index, matches: filtering && effectMatches(clause, filters)}))
    .sort((a, b) => Number(b.matches) - Number(a.matches) || a.index - b.index)
    .map(({clause, matches}) => `<span class="effect-line${matches ? ' effect-match' : ''}">${escapeHtml(clause)}</span>`).join('');
}

function discoveryFiltersMarkup(filters = {}, kind = 'skill') {
  const groups = kind === 'title' ? ['role', 'target', 'purpose'] : ['purpose', 'target', 'activation'];
  return `<div class="effect-filters">${groups.map((group) => {
    const title = { role: '적용 직위·상황', purpose: '원하는 효과', target: '효과 적용 범위', activation: '발동 조건' }[group];
    const selected = selectedEffectValues(filters[group]);
    return `<div class="effect-filter-group"><span>${title}</span>
      <details data-effect-dropdown="${group}"><summary aria-label="${title} 선택"><span data-effect-summary>${escapeHtml(effectFilterSummary(group, selected))}</span></summary>
        <div class="effect-checkbox-menu" role="group" aria-label="${title}">
        ${[['', '전체 (선택 해제)'], ...EFFECT_FACETS[group], ['unknown', effectFilterLabel(group, 'unknown')]].map(([key, label]) => `<label><input type="checkbox" data-effect-group="${group}" value="${key}" ${key ? selected.includes(key) ? 'checked' : '' : !selected.length ? 'checked' : ''}><span>${label}</span></label>`).join('')}
        </div>
      </details></div>`;
  }).join('')}</div>
    <small class="discovery-hint">필터 구분 없이 선택한 조건 중 하나라도 포함되면 표시합니다 (OR).${kind === 'title' ? ' ‘조건 표기 없음’은 상시 효과를 뜻하지 않습니다.' : ''}</small>`;
}

function discoveryConditions(filters, query, extraLabel) {
  const labels = Object.keys(EFFECT_FACETS).filter((group) => selectedEffectValues(filters?.[group]).length)
    .map((group) => effectFilterSummary(group, filters[group]));
  if (extraLabel) labels.push(extraLabel);
  return [query ? `검색: ${query}` : '', labels.join(' 또는 ')].filter(Boolean).join(' · ') || '전체';
}

function selectEffectDescription(select, item) {
  if (/Title$/.test(select.id)) {
    const title = resolveTitleChoice(item.value);
    return title?.titleEffectSummary || title?.titleEffectTitle || '';
  }
  if (/(Trait|Equipment)Set$/.test(select.id)) {
    const kind = /TraitSet$/.test(select.id) ? 'trait' : 'equipment';
    const set = ceoSetByKey(kind, item.value);
    return (set?.items || []).map((entry) => [entry.label, entry.effectSummary || entry.description].filter(Boolean).join(': ')).filter(Boolean).join(' · ');
  }
  return '';
}

function discoveryChoiceMatches(select, item, filters, stat = 'all') {
  const hasEffects = Object.keys(EFFECT_FACETS).some((group) => selectedEffectValues(filters[group]).length);
  const hasStat = /Title$/.test(select.id) && stat !== 'all';
  return (!hasEffects && !hasStat)
    || (hasEffects && effectMatches(selectEffectDescription(select, item), filters))
    || (hasStat && titleChoiceMatchesStatFilter(resolveTitleChoice(item.value), stat));
}

function renderDiscoverySelect(select) {
  const panel = select._discoveryPanel;
  if (!panel || panel.hidden) return;
  const input = select.parentNode.querySelector(`[data-search-for="${select.id}"]`);
  const query = input?.value || '';
  const filters = select._effectFilters || {};
  const all = dedupePickerOptions(select, select._allOptions || []);
  const stat = /Title$/.test(select.id) ? titleFilterForPrefix(select.id.startsWith('source') ? 'source' : 'edit') : 'all';
  const matches = all.filter((item) => discoveryMatches(`${item.label} ${item.value} ${item.search || ''} ${selectEffectDescription(select, item)}`, query)
    && discoveryChoiceMatches(select, item, filters, stat));
  const current = all.find((item) => String(item.value) === select.value);
  const limit = select._discoveryLimit || 30;
  const statLabel = ({authority:'권위', instinct:'본능', cunning:'책략', expertise:'전문성', resolve:'결의'})[stat];
  panel.querySelector('.discovery-status').textContent = `${discoveryConditions(filters, query, statLabel)} · ${matches.length}개 결과`;
  panel.querySelector('.discovery-current').textContent = `현재 선택: ${(current ? discoveryOptionLabel(select, current) : '') || select.selectedOptions[0]?.textContent || '없음'} (검색 결과와 별도)`;
  panel.querySelector('.discovery-results').innerHTML = matches.slice(0, limit).map((item) => {
    const description = selectEffectDescription(select, item);
    return `<button type="button" class="discovery-result" data-discovery-value="${escapeHtml(item.value)}" aria-pressed="${String(item.value) === select.value}">
      <strong>${escapeHtml(discoveryOptionLabel(select, item))}</strong>${description ? `<span>${effectDescriptionMarkup(description, filters)}</span>` : ''}
    </button>`;
  }).join('') || '<p class="empty">일치하는 항목이 없습니다. 조건을 해제하거나 검색어를 줄여보세요.</p>';
  const more = panel.querySelector('[data-discovery-more]');
  more.hidden = matches.length <= limit;
  more.textContent = `더 보기 (${Math.min(limit, matches.length)}/${matches.length})`;
}

function attachDiscoverySelect(select, input) {
  const hasEffects = /Title$/.test(select.id);
  input.placeholder = hasEffects ? '이름·효과 검색 (예: 방어 본인)' : '이름 검색 · 여러 단어 입력 가능';
  input.setAttribute('aria-label', `${({Title:'칭호',TraitSet:'트레잇',EquipmentSet:'장비',AttributeSet:'능력치',Skill:'스킬셋',ImageSet:'이미지',Base:'기준 장수',CombatProfile:'장비 기준',UnitProfile:'부대 기준',Spawn:'등장'})[select.id.replace(/^(edit|source)/, '')] || '항목'} 검색`);
  const panel = document.createElement('div');
  panel.className = 'discovery-panel';
  panel.hidden = true;
  panel.innerHTML = `${hasEffects ? discoveryFiltersMarkup({}, 'title') : ''}
    <div class="discovery-actions"><button type="button" data-discovery-clear>조건 전체 해제</button><button type="button" data-discovery-close>목록 닫기</button></div>
    <small class="discovery-current"></small><p class="discovery-status" role="status"></p>
    <div class="discovery-results"></div><button type="button" data-discovery-more>더 보기</button>`;
  select.after(panel);
  select._discoveryPanel = panel;
  const open = () => {
    ensureSelectOptionsLoaded(select);
    panel.hidden = false;
    renderDiscoverySelect(select);
  };
  if (hasEffects) {
    const browse = document.createElement('button');
    browse.type = 'button';
    browse.className = 'effect-browse-button';
    browse.textContent = '효과로 칭호 찾기';
    input.before(browse);
    browse.addEventListener('click', open);
  }
  input.addEventListener('focus', open);
  input.addEventListener('input', () => { select._discoveryLimit = 30; open(); });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') panel.hidden = true;
  });
  select.addEventListener('change', () => renderDiscoverySelect(select));
  panel.addEventListener('change', (event) => {
    const group = event.target.dataset.effectGroup;
    if (!group) return;
    select._effectFilters ||= {};
    updateEffectCheckbox(event.target, select._effectFilters);
    select._discoveryLimit = 30;
    renderDiscoverySelect(select);
  });
  panel.addEventListener('click', (event) => {
    const choice = event.target.closest('[data-discovery-value]');
    if (choice) {
      setSelectValue(select.id, choice.dataset.discoveryValue);
      select.dispatchEvent(new Event('change', { bubbles: true }));
      renderDiscoverySelect(select);
    } else if (event.target.closest('[data-discovery-more]')) {
      select._discoveryLimit = (select._discoveryLimit || 30) + 30;
      renderDiscoverySelect(select);
    } else if (event.target.closest('[data-discovery-clear]')) {
      input.value = '';
      select._effectFilters = {};
      select._discoveryLimit = 30;
      panel.querySelectorAll('[data-effect-group]').forEach((control) => { control.checked = control.value === ''; });
      panel.querySelectorAll('[data-effect-summary]').forEach((label) => { label.textContent = '전체'; });
      if (/Title$/.test(select.id)) applyTitleFilter(select.id.startsWith('source') ? 'source' : 'edit', 'all');
      filterSelectOptions(select);
    } else if (event.target.closest('[data-discovery-close]')) {
      panel.hidden = true;
    }
  });
}

function skillDiscoveryState(prefix) {
  state.skillDiscovery ||= {};
  return state.skillDiscovery[prefix] ||= { query: '', filters: {}, limit: 40 };
}

function skillDiscoveryMarkup(prefix) {
  const discovery = skillDiscoveryState(prefix);
  return `<div data-skill-discovery="${prefix}">${discoveryFiltersMarkup(discovery.filters)}
    <button type="button" data-skill-clear="${prefix}">검색·필터 전체 해제</button></div>`;
}

document.addEventListener('change', (event) => {
  const group = event.target.dataset.effectGroup;
  const owner = event.target.closest('[data-skill-discovery]');
  if (!group || !owner) return;
  const prefix = owner.dataset.skillDiscovery;
  const discovery = skillDiscoveryState(prefix);
  updateEffectCheckbox(event.target, discovery.filters);
  discovery.limit = 40;
  document.querySelector(`[data-skill-candidates="${prefix}"]`).innerHTML = renderSkillCandidates(prefix, discovery.query);
});

document.addEventListener('click', (event) => {
  const clear = event.target.closest('[data-skill-clear]');
  const more = event.target.closest('[data-skill-more]');
  if (!clear && !more) return;
  const prefix = clear?.dataset.skillClear || more.dataset.skillMore;
  const discovery = skillDiscoveryState(prefix);
  if (clear) {
    discovery.query = '';
    discovery.filters = {};
    discovery.limit = 40;
    state.skillCandidateTabs[prefix] = 'all';
    renderSkillTreeEditor(prefix);
  } else {
    discovery.limit += 40;
    document.querySelector(`[data-skill-candidates="${prefix}"]`).innerHTML = renderSkillCandidates(prefix, discovery.query);
  }
});
