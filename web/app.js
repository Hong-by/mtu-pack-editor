const state = {
  analysis: null,
  characters: [],
  artSets: [],
  ageRanges: [],
  initialCeos: [],
  selectedKey: null,
  recipe: {
    modName: "hby_web_recipe",
    equipmentStatPatches: [],
    characterPatches: [],
    characterCloneRecipes: []
  }
};

const $ = (id) => document.getElementById(id);

const fields = {
  adapter: $("adapterSelect"),
  inputPath: $("inputPath"),
  outputPath: $("outputPath"),
  includeVanilla: $("includeVanilla"),
  inPlace: $("inPlace"),
  status: $("statusText"),
  list: $("characterList"),
  search: $("searchInput"),
  recipe: $("recipeText"),
  log: $("logOutput")
};

function setStatus(text) {
  fields.status.textContent = text;
}

function appendLog(entry) {
  const text = typeof entry === "string" ? entry : JSON.stringify(entry, null, 2);
  fields.log.textContent = `${new Date().toLocaleTimeString()} ${text}\n\n${fields.log.textContent}`;
}

async function postJson(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || JSON.stringify(data));
  }
  return data;
}

function requestBase() {
  return {
    adapter: fields.adapter.value,
    inputPath: fields.inputPath.value,
    includeVanilla: fields.includeVanilla.checked
  };
}

async function openPack() {
  setStatus("여는 중");
  const data = await postJson("/api/open", requestBase());
  state.analysis = data.analysis;
  const summary = data.characters.pack;
  state.characters = summary.characters;
  state.artSets = summary.artSets;
  state.ageRanges = summary.ageRanges;
  state.initialCeos = summary.initialCeos;
  renderCharacters();
  fillCloneSources();
  if (!state.selectedKey && state.characters.length) {
    selectCharacter(state.characters[0].key);
  }
  if (data.characters.vanilla.error) {
    appendLog(data.characters.vanilla.error);
  }
  setStatus(`${data.analysis.packName} · 장수 ${state.characters.length}명`);
  appendLog({ opened: data.analysis.packName, tables: data.analysis.dbTables.length });
}

function renderCharacters() {
  const query = fields.search.value.trim().toLowerCase();
  fields.list.innerHTML = "";
  for (const character of state.characters) {
    const haystack = `${character.displayName || ""} ${character.key}`.toLowerCase();
    if (query && !haystack.includes(query)) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = `character-row${character.key === state.selectedKey ? " active" : ""}`;
    button.innerHTML = `
      <div>
        <strong>${escapeHtml(character.displayName || character.key)}</strong>
        <span>${escapeHtml(character.key)}</span>
        <span>${escapeHtml(character.subtype || "")} · ${escapeHtml(character.artSet || "")}</span>
      </div>
      <b class="mode-count">${character.details.length}</b>
    `;
    button.addEventListener("click", () => selectCharacter(character.key));
    fields.list.appendChild(button);
  }
}

function selectCharacter(key) {
  state.selectedKey = key;
  const character = findCharacter(key);
  if (!character) return;
  $("patchTemplate").value = character.key;
  $("patchWeight").value = character.weight ?? "";
  $("patchMinRound").value = character.minSpawnRound ?? "";
  $("patchMaxRound").value = character.maxSpawnRound ?? "";
  const historical = character.details.find((detail) => detail.gameMode === "historical") || {};
  const romance = character.details.find((detail) => detail.gameMode === "romance") || {};
  $("patchHistRetinue").value = historical.retinue || "";
  $("patchHistSkill").value = historical.skillSet || "";
  $("patchRomanceRetinue").value = romance.retinue || "";
  $("patchRomanceSkill").value = romance.skillSet || "";
  $("cloneBody").value = character.key;
  $("cloneDetails").value = character.key;
  setCloneDefaults(character);
  renderCharacters();
}

function setCloneDefaults(character) {
  const suffix = character.key.replace(/^3k_/, "hby_").replace(/[^a-zA-Z0-9_]/g, "_");
  $("cloneTemplateKey").value = `${suffix}_clone`;
  $("cloneArtKey").value = `hby_art_set_${Date.now().toString().slice(-6)}`;
  $("cloneAgeKey").value = `hby_age_${Date.now().toString().slice(-6)}`;
  $("cloneCeoKey").value = `hby_ceo_initial_${Date.now().toString().slice(-6)}`;
  $("cloneSubtype").value = character.subtype || "";
  $("cloneWeight").value = character.weight ?? 0;
  $("cloneBirthYear").value = 172;
  if (state.artSets.includes(character.artSet)) $("cloneArt").value = character.artSet;
  if (state.ageRanges.includes(character.ageRange)) $("cloneAge").value = character.ageRange;
  const detail = character.details.find((item) => item.initialCeos);
  if (detail && state.initialCeos.includes(detail.initialCeos)) $("cloneCeo").value = detail.initialCeos;
}

function fillCloneSources() {
  fillSelect($("cloneBody"), state.characters.map((item) => ({ value: item.key, label: characterLabel(item) })));
  fillSelect($("cloneDetails"), state.characters.map((item) => ({ value: item.key, label: characterLabel(item) })));
  fillSelect($("cloneArt"), state.artSets.map((value) => ({ value, label: value })));
  fillSelect($("cloneAge"), state.ageRanges.map((value) => ({ value, label: value })));
  fillSelect($("cloneCeo"), state.initialCeos.map((value) => ({ value, label: value })));
}

function fillSelect(select, options) {
  select.innerHTML = "";
  for (const item of options) {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    select.appendChild(option);
  }
}

function characterLabel(character) {
  return character.displayName ? `${character.displayName} · ${character.key}` : character.key;
}

function stagePatch() {
  const key = $("patchTemplate").value;
  if (!key) return;
  upsertByKey(state.recipe.characterPatches, "templateKey", {
    templateKey: key,
    templateOverrides: {
      weight: numberValue("patchWeight"),
      min_spawn_round: numberValue("patchMinRound"),
      max_spawn_round: numberValue("patchMaxRound")
    },
    detailOverrides: {
      historical: compactObject({
        retinue: $("patchHistRetinue").value,
        skill_set_override: $("patchHistSkill").value
      }),
      romance: compactObject({
        retinue: $("patchRomanceRetinue").value,
        skill_set_override: $("patchRomanceSkill").value
      })
    }
  });
  renderRecipe();
  appendLog(`수정 반영: ${key}`);
}

function stageClone() {
  const clone = {
    newTemplateKey: $("cloneTemplateKey").value,
    sourceTemplateKey: $("cloneBody").value,
    detailSourceTemplateKey: $("cloneDetails").value,
    newArtSetId: $("cloneArtKey").value,
    artSetSourceId: $("cloneArt").value,
    newAgeRangeKey: $("cloneAgeKey").value,
    ageRangeSourceKey: $("cloneAge").value,
    newInitialCeoKey: $("cloneCeoKey").value,
    initialCeoSourceKey: $("cloneCeo").value,
    templateOverrides: compactObject({
      subtype: $("cloneSubtype").value,
      weight: numberValue("cloneWeight")
    }),
    detailOverrides: {},
    ageRangeOverrides: compactObject({
      birth_year: numberValue("cloneBirthYear")
    })
  };
  upsertByKey(state.recipe.characterCloneRecipes, "newTemplateKey", clone);
  renderRecipe();
  appendLog(`신규 반영: ${clone.newTemplateKey}`);
}

async function validateRecipe() {
  syncRecipeFromText();
  setStatus("검증 중");
  const data = await postJson("/api/validate", {
    ...requestBase(),
    outputPath: fields.outputPath.value,
    recipe: state.recipe
  });
  appendLog(data.messages);
  setStatus(data.ok ? "검증 완료" : "검증 실패");
}

async function buildPack() {
  syncRecipeFromText();
  setStatus("저장 중");
  const data = await postJson("/api/build", {
    ...requestBase(),
    outputPath: fields.inPlace.checked ? null : fields.outputPath.value,
    inPlace: fields.inPlace.checked,
    recipe: state.recipe
  });
  appendLog(data.messages);
  setStatus(data.ok ? "저장 완료" : "저장 실패");
}

function syncRecipeFromText() {
  state.recipe = JSON.parse(fields.recipe.value || "{}");
}

function renderRecipe() {
  fields.recipe.value = JSON.stringify(state.recipe, null, 2);
}

function findCharacter(key) {
  return state.characters.find((character) => character.key === key);
}

function upsertByKey(list, keyName, item) {
  const index = list.findIndex((existing) => existing[keyName] === item[keyName]);
  if (index >= 0) list[index] = item;
  else list.push(item);
}

function numberValue(id) {
  const raw = $(id).value;
  if (raw === "") return undefined;
  const value = Number(raw);
  return Number.isFinite(value) ? value : undefined;
}

function compactObject(object) {
  return Object.fromEntries(
    Object.entries(object).filter(([, value]) => value !== undefined && value !== "")
  );
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function switchTab(name) {
  for (const button of document.querySelectorAll(".tab")) {
    button.classList.toggle("active", button.dataset.tab === name);
  }
  for (const panel of document.querySelectorAll(".tab-panel")) {
    panel.classList.toggle("active", panel.id === `${name}Tab`);
  }
}

for (const button of document.querySelectorAll(".tab")) {
  button.addEventListener("click", () => switchTab(button.dataset.tab));
}

$("openButton").addEventListener("click", () => openPack().catch((error) => {
  setStatus("열기 실패");
  appendLog(error.message);
}));
$("validateButton").addEventListener("click", () => validateRecipe().catch((error) => {
  setStatus("검증 실패");
  appendLog(error.message);
}));
$("buildButton").addEventListener("click", () => buildPack().catch((error) => {
  setStatus("저장 실패");
  appendLog(error.message);
}));
$("stagePatchButton").addEventListener("click", stagePatch);
$("stageCloneButton").addEventListener("click", stageClone);
fields.search.addEventListener("input", renderCharacters);
fields.inPlace.addEventListener("change", () => {
  fields.outputPath.disabled = fields.inPlace.checked;
});

renderRecipe();
openPack().catch((error) => appendLog(error.message));
