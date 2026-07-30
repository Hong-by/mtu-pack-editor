'use strict';

let buildInFlight = false;

function validationItem(level, title, detail, meta = {}) {
  return { level, title, detail, ...meta };
}

function isProgressValidationItem(item) {
  if (!item || item.level !== 'info') return false;
  const text = `${item.title || ''} ${item.detail || ''}`;
  return /(읽는 중|검증 중|저장 중|갱신 중|불러오는 중|생성 중|처리 중|로딩 중)/.test(text);
}

function saveOperationTiming(operationKey, elapsedMs) {
  if (!operationKey || !Number.isFinite(elapsedMs) || elapsedMs <= 0) return;
  const elapsedSeconds = Math.max(1, Math.round(elapsedMs / 1000));
  const previous = Number(state.operationTimings?.[operationKey] || 0);
  const blended = previous > 0
    ? Math.round(previous * 0.65 + elapsedSeconds * 0.35)
    : elapsedSeconds;
  state.operationTimings = {
    ...(state.operationTimings || {}),
    [operationKey]: blended,
  };
  try {
    window.localStorage?.setItem(OPERATION_TIMING_STORAGE_KEY, JSON.stringify(state.operationTimings));
  } catch {
    // Ignore storage errors; timing estimates are only a UI hint.
  }
}

function progressStatusText(item) {
  const startedAt = Number(item?.progressStartedAt || 0);
  if (!startedAt) return '';
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
  const estimateSeconds = Number(state.operationTimings?.[item.operationKey] || 0);
  if (estimateSeconds > 0) {
    const remainingSeconds = Math.max(0, estimateSeconds - elapsedSeconds);
    return `경과 ${elapsedSeconds}초 · 최근 기준 약 ${remainingSeconds}초 남음`;
  }
  return `경과 ${elapsedSeconds}초 · 예상 시간 계산 중`;
}

function ensureValidationTimer(active) {
  if (active && !state.validationTimerId) {
    state.validationTimerId = window.setInterval(renderValidation, 1000);
  } else if (!active && state.validationTimerId) {
    window.clearInterval(state.validationTimerId);
    state.validationTimerId = null;
  }
}

function scheduleValidation() {
  debounceRender('validation', renderValidation, 80);
}

function bindValidationInput(control) {
  if (!control || control.dataset.validationReady === '1') return;
  control.addEventListener('input', scheduleValidation);
  control.addEventListener('change', scheduleValidation);
  control.dataset.validationReady = '1';
}

function clearReferenceEditWarning() {
  state.serverMessages = state.serverMessages.filter((message) => message.title !== '참조 장수 수정 보류');
}

function renderValidation() {
  syncCreateSubtypeWarning();
  const items = [];
  for (const message of state.serverMessages.slice(-1)) {
    const level = message.level === 'error' ? 'error' : message.level === 'warning' ? 'warning' : message.level === 'ok' ? 'ok' : 'info';
    items.push(validationItem(level, message.title || message.code || 'server_message', message.detail || message.message || String(message), {
      operationKey: message.operationKey,
      progressStartedAt: message.progressStartedAt,
    }));
  }

  $('validationCount').textContent = items.length ? '1개' : '0개';
  $('validationList').innerHTML = items.map((item) => {
    const isProgress = isProgressValidationItem(item);
    const progressText = isProgress ? progressStatusText(item) : '';
    return `
    <article class="validation-item ${item.level} ${isProgress ? 'working' : ''}">
      <b>${isProgress ? '<i class="loading-dot" aria-hidden="true"></i>' : ''}${escapeHtml(item.title)}</b>
      <span>${escapeHtml(item.detail)}</span>
      ${progressText ? `<small class="validation-progress-meta">${escapeHtml(progressText)}</small>` : ''}
      ${isProgress ? '<div class="validation-progress" aria-label="작업 진행 중"><i></i></div>' : ''}
    </article>
  `;
  }).join('');
  ensureValidationTimer(items.some(isProgressValidationItem));
}

function previewRecipe() {
  syncQueuedDedicatedArmourFromEditor();
  const actualRecipe = recipeFromQueue();
  state.lastRecipe = actualRecipe;
  const saveMode = $('saveModeSelect').value;
  const recipe = {
    ...actualRecipe,
    game: 'total_war_three_kingdoms',
    inputPack: $('inputPackPath').value,
    outputMode: saveMode,
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

function materialBuildOptions(saveMode = $('saveModeSelect').value) {
  const enabled = saveMode === INTERNAL_MATERIAL_BUILD.enabledForSaveMode;
  return {
    enabled,
    materialPath: INTERNAL_MATERIAL_BUILD.materialPath,
    coreAssetSourceId: INTERNAL_MATERIAL_BUILD.coreAssetSourceId,
  };
}

function serverPayload() {
  syncQueuedDedicatedArmourFromEditor();
  const saveMode = $('saveModeSelect').value;
  const inPlace = saveMode === 'in_place';
  const materialBuild = materialBuildOptions(saveMode);
  return {
    adapter: 'rpfm',
    inputPath: $('inputPackPath').value,
    outputPath: inPlace ? '' : $('outputPackPath').value,
    referencePackPaths: referencePackPaths(),
    inPlace,
    delta: saveMode === 'patch_pack',
    useInternalMaterials: materialBuild.enabled,
    materialBuildMode: materialBuild.enabled ? 'internal_materials_v015' : 'pack_reference',
    materialPath: materialBuild.enabled ? materialBuild.materialPath : '',
    coreAssetSourceId: materialBuild.enabled ? materialBuild.coreAssetSourceId : '',
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

async function loadPack(options = {}) {
  if (state.loadingPack) return;
  const forceRefresh = Boolean(options.forceRefresh);
  const operationKey = forceRefresh ? 'refreshPack' : 'readPack';
  const progressStartedAt = Date.now();
  state.loadingPack = true;
  state.serverMessages = [validationItem('info', forceRefresh ? 'pack 원본에서 DB 갱신 중' : 'DB 스냅샷 읽는 중', $('inputPackPath').value, {
    operationKey,
    progressStartedAt,
  })];
  renderValidation();
  try {
    const data = await postJson('/api/open', {
      adapter: 'auto',
      inputPath: $('inputPackPath').value,
      referencePackPaths: referencePackPaths(),
      includeVanilla: false,
      forceRefresh,
    });
    hydrateFromPackData(data.characters, data);
    const cacheText = data.cache?.hit ? 'DB 스냅샷 사용' : 'pack 원본 해석 후 DB 저장';
    const referenceOk = (data.characters?.referencePacks || []).filter((item) => item.ok).length;
    const referenceTotal = (data.characters?.referencePacks || []).length;
    const referenceText = referenceTotal ? ` · 참조 pack ${referenceOk}/${referenceTotal}` : '';
    const timings = data.timings || {};
    const detailTimings = data.characters?.timings || {};
    saveOperationTiming(operationKey, Number(timings.total) > 0 ? Number(timings.total) * 1000 : Date.now() - progressStartedAt);
    const timingText = timings.total
      ? ` · ${timings.total}s(open ${timings.openSession || 0}s / read ${timings.readCharacterData || 0}s / merge ${detailTimings.mergeReferences || 0}s / summarize ${detailTimings.summarizePack || 0}s)`
      : '';
    state.serverMessages = [validationItem('info', '팩 읽기 완료', `${state.characters.length}명 로드 · ${cacheText}${referenceText}${timingText}`)];
    renderAll();
  } catch (error) {
    if (!forceRefresh && isMissingSnapshotError(error)) {
      state.loadingPack = false;
      await loadPack({ forceRefresh: true });
      return;
    }
    state.serverMessages = [validationItem(
      'error',
      forceRefresh ? 'DB 갱신 실패' : 'DB 스냅샷 없음',
      error.message,
    )];
    renderValidation();
  } finally {
    state.loadingPack = false;
  }
}

function isMissingSnapshotError(error) {
  const message = String(error?.message || '');
  return message.includes('DB') && (
    message.includes('스냅샷')
    || message.includes('갱신')
    || message.includes('pack 원본')
  );
}

async function validateServerRecipe() {
  const operationKey = 'validateRecipe';
  const progressStartedAt = Date.now();
  state.serverMessages = [validationItem('info', '서버 검증 중', '현재 작업 큐를 CLI recipe로 변환했습니다.', {
    operationKey,
    progressStartedAt,
  })];
  renderValidation();
  try {
    const data = await postJson('/api/validate', serverPayload());
    saveOperationTiming(operationKey, Date.now() - progressStartedAt);
    state.serverMessages = data.messages.length
      ? data.messages
      : [validationItem('ok', '서버 검증 통과', 'CLI 검증 기준으로 막히는 항목이 없습니다.')];
  } catch (error) {
    state.serverMessages = [validationItem('error', '서버 검증 실패', error.message)];
  }
  renderValidation();
}

async function buildServerPack() {
  if (buildInFlight) {
    state.serverMessages = [validationItem('info', '저장 진행 중', '이미 pack 저장을 처리하고 있습니다.')];
    renderValidation();
    return;
  }
  buildInFlight = true;
  const buildButton = $('buildButton');
  const previousDisabled = buildButton?.disabled || false;
  if (buildButton) buildButton.disabled = true;
  const operationKey = 'buildPack';
  const progressStartedAt = Date.now();
  const saveMode = $('saveModeSelect').value;
  const saveTarget = saveMode === 'in_place'
    ? '원본 수정'
    : saveMode === 'patch_pack'
      ? `패치 pack: ${$('outputPackPath').value}`
      : `Save As 원본 복사: ${$('outputPackPath').value}`;
  state.serverMessages = [validationItem('info', '저장 중', saveTarget, {
    operationKey,
    progressStartedAt,
  })];
  renderValidation();
  try {
    const data = await postJson('/api/build', serverPayload());
    saveOperationTiming(operationKey, Date.now() - progressStartedAt);
    state.serverMessages = data.messages?.length
      ? data.messages
      : [validationItem(data.ok === false ? 'error' : 'ok', data.ok === false ? '저장 검증 실패' : '저장 완료', 'pack 생성이 완료되었습니다.')];
  } catch (error) {
    state.serverMessages = [validationItem('error', '저장 실패', `pack 생성에 실패했습니다: ${error.message}`)];
  } finally {
    buildInFlight = false;
    if (buildButton) buildButton.disabled = previousDisabled;
  }
  renderValidation();
}
