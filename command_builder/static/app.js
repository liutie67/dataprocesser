const state = {
  profiles: [],
  currentId: null,
  command: "",
  dirty: false,
  formLoading: false,
  historyTimer: null,
  previewTimer: null,
  previewSequence: 0,
  parseSnapshot: null,
  draggedCard: null,
  savedProfileName: null,
  savedStructure: null,
  historyWidth: 280,
  historyPreferredWidth: 280,
  historyResize: null,
};

const $ = (selector) => document.querySelector(selector);
const elements = {
  layout: $("#main-layout"),
  profilePanel: $("#profile-panel"),
  historyPanel: $("#history-panel"),
  historyResizer: $("#history-resizer"),
  profileList: $("#profile-list"),
  name: $("#profile-name"),
  invocationMode: $("#invocation-mode"),
  scriptPath: $("#script-path"),
  scriptPathLabel: $("#script-path-label"),
  prefix: $("#prefix"),
  shell: $("#shell"),
  argumentList: $("#argument-list"),
  saveState: $("#save-state"),
  result: $("#command-result code"),
  previewError: $("#preview-error"),
  copyResult: $("#copy-result"),
  historyList: $("#history-list"),
  historySearch: $("#history-search"),
  importFile: $("#import-file"),
  importMode: $("#import-mode"),
  commandInput: $("#command-input"),
  dialect: $("#dialect-select"),
  parseStatus: $("#parse-status"),
  undoParse: $("#undo-parse"),
  conflictDialog: $("#name-conflict-dialog"),
  conflictTitle: $("#name-conflict-title"),
  conflictMessage: $("#name-conflict-message"),
  overwriteProfile: $("#overwrite-profile"),
  toast: $("#toast"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: options.body ? { "Content-Type": "application/json", ...(options.headers || {}) } : options.headers,
  });
  if (!response.ok) {
    let detail = `请求失败（${response.status}）`;
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") detail = payload.detail;
      else if (Array.isArray(payload.detail)) detail = payload.detail.map((item) => item.msg).join("；");
    } catch (_) { /* use default message */ }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  if (response.status === 204) return null;
  return response.json();
}

function showToast(message, isError = false) {
  elements.toast.textContent = message;
  elements.toast.className = `toast show${isError ? " error" : ""}`;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => { elements.toast.className = "toast"; }, 2800);
}

function setDirtyState(dirty, message = null) {
  state.dirty = dirty;
  elements.saveState.textContent = message || (dirty ? "有未保存修改" : "已保存");
  elements.saveState.className = `save-state${dirty ? "" : " saved"}`;
}

function markDirty() {
  if (state.formLoading) return;
  setDirtyState(true);
  schedulePreview();
}

function markSaved() {
  setDirtyState(false);
}

function confirmDiscard() {
  return !state.dirty || confirm("当前配置有未保存修改，确定放弃这些修改？");
}

function emptyProfile() {
  return {
    name: "",
    script_path: "",
    invocation_mode: "script",
    prefix: "python",
    shell: "powershell",
    arguments: [],
  };
}

function makeArgument() {
  return {
    id: crypto.randomUUID(),
    position: elements.argumentList.querySelectorAll(".argument-card").length,
    mode: "named",
    token: "--参数",
    value_type: "str",
    value: "",
    choices: [],
    enabled: true,
  };
}

function updateInvocationFields() {
  const isModule = elements.invocationMode.value === "module";
  elements.scriptPathLabel.textContent = isModule ? "Python 模块名" : "Python 文件路径";
  elements.scriptPath.placeholder = isModule
    ? "例如：package.module"
    : "例如：.\\testbench.py 或 C:\\项目\\testbench.py";
}

function populateForm(profile) {
  state.formLoading = true;
  elements.name.value = profile.name || "";
  elements.scriptPath.value = profile.script_path || "";
  elements.invocationMode.value = profile.invocation_mode || "script";
  elements.prefix.value = profile.prefix || "python";
  elements.shell.value = profile.shell || "powershell";
  updateInvocationFields();
  elements.argumentList.replaceChildren();
  [...(profile.arguments || [])].sort((a, b) => a.position - b.position).forEach(addArgumentCard);
  if (!profile.arguments?.length) renderArgumentEmptyState();
  refreshMoveButtons();
  state.formLoading = false;
  schedulePreview(true);
}

function setProfileForm(profile) {
  populateForm(profile);
  state.savedProfileName = profile.name;
  state.savedStructure = structureSignature(profile);
  state.parseSnapshot = null;
  elements.undoParse.classList.add("hidden");
  elements.parseStatus.textContent = "";
  markSaved();
}

function renderArgumentEmptyState() {
  if (!elements.argumentList.querySelector(".argument-card")) {
    const empty = document.createElement("div");
    empty.className = "empty-state argument-empty";
    empty.textContent = "还没有参数。点击“添加参数”开始配置。";
    elements.argumentList.append(empty);
  }
}

function clearArgumentEmptyState() {
  elements.argumentList.querySelector(".argument-empty")?.remove();
}

function splitChoices(value) {
  return value.split(/[\n,]/).map((item) => item.trim()).filter((item, index, all) => item && all.indexOf(item) === index);
}

function renderValueControl(card, value) {
  const slot = card.querySelector(".value-slot");
  const type = card.querySelector(".arg-type").value;
  slot.replaceChildren();
  let control;
  if (type === "bool") {
    control = document.createElement("input");
    control.type = "checkbox";
    control.checked = value === true || value === "true";
    control.title = "勾选后在命令中加入此开关，取消勾选后移除";
  } else if (type === "choice") {
    control = document.createElement("select");
    const choices = splitChoices(card.querySelector(".arg-choices").value);
    choices.forEach((choice) => {
      const option = document.createElement("option");
      option.value = choice;
      option.textContent = choice;
      control.append(option);
    });
    if (value != null && choices.includes(String(value))) control.value = String(value);
  } else {
    control = document.createElement("input");
    control.type = type === "int" || type === "float" ? "number" : "text";
    if (control.type === "number") {
      control.addEventListener("wheel", (event) => event.preventDefault(), { passive: false });
    }
    if (type === "float") control.step = "any";
    control.placeholder = type === "path" ? "路径或文件名" : "参数值";
    control.value = value ?? "";
  }
  control.className = "arg-value";
  control.setAttribute("aria-label", type === "bool" ? "是否加入此布尔开关" : "当前值");
  control.addEventListener("input", () => { validateArgumentCard(card); markDirty(); });
  control.addEventListener("change", () => { validateArgumentCard(card); markDirty(); });
  slot.append(control);
}

function validateArgumentCard(card) {
  const enabled = card.querySelector(".arg-enabled").checked;
  const mode = card.querySelector(".arg-mode").value;
  const type = card.querySelector(".arg-type").value;
  const token = card.querySelector(".arg-token").value.trim();
  const value = card.querySelector(".arg-value");
  let message = "";
  if (enabled && mode === "named" && !token.startsWith("-")) message = "命名参数必须以 - 或 -- 开头";
  else if (enabled && type === "choice" && !splitChoices(card.querySelector(".arg-choices").value).length) message = "请至少填写一个候选值";
  else if (enabled && type !== "bool" && (!value || value.value === "")) message = "启用的参数必须填写当前值";
  card.classList.toggle("invalid", Boolean(message));
  card.querySelector(".arg-error").textContent = message;
  return !message;
}

function validateAllArguments() {
  return [...elements.argumentList.querySelectorAll(".argument-card")].every(validateArgumentCard);
}

function updateArgumentCard(card) {
  const enabled = card.querySelector(".arg-enabled").checked;
  const mode = card.querySelector(".arg-mode").value;
  const type = card.querySelector(".arg-type").value;
  card.classList.toggle("disabled", !enabled);
  card.querySelector(".token-field").classList.toggle("hidden", mode === "positional");
  card.querySelector(".choices-field").classList.toggle("hidden", type !== "choice");
  [...card.querySelector(".arg-type").options].forEach((option) => {
    if (option.value === "bool") option.disabled = mode === "positional";
  });
  validateArgumentCard(card);
}

function moveCard(card, direction) {
  const sibling = direction < 0 ? card.previousElementSibling : card.nextElementSibling;
  if (!sibling || !sibling.classList.contains("argument-card")) return;
  if (direction < 0) elements.argumentList.insertBefore(card, sibling);
  else elements.argumentList.insertBefore(sibling, card);
  refreshMoveButtons();
  card.focus({ preventScroll: true });
  markDirty();
}

function refreshMoveButtons() {
  const cards = [...elements.argumentList.querySelectorAll(".argument-card")];
  cards.forEach((card, index) => {
    card.querySelector(".move-up").disabled = index === 0;
    card.querySelector(".move-down").disabled = index === cards.length - 1;
  });
}

function addArgumentCard(argument) {
  clearArgumentEmptyState();
  const card = document.createElement("div");
  card.className = `argument-card${argument.enabled === false ? " disabled" : ""}`;
  card.dataset.id = argument.id || crypto.randomUUID();
  card.tabIndex = 0;
  card.innerHTML = `
    <button class="drag-handle" type="button" draggable="true" title="拖拽排序" aria-label="拖拽排序">⠿</button>
    <label class="check-label" title="启用参数"><input class="arg-enabled" type="checkbox" aria-label="启用参数"><span>启用</span></label>
    <label><span>模式</span><select class="arg-mode" aria-label="参数模式"><option value="named">命名参数</option><option value="positional">位置参数</option></select></label>
    <label><span>类型</span><select class="arg-type" aria-label="值类型"><option value="str">str</option><option value="path">Path</option><option value="int">int</option><option value="float">float</option><option value="choice">choices</option><option value="bool">bool 开关</option></select></label>
    <label class="token-field"><span>参数标记</span><input class="arg-token" maxlength="128" placeholder="--budget" aria-label="参数标记"></label>
    <label class="value-field"><span>当前值</span><span class="value-slot"></span></label>
    <div class="argument-tools"><button class="mini-button move-up" type="button" title="上移">↑</button><button class="mini-button move-down" type="button" title="下移">↓</button><button class="mini-button delete" type="button" title="删除">×</button></div>
    <label class="choices-field hidden"><span>候选值（逗号或换行分隔）</span><input class="arg-choices" placeholder="small, medium, large"></label>
    <span class="arg-error" role="status"></span>
  `;
  card.querySelector(".arg-enabled").checked = argument.enabled !== false;
  card.querySelector(".arg-mode").value = argument.mode || "named";
  card.querySelector(".arg-type").value = argument.value_type || "str";
  card.querySelector(".arg-token").value = argument.token || "";
  card.querySelector(".arg-choices").value = (argument.choices || []).join(", ");
  elements.argumentList.append(card);
  renderValueControl(card, argument.value);
  updateArgumentCard(card);

  card.querySelector(".arg-enabled").addEventListener("change", () => { updateArgumentCard(card); markDirty(); });
  card.querySelector(".arg-mode").addEventListener("change", () => {
    if (card.querySelector(".arg-mode").value === "positional" && card.querySelector(".arg-type").value === "bool") {
      card.querySelector(".arg-type").value = "str";
      renderValueControl(card, "");
    }
    updateArgumentCard(card);
    markDirty();
  });
  card.querySelector(".arg-type").addEventListener("change", () => {
    const type = card.querySelector(".arg-type").value;
    // Selecting a bool type represents adding a command-line switch. Start it
    // enabled so the preview changes immediately; the visible checkbox then
    // controls whether the switch is included.
    renderValueControl(card, type === "bool" ? true : "");
    updateArgumentCard(card);
    markDirty();
  });
  card.querySelector(".arg-choices").addEventListener("input", () => {
    const current = card.querySelector(".arg-value")?.value || "";
    renderValueControl(card, current);
    validateArgumentCard(card);
    markDirty();
  });
  card.querySelector(".arg-token").addEventListener("input", () => { validateArgumentCard(card); markDirty(); });
  card.querySelector(".delete").addEventListener("click", () => {
    card.remove();
    renderArgumentEmptyState();
    refreshMoveButtons();
    markDirty();
  });
  card.querySelector(".move-up").addEventListener("click", () => moveCard(card, -1));
  card.querySelector(".move-down").addEventListener("click", () => moveCard(card, 1));
  card.addEventListener("keydown", (event) => {
    if (!event.altKey || !["ArrowUp", "ArrowDown"].includes(event.key)) return;
    event.preventDefault();
    moveCard(card, event.key === "ArrowUp" ? -1 : 1);
  });
  const handle = card.querySelector(".drag-handle");
  handle.addEventListener("dragstart", (event) => {
    state.draggedCard = card;
    card.classList.add("dragging");
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", card.dataset.id);
  });
  handle.addEventListener("dragend", () => {
    card.classList.remove("dragging");
    elements.argumentList.querySelectorAll(".drag-over").forEach((item) => item.classList.remove("drag-over"));
    state.draggedCard = null;
    refreshMoveButtons();
    markDirty();
  });
  refreshMoveButtons();
}

function readArguments() {
  return [...elements.argumentList.querySelectorAll(".argument-card")].map((card, position) => {
    const type = card.querySelector(".arg-type").value;
    const valueControl = card.querySelector(".arg-value");
    return {
      id: card.dataset.id,
      position,
      mode: card.querySelector(".arg-mode").value,
      token: card.querySelector(".arg-mode").value === "named" ? card.querySelector(".arg-token").value.trim() : "",
      value_type: type,
      value: type === "bool" ? valueControl.checked : valueControl.value,
      choices: type === "choice" ? splitChoices(card.querySelector(".arg-choices").value) : [],
      enabled: card.querySelector(".arg-enabled").checked,
    };
  });
}

function readDraft() {
  return {
    script_path: elements.scriptPath.value.trim(),
    invocation_mode: elements.invocationMode.value,
    prefix: elements.prefix.value,
    shell: elements.shell.value,
    arguments: readArguments(),
  };
}

function readProfileForm() {
  return { name: elements.name.value.trim(), ...readDraft() };
}

function structureSignature(profile) {
  return JSON.stringify((profile.arguments || []).map((argument) => [argument.mode, argument.value_type]));
}

function hasSavedNameChanged(name) {
  return Boolean(state.currentId && state.savedProfileName !== null && name !== state.savedProfileName);
}

function schedulePreview(immediate = false) {
  clearTimeout(state.previewTimer);
  const delay = immediate ? 0 : 200;
  state.previewTimer = setTimeout(() => refreshPreview().catch(() => {}), delay);
}

async function refreshPreview() {
  const draft = readDraft();
  const sequence = ++state.previewSequence;
  if (!draft.script_path) {
    state.command = "";
    elements.result.textContent = elements.invocationMode.value === "module" ? "填写模块名后将自动生成" : "填写脚本路径后将自动生成";
    elements.previewError.textContent = "";
    elements.copyResult.disabled = true;
    return;
  }
  if (!validateAllArguments()) {
    state.command = "";
    elements.result.textContent = "请先修正参数行中的问题";
    elements.previewError.textContent = "存在无效参数，暂时无法生成预览。";
    elements.copyResult.disabled = true;
    return;
  }
  try {
    const result = await api("/api/commands/preview", { method: "POST", body: JSON.stringify(draft) });
    if (sequence !== state.previewSequence) return;
    state.command = result.command;
    elements.result.textContent = result.command;
    elements.previewError.textContent = "";
    elements.copyResult.disabled = false;
  } catch (error) {
    if (sequence !== state.previewSequence) return;
    state.command = "";
    elements.result.textContent = "暂时无法生成预览";
    elements.previewError.textContent = error.message;
    elements.copyResult.disabled = true;
  }
}

function suggestedProfileName() {
  const target = elements.scriptPath.value.trim();
  if (!target) return "未命名配置";
  if (elements.invocationMode.value === "module") return target.split(".").at(-1) || "未命名配置";
  return target.split(/[\\/]/).at(-1).replace(/\.pyw?$/i, "") || "未命名配置";
}

function findNameConflict(name, excludeId = state.currentId) {
  const normalized = name.trim().toLocaleLowerCase();
  return state.profiles.find((profile) => profile.name.toLocaleLowerCase() === normalized && profile.id !== excludeId);
}

function nextNumberedName(baseName) {
  const names = new Set(state.profiles.map((item) => item.name.toLocaleLowerCase()));
  let number = 1;
  while (names.has(`${baseName} ${number}`.toLocaleLowerCase())) number += 1;
  return `${baseName} ${number}`;
}

function askSaveChoice({ name, structuralChange = false }) {
  elements.conflictTitle.textContent = structuralChange ? "参数结构已变化" : "已有同名配置";
  elements.overwriteProfile.textContent = structuralChange ? "覆盖原配置" : "覆盖同名配置";
  elements.conflictMessage.textContent = structuralChange
    ? `配置“${name}”的参数数量、模式或类型已经变化。可以覆盖原配置，或以“${nextNumberedName(name)}”另存。`
    : `配置“${name}”已经存在。可以覆盖已有配置，或以“${nextNumberedName(name)}”另存。`;
  return new Promise((resolve) => {
    elements.conflictDialog.addEventListener("close", () => resolve(elements.conflictDialog.returnValue || "cancel"), { once: true });
    elements.conflictDialog.showModal();
  });
}

async function persistProfile(payload, targetId = state.currentId) {
  const method = targetId ? "PUT" : "POST";
  const path = targetId ? `/api/profiles/${targetId}` : "/api/profiles";
  const saved = await api(path, { method, body: JSON.stringify(payload) });
  state.currentId = saved.id;
  elements.name.value = saved.name;
  await loadProfiles(false);
  state.savedProfileName = saved.name;
  state.savedStructure = structureSignature(saved);
  markSaved();
  return saved;
}

async function saveCurrentProfile({ resolveConflicts = true } = {}) {
  const payload = readProfileForm();
  if (!payload.name) throw new Error("请填写配置名称");
  if (!payload.script_path) throw new Error(payload.invocation_mode === "module" ? "请填写 Python 模块名" : "请填写 Python 文件路径");
  if (!validateAllArguments()) throw new Error("请先修正参数行中的问题");
  const nameChanged = hasSavedNameChanged(payload.name);
  const structuralChange = Boolean(
    state.currentId
    && !nameChanged
    && state.savedStructure !== null
    && structureSignature(payload) !== state.savedStructure
  );
  if (structuralChange && resolveConflicts) {
    const choice = await askSaveChoice({ name: payload.name, structuralChange: true });
    if (choice === "cancel") return null;
    if (choice === "overwrite") return persistProfile(payload, state.currentId);
    payload.name = nextNumberedName(payload.name);
    elements.name.value = payload.name;
    return persistProfile(payload, null);
  }
  const targetId = nameChanged ? null : state.currentId;
  try {
    return await persistProfile(payload, targetId);
  } catch (error) {
    if (error.status !== 409 || !resolveConflicts) throw error;
    await loadProfiles(false);
    const conflict = findNameConflict(payload.name, null);
    if (!conflict) throw error;
    const choice = await askSaveChoice({ name: payload.name });
    if (choice === "cancel") return null;
    if (choice === "overwrite") return persistProfile(payload, conflict.id);
    payload.name = nextNumberedName(payload.name);
    elements.name.value = payload.name;
    return persistProfile(payload, null);
  }
}

async function loadProfiles(selectFirst = true) {
  state.profiles = await api("/api/profiles");
  renderProfiles();
  if (selectFirst && !state.currentId && state.profiles.length) selectProfile(state.profiles[0].id, true);
}

function renderProfiles() {
  elements.profileList.replaceChildren();
  if (!state.profiles.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "还没有保存的配置";
    elements.profileList.append(empty);
    return;
  }
  state.profiles.forEach((profile) => {
    const button = document.createElement("button");
    button.className = `profile-item${profile.id === state.currentId ? " active" : ""}`;
    const name = document.createElement("strong");
    name.textContent = profile.name;
    const path = document.createElement("small");
    path.textContent = profile.invocation_mode === "module" ? `-m ${profile.script_path}` : profile.script_path;
    button.append(name, path);
    button.addEventListener("click", () => selectProfile(profile.id));
    elements.profileList.append(button);
  });
}

function selectProfile(profileId, skipGuard = false) {
  if (profileId === state.currentId && !skipGuard) return;
  if (!skipGuard && !confirmDiscard()) return;
  const profile = state.profiles.find((item) => item.id === profileId);
  if (!profile) return;
  state.currentId = profile.id;
  setProfileForm(profile);
  renderProfiles();
}

function newProfile(skipGuard = false) {
  if (!skipGuard && !confirmDiscard()) return;
  state.currentId = null;
  state.savedProfileName = null;
  state.savedStructure = null;
  populateForm(emptyProfile());
  state.parseSnapshot = null;
  elements.undoParse.classList.add("hidden");
  setDirtyState(false, "新配置，尚未保存");
  renderProfiles();
  elements.name.focus();
}

function nextCopyName(original) {
  const names = new Set(state.profiles.map((item) => item.name.toLocaleLowerCase()));
  let candidate = `${original} 副本`;
  let number = 2;
  while (names.has(candidate.toLocaleLowerCase())) {
    candidate = `${original} 副本 ${number}`;
    number += 1;
  }
  return candidate;
}

async function parseExistingCommand() {
  const command = elements.commandInput.value.trim();
  if (!command) return showToast("请先粘贴一条命令", true);
  if (!confirmDiscard()) return;
  const button = $("#parse-command");
  button.disabled = true;
  elements.parseStatus.className = "inline-status";
  elements.parseStatus.textContent = "正在解析…";
  try {
    const result = await api("/api/commands/parse", {
      method: "POST",
      body: JSON.stringify({ command, dialect: elements.dialect.value, fallback_shell: elements.shell.value }),
    });
    state.parseSnapshot = {
      profile: readProfileForm(),
      currentId: state.currentId,
      dirty: state.dirty,
      savedProfileName: state.savedProfileName,
      savedStructure: state.savedStructure,
    };
    const currentName = elements.name.value.trim();
    const target = result.draft.script_path;
    const fallbackName = result.draft.invocation_mode === "module"
      ? target.split(".").at(-1)
      : target.split(/[\\/]/).at(-1).replace(/\.pyw?$/i, "");
    populateForm({ ...result.draft, name: currentName || fallbackName || "解析的命令" });
    setDirtyState(true, "已解析，尚未保存");
    elements.undoParse.classList.remove("hidden");
    const warning = result.warnings.length ? ` ${result.warnings.join(" ")}` : "";
    elements.parseStatus.textContent = `已按 ${result.detected_shell} 解析，共识别 ${result.draft.arguments.length} 个参数。${warning}`;
    renderProfiles();
  } catch (error) {
    elements.parseStatus.className = "inline-status error";
    elements.parseStatus.textContent = error.message;
    showToast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

function undoParsedCommand() {
  if (!state.parseSnapshot) return;
  const snapshot = state.parseSnapshot;
  state.currentId = snapshot.currentId;
  state.savedProfileName = snapshot.savedProfileName;
  state.savedStructure = snapshot.savedStructure;
  populateForm(snapshot.profile);
  if (snapshot.dirty) setDirtyState(true);
  else if (snapshot.currentId) markSaved();
  else setDirtyState(false, "新配置，尚未保存");
  state.parseSnapshot = null;
  elements.undoParse.classList.add("hidden");
  elements.parseStatus.textContent = "已撤销本次解析。";
  renderProfiles();
}

async function writeClipboard(text) {
  if (!text) throw new Error("当前没有可复制的命令");
  if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
  else {
    const area = document.createElement("textarea");
    area.value = text;
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
}

async function copyText(text) {
  await writeClipboard(text);
  showToast("已复制到剪贴板");
}

async function autoSaveNewProfileForCopy() {
  if (!elements.name.value.trim()) {
    elements.name.value = suggestedProfileName();
    markDirty();
  }
  const nameChanged = hasSavedNameChanged(elements.name.value.trim());
  if (state.currentId && !nameChanged) return "";
  await loadProfiles(false);
  if (findNameConflict(elements.name.value, null)) {
    return "存在同名配置，本次未自动保存";
  }
  try {
    const payload = readProfileForm();
    await persistProfile(payload, null);
    return nameChanged ? "已按新名称另存配置" : "新配置已自动保存";
  } catch (error) {
    if (error.status === 409) return "存在同名配置，本次未自动保存";
    throw error;
  }
}

async function copyCurrentCommand() {
  const button = elements.copyResult;
  button.disabled = true;
  try {
    await refreshPreview();
    if (!state.command) throw new Error(elements.previewError.textContent || "当前没有可复制的命令");
    const saveMessage = await autoSaveNewProfileForCopy();
    const profileName = elements.name.value.trim() || suggestedProfileName();
    const linkedProfileId = state.currentId && profileName === state.savedProfileName ? state.currentId : null;
    await writeClipboard(state.command);
    try {
      await api("/api/commands/record", {
        method: "POST",
        body: JSON.stringify({ profile_id: linkedProfileId, profile_name: profileName, draft: readDraft() }),
      });
    } catch (error) {
      throw new Error(`命令已复制，但记录历史失败：${error.message}`);
    }
    await loadHistory();
    showToast(saveMessage ? `已复制并记录；${saveMessage}` : "已复制并记录到历史");
  } finally {
    button.disabled = !state.command;
  }
}

async function loadHistory() {
  const query = encodeURIComponent(elements.historySearch.value.trim());
  const history = await api(`/api/history?q=${query}`);
  renderHistory(history);
}

function enableHistoryNoteAutoSave(input, item) {
  let savedValue = item.note || "";
  let saveTimer = null;
  let saveInFlight = false;
  let needsSave = false;

  const flush = async () => {
    clearTimeout(saveTimer);
    saveTimer = null;
    if (saveInFlight || !needsSave) return;
    const note = input.value;
    needsSave = false;
    if (note === savedValue) {
      input.classList.remove("saving", "save-error");
      input.title = "备注会自动保存";
      return;
    }

    saveInFlight = true;
    input.classList.add("saving");
    input.title = "正在保存备注";
    try {
      const saved = await api(`/api/history/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({ note }),
      });
      savedValue = saved.note;
      item.note = saved.note;
      input.classList.remove("save-error");
      if (input.value !== savedValue) needsSave = true;
      else {
        input.classList.remove("saving");
        input.title = "备注已自动保存";
      }
    } catch (error) {
      input.classList.remove("saving");
      input.classList.add("save-error");
      input.title = "备注保存失败，继续编辑可重试";
      handleError(new Error(`备注保存失败：${error.message}`));
    } finally {
      saveInFlight = false;
      if (needsSave) saveTimer = setTimeout(flush, 0);
    }
  };

  input.addEventListener("input", () => {
    needsSave = true;
    input.classList.remove("save-error");
    input.classList.add("saving");
    input.title = "备注将在停止输入后自动保存";
    clearTimeout(saveTimer);
    saveTimer = setTimeout(flush, 450);
  });
  input.addEventListener("change", () => {
    needsSave = true;
    flush();
  });
}

function renderHistory(history) {
  elements.historyList.replaceChildren();
  if (!history.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "暂无生成记录";
    elements.historyList.append(empty);
    return;
  }
  history.forEach((item) => {
    const card = document.createElement("article");
    card.className = "history-item";
    const meta = document.createElement("div");
    meta.className = "history-meta";
    const name = document.createElement("strong");
    name.textContent = item.profile_name;
    name.title = item.profile_name;
    const note = document.createElement("input");
    note.className = "history-note";
    note.type = "text";
    note.maxLength = 500;
    note.placeholder = "备注";
    note.value = item.note || "";
    note.title = "备注会自动保存";
    note.setAttribute("aria-label", `${item.profile_name} 的历史备注`);
    enableHistoryNoteAutoSave(note, item);
    const time = document.createElement("time");
    time.textContent = new Date(item.created_at).toLocaleString();
    meta.append(name, note, time);
    const command = document.createElement("div");
    command.className = "history-command";
    command.textContent = item.command;
    const actions = document.createElement("div");
    actions.className = "history-actions";
    const copy = document.createElement("button");
    copy.className = "button secondary";
    copy.textContent = "复制";
    copy.addEventListener("click", () => copyText(item.command).catch(handleError));
    const remove = document.createElement("button");
    remove.className = "button danger-quiet";
    remove.textContent = "删除";
    remove.addEventListener("click", async () => {
      try { await api(`/api/history/${item.id}`, { method: "DELETE" }); await loadHistory(); }
      catch (error) { handleError(error); }
    });
    actions.append(copy, remove);
    card.append(meta, command, actions);
    elements.historyList.append(card);
  });
}

function handleError(error) {
  console.error(error);
  showToast(error.message || "操作失败", true);
}

const HISTORY_WIDTH = { default: 280, min: 260 };

function historyWidthBounds() {
  const leftWidth = elements.profilePanel.classList.contains("collapsed") ? 52 : 220;
  const layoutStyle = getComputedStyle(elements.layout);
  const horizontalPadding = parseFloat(layoutStyle.paddingLeft) + parseFloat(layoutStyle.paddingRight);
  const columnGaps = parseFloat(layoutStyle.columnGap) * 2;
  const layoutWidth = elements.layout.clientWidth || document.documentElement.clientWidth;
  const flexibleWidth = layoutWidth - horizontalPadding - leftWidth - columnGaps;
  const workspaceMinimumLimit = flexibleWidth - 560;
  const equalColumnsLimit = Math.floor(flexibleWidth / 2);
  return { min: HISTORY_WIDTH.min, max: Math.max(HISTORY_WIDTH.min, Math.min(workspaceMinimumLimit, equalColumnsLimit)) };
}

function applyHistoryWidth(width, persist = false, remember = true) {
  const bounds = historyWidthBounds();
  const parsed = Number(width);
  const requested = Number.isFinite(parsed) ? parsed : HISTORY_WIDTH.default;
  if (remember) state.historyPreferredWidth = Math.min(bounds.max, Math.max(bounds.min, requested));
  const next = Math.min(bounds.max, Math.max(bounds.min, requested));
  state.historyWidth = Math.round(next);
  elements.layout.style.setProperty("--history-panel-width", `${state.historyWidth}px`);
  elements.historyResizer.setAttribute("aria-valuemin", String(bounds.min));
  elements.historyResizer.setAttribute("aria-valuemax", String(bounds.max));
  elements.historyResizer.setAttribute("aria-valuenow", String(state.historyWidth));
  elements.historyResizer.title = `历史栏宽度 ${state.historyWidth}px；向左拖动可拉宽，双击恢复默认宽度`;
  if (persist) {
    try { localStorage.setItem("command-builder-history-width", String(state.historyPreferredWidth)); } catch (_) { /* unavailable */ }
  }
}

function setSidebar(side, collapsed) {
  const panel = side === "left" ? elements.profilePanel : elements.historyPanel;
  const button = side === "left" ? $("#toggle-left") : $("#toggle-right");
  panel.classList.toggle("collapsed", collapsed);
  elements.layout.classList.toggle(`${side}-collapsed`, collapsed);
  button.setAttribute("aria-expanded", String(!collapsed));
  if (side === "left") button.textContent = collapsed ? "›" : "‹";
  else button.textContent = collapsed ? "‹" : "›";
  button.title = `${collapsed ? "展开" : "折叠"}${side === "left" ? "配置" : "历史"}栏`;
  try { localStorage.setItem(`command-builder-${side}-collapsed`, String(collapsed)); } catch (_) { /* unavailable */ }
  if (window.innerWidth >= 1280) applyHistoryWidth(state.historyPreferredWidth, false, false);
}

function restoreSidebars() {
  let left = false;
  let right = true;
  try {
    if (localStorage.getItem("command-builder-left-collapsed") !== null) left = localStorage.getItem("command-builder-left-collapsed") === "true";
    if (localStorage.getItem("command-builder-right-collapsed") !== null) right = localStorage.getItem("command-builder-right-collapsed") === "true";
    const savedWidth = Number(localStorage.getItem("command-builder-history-width"));
    if (Number.isFinite(savedWidth) && savedWidth > 0) state.historyPreferredWidth = savedWidth;
  } catch (_) { /* use defaults */ }
  setSidebar("left", left);
  setSidebar("right", right);
  applyHistoryWidth(state.historyPreferredWidth, false, false);
}

elements.argumentList.addEventListener("dragover", (event) => {
  if (!state.draggedCard) return;
  event.preventDefault();
  const target = event.target.closest(".argument-card");
  elements.argumentList.querySelectorAll(".drag-over").forEach((item) => item.classList.remove("drag-over"));
  if (!target || target === state.draggedCard) return;
  target.classList.add("drag-over");
  const before = event.clientY < target.getBoundingClientRect().top + target.offsetHeight / 2;
  elements.argumentList.insertBefore(state.draggedCard, before ? target : target.nextSibling);
});
elements.argumentList.addEventListener("drop", (event) => event.preventDefault());

$("#toggle-left").addEventListener("click", () => setSidebar("left", !elements.profilePanel.classList.contains("collapsed")));
$("#toggle-right").addEventListener("click", () => setSidebar("right", !elements.historyPanel.classList.contains("collapsed")));
elements.historyResizer.addEventListener("pointerdown", (event) => {
  if (event.button !== 0 || window.innerWidth < 1280 || elements.historyPanel.classList.contains("collapsed")) return;
  event.preventDefault();
  state.historyResize = { pointerId: event.pointerId, startX: event.clientX, startWidth: state.historyWidth };
  elements.historyResizer.setPointerCapture(event.pointerId);
  elements.historyResizer.classList.add("dragging");
  document.body.classList.add("resizing-history");
});
elements.historyResizer.addEventListener("pointermove", (event) => {
  if (!state.historyResize || event.pointerId !== state.historyResize.pointerId) return;
  applyHistoryWidth(state.historyResize.startWidth + state.historyResize.startX - event.clientX);
});
function finishHistoryResize(event) {
  if (!state.historyResize || event.pointerId !== state.historyResize.pointerId) return;
  state.historyResize = null;
  elements.historyResizer.classList.remove("dragging");
  document.body.classList.remove("resizing-history");
  applyHistoryWidth(state.historyWidth, true);
}
elements.historyResizer.addEventListener("pointerup", finishHistoryResize);
elements.historyResizer.addEventListener("pointercancel", finishHistoryResize);
elements.historyResizer.addEventListener("dblclick", () => applyHistoryWidth(HISTORY_WIDTH.default, true));
elements.historyResizer.addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const bounds = historyWidthBounds();
  if (event.key === "Home") applyHistoryWidth(bounds.min, true);
  else if (event.key === "End") applyHistoryWidth(bounds.max, true);
  else applyHistoryWidth(state.historyWidth + (event.key === "ArrowLeft" ? 20 : -20), true);
});
window.addEventListener("resize", () => applyHistoryWidth(state.historyPreferredWidth, false, false));
$("#new-profile").addEventListener("click", () => newProfile());
$("#add-argument").addEventListener("click", () => { addArgumentCard(makeArgument()); markDirty(); });
$("#save-profile").addEventListener("click", () => saveCurrentProfile().then((saved) => { if (saved) showToast("配置已保存"); }).catch(handleError));
$("#parse-command").addEventListener("click", () => parseExistingCommand().catch(handleError));
$("#undo-parse").addEventListener("click", undoParsedCommand);
$("#load-example").addEventListener("click", () => {
  elements.commandInput.value = "uv run python testbench.py --budget 20 --od-limit 200 --verbose";
  elements.commandInput.focus();
});
$("#clear-command-input").addEventListener("click", () => {
  elements.commandInput.value = "";
  elements.parseStatus.textContent = "";
  elements.commandInput.focus();
});
elements.copyResult.addEventListener("click", () => copyCurrentCommand().catch(handleError));

$("#duplicate-profile").addEventListener("click", async () => {
  try {
    const payload = readProfileForm();
    if (!payload.name || !payload.script_path) throw new Error("请先填写当前配置");
    payload.name = nextCopyName(payload.name);
    state.currentId = null;
    state.savedProfileName = null;
    state.savedStructure = null;
    populateForm(payload);
    elements.name.value = payload.name;
    const saved = await saveCurrentProfile();
    selectProfile(saved.id, true);
    showToast("已创建配置副本");
  } catch (error) { handleError(error); }
});

$("#delete-profile").addEventListener("click", async () => {
  if (!state.currentId) return showToast("当前配置尚未保存", true);
  if (!confirm("删除当前配置？已有历史命令仍会保留。")) return;
  try {
    await api(`/api/profiles/${state.currentId}`, { method: "DELETE" });
    state.currentId = null;
    state.savedProfileName = null;
    state.savedStructure = null;
    state.dirty = false;
    await loadProfiles();
    if (!state.profiles.length) newProfile(true);
    showToast("配置已删除");
  } catch (error) { handleError(error); }
});

$("#clear-history").addEventListener("click", async () => {
  if (!confirm("确定清空全部生成历史？此操作无法撤销。")) return;
  try { await api("/api/history", { method: "DELETE" }); await loadHistory(); showToast("历史已清空"); }
  catch (error) { handleError(error); }
});

elements.historySearch.addEventListener("input", () => {
  clearTimeout(state.historyTimer);
  state.historyTimer = setTimeout(() => loadHistory().catch(handleError), 220);
});

elements.importFile.addEventListener("change", async () => {
  const file = elements.importFile.files[0];
  if (!file) return;
  if (!confirmDiscard()) { elements.importFile.value = ""; return; }
  const mode = elements.importMode.value;
  if (mode === "replace" && !confirm("全部替换会删除本机现有配置和历史，确定继续？")) {
    elements.importFile.value = "";
    return;
  }
  try {
    const backup = JSON.parse(await file.text());
    const result = await api("/api/import", { method: "POST", body: JSON.stringify({ mode, backup }) });
    state.currentId = null;
    state.savedProfileName = null;
    state.savedStructure = null;
    state.dirty = false;
    await loadProfiles();
    await loadHistory();
    showToast(`已导入 ${result.profiles_imported} 个配置和 ${result.history_imported} 条历史`);
  } catch (error) { handleError(error); }
  finally { elements.importFile.value = ""; }
});

[elements.name, elements.scriptPath, elements.prefix, elements.shell, elements.invocationMode].forEach((input) => {
  input.addEventListener("input", markDirty);
  input.addEventListener("change", () => {
    if (input === elements.invocationMode) updateInvocationFields();
    markDirty();
  });
});

document.addEventListener("keydown", (event) => {
  if (event.isComposing || !(event.ctrlKey || event.metaKey)) return;
  if (event.key.toLowerCase() === "s") {
    event.preventDefault();
    saveCurrentProfile().then((saved) => { if (saved) showToast("配置已保存"); }).catch(handleError);
  } else if (event.key === "Enter") {
    event.preventDefault();
    copyCurrentCommand().catch(handleError);
  }
});

window.addEventListener("beforeunload", (event) => {
  if (!state.dirty) return;
  event.preventDefault();
  event.returnValue = "";
});

restoreSidebars();
Promise.all([loadProfiles(), loadHistory()])
  .then(() => { if (!state.profiles.length) newProfile(true); })
  .catch(handleError);
