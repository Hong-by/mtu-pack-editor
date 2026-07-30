'use strict';

const WORK_QUEUE_STORAGE_KEY = 'mtu-pack-editor.work-queue.v1';
const WORK_QUEUE_STORAGE_VERSION = 1;
const MAX_PERSISTED_WORK_QUEUE_ITEMS = 500;

function normalizePersistedWorkQueue(value) {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item) => (
      item
      && typeof item === 'object'
      && !Array.isArray(item)
      && typeof item.kind === 'string'
      && typeof item.type === 'string'
      && typeof item.title === 'string'
      && (!('payload' in item) || (
        item.payload
        && typeof item.payload === 'object'
        && !Array.isArray(item.payload)
      ))
    ))
    .slice(0, MAX_PERSISTED_WORK_QUEUE_ITEMS);
}

function loadPersistedWorkQueue() {
  try {
    const raw = window.localStorage?.getItem(WORK_QUEUE_STORAGE_KEY);
    if (!raw) return [];
    const stored = JSON.parse(raw);
    const queue = Array.isArray(stored) ? stored : stored?.queue;
    return normalizePersistedWorkQueue(queue);
  } catch (error) {
    console.warn('[MTU Pack Editor] failed to restore work queue', error);
    return [];
  }
}

function loadOperationTimings() {
  try {
    const raw = window.localStorage?.getItem(OPERATION_TIMING_STORAGE_KEY);
    const value = raw ? JSON.parse(raw) : {};
    return value && typeof value === 'object' ? value : {};
  } catch {
    return {};
  }
}

const state = {
  characters: SAMPLE_CHARACTERS,
  options: null,
  dedicatedArmour: null,
  selectedKey: SAMPLE_CHARACTERS[0].key,
  filter: 'all',
  mode: 'edit',
  workView: 'queue',
  workflowGender: 'male',
  editGender: 'male',
  createGender: 'male',
  queue: loadPersistedWorkQueue(),
  serverMessages: [],
  lastRecipe: null,
  loadingPack: false,
  editingQueueIndex: null,
  skillTreeDrafts: {},
  activeSkillNode: null,
  skillCandidateTabs: {},
  titleFilters: {
    edit: 'all',
    source: 'all',
  },
  selectedAppearanceCardKey: '',
  imageGalleryQuery: '',
  favoriteAppearanceKeys: loadFavoriteAppearanceKeys(),
  favoriteCharacterKeys: loadFavoriteCharacterKeys(),
  operationTimings: loadOperationTimings(),
  validationTimerId: null,
  formOptionsSignature: '',
  titleOptionsSignatures: {},
  dataVersion: 0,
  assetCacheVersion: 0,
  derivedCache: {},
  renderTimers: {},
  rosterRenderLimit: ROSTER_INITIAL_RENDER_LIMIT,
  appearanceGalleryRenderLimit: APPEARANCE_GALLERY_INITIAL_RENDER_LIMIT,
  rosterResultCount: 0,
  rosterRenderedCount: 0,
  rosterFilteredCharacters: [],
  appearanceGalleryResultCount: 0,
};

const INTERNAL_MATERIAL_BUILD = {
  enabledForSaveMode: 'patch_pack',
  materialPath: 'work\\internal_materials\\materials.v015.json',
  coreAssetSourceId: '17309a40b912',
};

const $ = (id) => document.getElementById(id);

function persistWorkQueue() {
  try {
    window.localStorage?.setItem(
      WORK_QUEUE_STORAGE_KEY,
      JSON.stringify({
        version: WORK_QUEUE_STORAGE_VERSION,
        savedAt: new Date().toISOString(),
        queue: normalizePersistedWorkQueue(state.queue),
      }),
    );
    return true;
  } catch (error) {
    console.warn('[MTU Pack Editor] failed to persist work queue', error);
    return false;
  }
}

function invalidateDerivedCaches() {
  state.derivedCache = {};
}

function bumpDataVersion() {
  state.dataVersion += 1;
  invalidateDerivedCaches();
  state.formOptionsSignature = '';
  state.titleOptionsSignatures = {};
  resetRosterRenderLimit();
  resetAppearanceGalleryRenderLimit();
}

function cachedDerived(key, build) {
  const cacheKey = `${state.dataVersion}:${key}`;
  const cached = state.derivedCache?.[cacheKey];
  if (cached !== undefined) return cached;
  const value = build();
  state.derivedCache[cacheKey] = value;
  return value;
}

function debounceRender(key, callback, delay = INPUT_RENDER_DEBOUNCE_MS) {
  if (state.renderTimers[key]) {
    window.clearTimeout(state.renderTimers[key]);
  }
  state.renderTimers[key] = window.setTimeout(() => {
    state.renderTimers[key] = 0;
    callback();
  }, delay);
}

function cappedList(items, limit) {
  const safeLimit = Math.max(1, Number(limit) || items.length || 1);
  return {
    visible: items.slice(0, safeLimit),
    hiddenCount: Math.max(0, items.length - safeLimit),
  };
}

function renderScrollLoadMarker(hiddenCount) {
  if (!hiddenCount) return '';
  return '<p class="lazy-load-sentinel" aria-hidden="true">스크롤하면 더 표시됩니다</p>';
}

function resetRosterRenderLimit() {
  state.rosterRenderLimit = ROSTER_INITIAL_RENDER_LIMIT;
  state.rosterRenderedCount = 0;
  state.rosterFilteredCharacters = [];
}

function resetAppearanceGalleryRenderLimit() {
  state.appearanceGalleryRenderLimit = APPEARANCE_GALLERY_INITIAL_RENDER_LIMIT;
}

function isNearScrollEnd(container, threshold = 220) {
  if (!container) return false;
  if (container === window || container === document || container === document.documentElement) {
    const scrollTop = window.scrollY || document.documentElement.scrollTop || 0;
    const clientHeight = window.innerHeight || document.documentElement.clientHeight || 0;
    const scrollHeight = document.documentElement.scrollHeight || 0;
    return scrollTop + clientHeight >= scrollHeight - threshold;
  }
  return container.scrollTop + container.clientHeight >= container.scrollHeight - threshold;
}

function maybeLoadMoreRoster() {
  if (state.rosterRenderedCount >= state.rosterResultCount) return;
  const list = $('characterList');
  if (!isNearScrollEnd(list)) return;
  appendRosterSlice();
}

function maybeLoadMoreAppearanceGallery() {
  if (state.appearanceGalleryRenderLimit >= state.appearanceGalleryResultCount) return;
  const panel = document.querySelector('.detail-panel');
  if (!isNearScrollEnd(panel || window)) return;
  const scrollTop = panel?.scrollTop ?? 0;
  state.appearanceGalleryRenderLimit = Math.min(
    state.appearanceGalleryRenderLimit + SCROLL_RENDER_STEP,
    state.appearanceGalleryResultCount,
  );
  renderAppearanceGallery();
  if (panel) panel.scrollTop = scrollTop;
}
