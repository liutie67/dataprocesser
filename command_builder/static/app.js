const state = {
  profiles: [],
  currentId: null,
  command: "",
  historyTimer: null,
};

const $ = (selector) => document.querySelector(selector);
const elements = {
  profileList: $("#profile-list"),
  name: $("#profile-name"),
  scriptPath: $("#script-path"),
  prefix: $("#prefix"),
  shell: $("#shell"),
  argumentList: $("#argument-list"),
  saveState: $("#save-state"),
  result: $("#command-result code"),
  copyResult: $("#copy-result"),
  historyList: $("#history-list"),
  historySearch: $("#history-search"),
  importFile: $("#import-file"),
  importMode: $("#import-mode"),
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
    throw new Error(detail);
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

function markDirty() {
  elements.saveState.textContent = "有未保存修改";
  elements.saveState.className = "save-state";
}

function markSaved() {
  elements.saveState.textContent = "已保存";
  elements.saveState.className = "save-state saved";
}

function emptyProfile() {
  return { name: "", script_path: "", prefix: "python", shell: "powershell", arguments: [] };
}

function makeArgument() {
  return {
    id: crypto.randomUUID(),
    position: elements.argumentList.children.length,
    mode: "named",
    token: "--参数",
    value_type: "str",
    value: "",
    choices: [],
    enabled: true,
  };
}

function setProfileForm(profile) {
  elements.name.value = profile.name || "";
  elements.scriptPath.value = profile.script_path || "";
  elements.prefix.value = profile.prefix || "python";
  elements.shell.value = profile.shell || "powershell";
  elements.argumentList.replaceChildren();
  (profile.arguments || []).sort((a, b) => a.position - b.position).forEach(addArgumentCard);
  if (!profile.arguments?.length) renderArgumentEmptyState();
  state.command = "";
  elements.result.textContent = "配置完成后点击“生成命令”";
  elements.copyResult.disabled = true;
  markSaved();
}

function renderArgumentEmptyState() {
  if (!elements.argumentList.children.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state argument-empty";
    empty.textContent = "还没有参数。点击“添加参数”开始配置。";
    elements.argumentList.append(empty);
  }
}

function clearArgumentEmptyState() {
  elements.argumentList.querySelector(".argument-empty")?.remove();
}

function addArgumentCard(argument) {
  clearArgumentEmptyState();
  const card = document.createElement("div");
  card.className = `argument-card${argument.enabled ? "" : " disabled"}`;
  card.dataset.id = argument.id || crypto.randomUUID();
  card.innerHTML = `
    <label class="check-label"><input class="arg-enabled" type="checkbox"><span>启用</span></label>
    <label><span>模式</span><select class="arg-mode"><option value="named">命名参数</option><option value="positional">位置参数</option></select></label>
    <label><span>类型</span><select class="arg-type"><option value="str">str</option><option value="path">Path</option><option value="int">int</option><option value="float">float</option><option value="choice">choices</option><option value="bool">bool 开关</option></select></label>
    <label class="token-field"><span>参数标记</span><input class="arg-token" maxlength="128" placeholder="--budget"></label>
    <label class="value-field"><span>当前值</span><span class="value-slot"></span></label>
    <label class="choices-field hidden"><span>候选值（逗号或换行分隔）</span><input class="arg-choices" placeholder="small, medium, large"></label>
    <div class="argument-tools"><button class="mini-button move-up" title="上移">↑</button><button class="mini-button move-down" title="下移">↓</button><button class="mini-button delete" title="删除">×</button></div>
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
    updateArgumentCard(card); markDirty();
  });
  card.querySelector(".arg-type").addEventListener("change", () => { renderValueControl(card, ""); updateArgumentCard(card); markDirty(); });
  card.querySelector(".arg-choices").addEventListener("input", () => { renderValueControl(card, ""); markDirty(); });
  card.querySelector(".arg-token").addEventListener("input", markDirty);
  card.querySelector(".delete").addEventListener("click", () => { card.remove(); renderArgumentEmptyState(); markDirty(); });
  card.querySelector(".move-up").addEventListener("click", () => {
    const previous = card.previousElementSibling;
    if (previous) elements.argumentList.insertBefore(card, previous);
    markDirty();
  });
  card.querySelector(".move-down").addEventListener("click", () => {
    const next = card.nextElementSibling;
    if (next) elements.argumentList.insertBefore(next, card);
    markDirty();
  });
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
    if (type === "float") control.step = "any";
    control.placeholder = type === "path" ? "路径或文件名" : "参数值";
    control.value = value ?? "";
  }
  control.className = "arg-value";
  control.addEventListener("input", markDirty);
  control.addEventListener("change", markDirty);
  slot.append(control);
}

function updateArgumentCard(card) {
  const enabled = card.querySelector(".arg-enabled").checked;
  const mode = card.querySelector(".arg-mode").value;
  const type = card.querySelector(".arg-type").value;
  card.classList.toggle("disabled", !enabled);
  card.querySelector(".token-field").classList.toggle("hidden", mode === "positional");
  card.querySelector(".choices-field").classList.toggle("hidden", type !== "choice");
  card.querySelector(".value-field").classList.toggle("hidden", type === "bool");
  [...card.querySelector(".arg-type").options].forEach((option) => {
    if (option.value === "bool") option.disabled = mode === "positional";
  });
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

function readProfileForm() {
  return {
    name: elements.name.value.trim(),
    script_path: elements.scriptPath.value.trim(),
    prefix: elements.prefix.value,
    shell: elements.shell.value,
    arguments: readArguments(),
  };
}

async function saveCurrentProfile() {
  const payload = readProfileForm();
  if (!payload.name) throw new Error("请填写配置名称");
  if (!payload.script_path) throw new Error("请填写 Python 文件路径");
  const method = state.currentId ? "PUT" : "POST";
  const path = state.currentId ? `/api/profiles/${state.currentId}` : "/api/profiles";
  const saved = await api(path, { method, body: JSON.stringify(payload) });
  state.currentId = saved.id;
  await loadProfiles(false);
  markSaved();
  return saved;
}

async function loadProfiles(selectFirst = true) {
  state.profiles = await api("/api/profiles");
  renderProfiles();
  if (selectFirst && !state.currentId && state.profiles.length) selectProfile(state.profiles[0].id);
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
    path.textContent = profile.script_path;
    button.append(name, path);
    button.addEventListener("click", () => selectProfile(profile.id));
    elements.profileList.append(button);
  });
}

function selectProfile(profileId) {
  const profile = state.profiles.find((item) => item.id === profileId);
  if (!profile) return;
  state.currentId = profile.id;
  setProfileForm(profile);
  renderProfiles();
}

function newProfile() {
  state.currentId = null;
  setProfileForm(emptyProfile());
  elements.saveState.textContent = "新配置，尚未保存";
  elements.saveState.className = "save-state";
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

async function generateCommand() {
  const saved = await saveCurrentProfile();
  const result = await api(`/api/profiles/${saved.id}/generate`, { method: "POST" });
  state.command = result.command;
  elements.result.textContent = result.command;
  elements.copyResult.disabled = false;
  await loadHistory();
  showToast("命令已生成并写入历史");
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
  else {
    const area = document.createElement("textarea");
    area.value = text;
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  showToast("已复制到剪贴板");
}

async function loadHistory() {
  const query = encodeURIComponent(elements.historySearch.value.trim());
  const history = await api(`/api/history?q=${query}`);
  renderHistory(history);
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
    const time = document.createElement("time");
    time.textContent = new Date(item.created_at).toLocaleString();
    meta.append(name, time);
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

$("#new-profile").addEventListener("click", newProfile);
$("#add-argument").addEventListener("click", () => { addArgumentCard(makeArgument()); markDirty(); });
$("#save-profile").addEventListener("click", () => saveCurrentProfile().then(() => showToast("配置已保存")).catch(handleError));
$("#generate-command").addEventListener("click", () => generateCommand().catch(handleError));
elements.copyResult.addEventListener("click", () => copyText(state.command).catch(handleError));

$("#duplicate-profile").addEventListener("click", async () => {
  try {
    const payload = readProfileForm();
    if (!payload.name || !payload.script_path) throw new Error("请先填写并保存当前配置");
    payload.name = nextCopyName(payload.name);
    state.currentId = null;
    setProfileForm(payload);
    elements.name.value = payload.name;
    const saved = await saveCurrentProfile();
    selectProfile(saved.id);
    showToast("已创建配置副本");
  } catch (error) { handleError(error); }
});

$("#delete-profile").addEventListener("click", async () => {
  if (!state.currentId) return showToast("当前配置尚未保存", true);
  if (!confirm("删除当前配置？已有历史命令仍会保留。")) return;
  try {
    await api(`/api/profiles/${state.currentId}`, { method: "DELETE" });
    state.currentId = null;
    await loadProfiles();
    if (!state.profiles.length) newProfile();
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
  const mode = elements.importMode.value;
  if (mode === "replace" && !confirm("全部替换会删除本机现有配置和历史，确定继续？")) {
    elements.importFile.value = "";
    return;
  }
  try {
    const backup = JSON.parse(await file.text());
    const result = await api("/api/import", { method: "POST", body: JSON.stringify({ mode, backup }) });
    state.currentId = null;
    await loadProfiles();
    await loadHistory();
    showToast(`已导入 ${result.profiles_imported} 个配置和 ${result.history_imported} 条历史`);
  } catch (error) { handleError(error); }
  finally { elements.importFile.value = ""; }
});

[elements.name, elements.scriptPath, elements.prefix, elements.shell].forEach((input) => {
  input.addEventListener("input", markDirty);
  input.addEventListener("change", markDirty);
});

Promise.all([loadProfiles(), loadHistory()])
  .then(() => { if (!state.profiles.length) newProfile(); })
  .catch(handleError);
