'use strict';

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
  return cachedDerived('skillIndexList:deduped', () => dedupeSkillInfos(
    Object.values(skillTreesData().skillIndex || {}).map((item) => enrichedSkillInfo(item)),
  ));
}

function normalizedSkillDedupeText(value) {
  return String(value || '')
    .replace(/\s+/g, '')
    .replace(/[·:;.,/()［］\[\]-]/g, '')
    .toLowerCase();
}

function skillInfoDedupeKey(info) {
  const name = normalizedSkillDedupeText(info?.name);
  const effect = normalizedSkillDedupeText(skillEffectText(info));
  const element = String(info?.element || '').trim();
  const source = normalizedSkillDedupeText(info?.source || skillSourceLabel(info));
  const owner = normalizedSkillDedupeText(info?.owner || '');
  if (!name && !effect) return String(info?.key || '');
  return `${element}|${source}|${owner}|${name}|${effect}`;
}

function skillInfoQuality(info) {
  let score = 0;
  if (info?.name && !String(info.name).includes('_')) score += 20;
  if (info?.effectSummary) score += 10;
  if (info?.manualEffect) score += 5;
  if (info?.element) score += 3;
  if (info?.source) score += 3;
  if (info?.owner) score += 2;
  if (info?.manualCatalog) score += 2;
  const key = String(info?.key || '');
  if (key.includes('3k_mtu')) score += 3;
  if (key.includes('3k_dlc')) score += 2;
  if (key.includes('3k_main')) score += 1;
  return score;
}

function dedupeSkillInfos(items) {
  const byKey = new Map();
  const order = [];
  for (const item of items || []) {
    const key = skillInfoDedupeKey(item);
    if (!key) continue;
    if (!byKey.has(key)) {
      byKey.set(key, item);
      order.push(key);
      continue;
    }
    const existing = byKey.get(key);
    if (skillInfoQuality(item) > skillInfoQuality(existing)) byKey.set(key, item);
  }
  return order.map((key) => byKey.get(key)).filter(Boolean);
}

function skillNodeDedupeKey(node) {
  return String(node?.key || '').trim();
}

function skillNodePositionKey(node) {
  const x = Number(node?.position?.x ?? 0);
  const y = Number(node?.position?.y ?? 0);
  return `${x}:${y}`;
}

function skillNodeModeRank(node) {
  const text = `${node?.key || ''} ${node?.skillKey || ''}`.toLowerCase();
  if (text.includes('romance')) return 3;
  if (text.includes('historical')) return 1;
  return 2;
}

function betterSkillNodeForPosition(candidate, existing) {
  return skillNodeModeRank(candidate) > skillNodeModeRank(existing);
}

function dedupeSkillTreeNodes(nodes) {
  const byNodeKey = new Map();
  const byPosition = new Map();
  const result = [];
  for (const node of nodes || []) {
    const nodeKey = skillNodeDedupeKey(node);
    const positionKey = skillNodePositionKey(node);
    if (nodeKey && byNodeKey.has(nodeKey)) continue;
    const existingAtPosition = byPosition.get(positionKey);
    if (existingAtPosition) {
      if (betterSkillNodeForPosition(node, existingAtPosition)) {
        const index = result.indexOf(existingAtPosition);
        if (index >= 0) result[index] = node;
        const existingKey = skillNodeDedupeKey(existingAtPosition);
        if (existingKey) byNodeKey.delete(existingKey);
        if (nodeKey) byNodeKey.set(nodeKey, node);
        byPosition.set(positionKey, node);
      }
      continue;
    }
    if (nodeKey) byNodeKey.set(nodeKey, node);
    byPosition.set(positionKey, node);
    result.push(node);
  }
  return result;
}

function skillTreeBySet(setKey) {
  return (skillTreesData().romance || []).find((tree) => tree.key === setKey) || null;
}

function hasSkillTree(setKey) {
  return Boolean(skillTreeBySet(setKey));
}

function selectedSkillCharacter(prefix) {
  const selectId = prefix === 'edit' ? 'editSkill' : 'sourceSkill';
  return characters().find((item) => item.key === $(selectId)?.value) || selectedCharacter();
}

function selectedSkillSetKey(prefix) {
  return skillSetKeyForEditor(selectedSkillCharacter(prefix));
}

function skillSetKeyForEditor(character) {
  if (!character) return '';
  const detailSets = (character.details || [])
    .filter((detail) => detail.gameMode === 'romance' || detail.gameMode === 'historical')
    .map((detail) => detail.skillSet)
    .filter(Boolean);
  const directCandidates = [
    character.romanceSkill,
    ...detailSets,
    character.historicalSkill,
  ];
  for (const key of directCandidates) {
    if (hasSkillTree(key)) return key;
  }
  const genericCandidates = genericSkillSetCandidates(character);
  return genericCandidates.find(hasSkillTree) || character.romanceSkill || character.historicalSkill || '';
}

function genericSkillSetCandidates(character) {
  const element = character?.element || '';
  const elementToken = element === 'water' ? 'water_strategist' : element;
  if (!elementToken) return [];
  return [
    `3k_main_skillset_generic_general_${elementToken}`,
    `3k_main_skillset_generic_minister_${elementToken}`,
    `3k_main_skillset_generic_governor_${elementToken}`,
    `3k_main_skillset_generic_envoy_${elementToken}`,
    `3k_main_skillset_generic_agent_${elementToken}`,
    `3k_main_skillset_generic_villager_${elementToken}`,
  ];
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
  return enrichedSkillInfo(skillKey);
}

function skillNodeLabel(node, draft) {
  const replacement = draft?.replacements?.[node.key];
  const info = skillInfo(replacement || node.skillKey);
  return replacement ? `${info.name} *` : info.name;
}

function skillSourceLabel(info) {
  const explicit = String(info?.source || '').trim();
  if (explicit) return explicit;
  const key = String(info?.key || '').toLowerCase();
  if (key.includes('3k_mtu')) return 'MTU';
  if (key.includes('3k_dlc') || key.includes('3k_ytr') || key.includes('_ep_') || key.startsWith('ep_')) return 'DLC';
  if (key.includes('3k_main')) return '바닐라';
  return '';
}

function skillMetaText(info) {
  const pieces = [];
  const source = skillSourceLabel(info);
  if (source) pieces.push(source);
  if (info?.owner) pieces.push(info.exclusive ? `${info.owner} 전용` : info.owner);
  if (info?.manualCatalog && !info?.owner) pieces.push('효과 카탈로그');
  return pieces.join(' · ');
}

function skillSourceBadgeMarkup(info) {
  const text = skillMetaText(info);
  return text ? `<em class="skill-source-badge">${escapeHtml(text)}</em>` : '';
}

function renderSkillTreeEditors() {
  renderSkillTreeEditor('edit');
  renderSkillTreeEditor('source');
}

function skillEffectText(info) {
  return info?.effectSummary || info?.description || '효과 정보 없음';
}

const SKILL_ELEMENT_TABS = [
  ['all', '전체'],
  ['fire', '火 화'],
  ['water', '水 수'],
  ['wood', '木 목'],
  ['metal', '金 금'],
  ['earth', '土 토'],
];

function activeSkillCandidateTab(prefix, activeInfo = null) {
  const saved = state.skillCandidateTabs[prefix];
  if (saved) return saved;
  return activeInfo?.element || 'all';
}

function skillCandidateTabsMarkup(prefix, activeTab) {
  return `
    <div class="skill-element-tabs" role="tablist" aria-label="교체 후보 오행">
      ${SKILL_ELEMENT_TABS.map(([key, label]) => `
        <button
          type="button"
          class="skill-element-tab ${key === activeTab ? 'active' : ''} ${key !== 'all' ? `element-${key}` : ''}"
          data-skill-element-tab="${key}"
          data-skill-prefix="${prefix}"
          role="tab"
          aria-selected="${key === activeTab ? 'true' : 'false'}"
        >${escapeHtml(label)}</button>
      `).join('')}
    </div>
  `;
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
  const nodes = dedupeSkillTreeNodes(tree.nodes);
  const draft = skillTreeDraft(prefix, setKey);
  const activeNodeKey = state.activeSkillNode?.prefix === prefix ? state.activeSkillNode.nodeKey : '';
  const xs = [...new Set(nodes.map((node) => Number(node.position?.x ?? 0)))].sort((a, b) => a - b);
  const ys = [...new Set(nodes.map((node) => Number(node.position?.y ?? 0)))].sort((a, b) => a - b);
  const gridStyle = `--skill-cols:${Math.max(xs.length, 1)};--skill-rows:${Math.max(ys.length, 1)}`;
  const activeNode = nodes.find((node) => node.key === activeNodeKey) || nodes[0];
  const activeInfo = activeNode ? skillInfo(draft.replacements[activeNode.key] || activeNode.skillKey) : null;
  const activeCandidateTab = activeSkillCandidateTab(prefix, activeInfo);
  container.innerHTML = `
    <div class="skill-tree-head">
      <div>
        <strong>${escapeHtml(skillTreeOwnerName(prefix))} 낭만 스킬트리</strong>
        <span>${nodes.length}개 노드 · 노드를 선택해 교체할 수 있습니다.</span>
      </div>
      ${SKILL_TREE_EDITING_ENABLED ? `<button type="button" class="ghost-btn mini" data-skill-reset="${prefix}">초기화</button>` : ''}
    </div>
    ${SKILL_TREE_EDITING_ENABLED ? '' : '<p class="skill-tree-readonly">스킬트리 노드 교체는 아직 수정 팩 생성에 반영되지 않아 UI에서 잠가뒀습니다. 위의 역사/낭만 스킬셋 선택만 현재 저장 대상입니다.</p>'}
    <div class="skill-tree-board ${SKILL_TREE_EDITING_ENABLED ? '' : 'readonly'}" style="${gridStyle}">
      ${nodes.map((node) => {
        const x = xs.indexOf(Number(node.position?.x ?? 0)) + 1;
        const y = ys.indexOf(Number(node.position?.y ?? 0)) + 1;
        const replaced = draft.replacements[node.key];
        const info = skillInfo(replaced || node.skillKey);
        const element = info.element || 'none';
        return `
          <${SKILL_TREE_EDITING_ENABLED ? 'button' : 'div'}
            ${SKILL_TREE_EDITING_ENABLED ? 'type="button"' : 'role="listitem"'}
            class="skill-node element-${element} ${node.key === activeNode?.key ? 'active' : ''} ${replaced ? 'changed' : ''}"
            ${SKILL_TREE_EDITING_ENABLED ? `data-skill-node="${escapeHtml(node.key)}" data-skill-prefix="${prefix}"` : ''}
            style="grid-column:${x};grid-row:${y}"
            title="${escapeHtml(`${info.name}\n${skillEffectText(info)}`)}"
          >
            ${skillSourceBadgeMarkup(info)}
            <b>${escapeHtml(info.name)}${replaced ? ' *' : ''}</b>
            <small>${escapeHtml(skillEffectText(info))}</small>
          </${SKILL_TREE_EDITING_ENABLED ? 'button' : 'div'}>
        `;
      }).join('')}
    </div>
    ${SKILL_TREE_EDITING_ENABLED ? `<div class="skill-picker">
      <div class="skill-picker-title">
        <strong>교체할 노드: ${escapeHtml(activeInfo?.name || '노드 선택')}</strong>
        <span>${escapeHtml(skillEffectText(activeInfo))}</span>
      </div>
      <input class="skill-search" data-skill-search="${prefix}" placeholder="스킬 이름이나 효과 검색">
      ${skillCandidateTabsMarkup(prefix, activeCandidateTab)}
      <div class="skill-candidates" data-skill-candidates="${prefix}">
        ${renderSkillCandidates(prefix, '')}
      </div>
    </div>` : ''}
  `;
}

function renderSkillCandidates(prefix, query) {
  const setKey = selectedSkillSetKey(prefix);
  const tree = skillTreeBySet(setKey);
  const nodes = dedupeSkillTreeNodes(tree?.nodes || []);
  const activeNodeKey = state.activeSkillNode?.prefix === prefix ? state.activeSkillNode.nodeKey : nodes[0]?.key;
  if (!activeNodeKey) return '<p class="skill-tree-empty">교체할 노드를 먼저 선택하세요.</p>';
  const activeNode = nodes.find((node) => node.key === activeNodeKey);
  const activeInfo = activeNode ? skillInfo(activeNode.skillKey) : null;
  const activeTab = activeSkillCandidateTab(prefix, activeInfo);
  const q = String(query || '').trim().toLowerCase();
  const candidates = skillIndexList()
    .filter((item) => {
      const haystack = `${item.name} ${item.description} ${item.effectSummary} ${item.key}`.toLowerCase();
      const matchesTab = activeTab === 'all' || item.element === activeTab;
      return matchesTab && (!q || haystack.includes(q));
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
      ${skillSourceBadgeMarkup(item)}
      <b>${escapeHtml(item.name)}</b>
      <span>${escapeHtml(skillEffectText(item))}</span>
    </button>
  `).join('') || '<p class="skill-tree-empty">검색 결과가 없습니다.</p>';
}
