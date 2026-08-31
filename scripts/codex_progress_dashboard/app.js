"use strict";

const taskSelect = document.querySelector("#task-select");
const packageSelect = document.querySelector("#package-select");
const connection = document.querySelector("#connection");
const connectionLabel = document.querySelector("#connection-label");
const taskTitle = document.querySelector("#task-title");
const taskStatus = document.querySelector("#task-status");
const formalSummary = document.querySelector("#formal-summary");
const gateLabel = document.querySelector("#gate-label");
const actualSummary = document.querySelector("#actual-summary");
const activityList = document.querySelector("#activity-list");
const freshness = document.querySelector("#freshness");
const nextAction = document.querySelector("#next-action");
const blocker = document.querySelector("#blocker");
const divergencePanel = document.querySelector("#divergence-panel");
const divergence = document.querySelector("#divergence");
const ticketList = document.querySelector("#ticket-list");
const ticketEmpty = document.querySelector("#ticket-empty");
const auditList = document.querySelector("#audit-list");

let events = null;
let selectedTask = null;

function clear(node) {
  while (node.firstChild) node.firstChild.remove();
}

function option(value, label) {
  const node = document.createElement("option");
  node.value = value;
  node.textContent = label;
  return node;
}

function setConnection(state, label) {
  connection.classList.toggle("live", state === "live");
  connection.classList.toggle("error", state === "error");
  connectionLabel.textContent = label;
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "时间未知";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

function stateLabel(value) {
  return {
    SATISFIED: "已正式验收",
    PENDING: "等待推进",
    BLOCKED: "当前受阻",
    "NEEDS-REVALIDATION": "需要重新验证",
    RETIRED: "已退出当前范围",
  }[value] || value;
}

function renderActivities(items) {
  clear(activityList);
  if (!items.length) {
    const row = document.createElement("li");
    row.className = "activity-item";
    row.textContent = "尚未观察到用户可见进展。";
    activityList.append(row);
    return;
  }
  items.forEach((item, index) => {
    const row = document.createElement("li");
    row.className = "activity-item";
    const time = document.createElement("time");
    time.className = "activity-time";
    time.dateTime = item.timestamp;
    time.textContent = index === 0 ? `最新 · ${formatTime(item.timestamp)}` : formatTime(item.timestamp);
    const text = document.createElement("p");
    text.className = "activity-text";
    text.textContent = item.text;
    row.append(time, text);
    activityList.append(row);
  });
}

function renderTickets(tickets) {
  clear(ticketList);
  ticketEmpty.hidden = tickets.length > 0;
  tickets.forEach((ticket) => {
    const row = document.createElement("div");
    row.className = "ticket-row";
    const name = document.createElement("div");
    name.className = "ticket-name";
    const strong = document.createElement("strong");
    strong.textContent = ticket.name;
    const id = document.createElement("small");
    id.textContent = `技术标识 · ${ticket.id}`;
    name.append(strong, id);

    const state = document.createElement("span");
    state.className = `state-badge ${ticket.state.toLowerCase()}`;
    state.textContent = stateLabel(ticket.state);

    const hint = document.createElement("p");
    hint.className = "completion-hint";
    hint.textContent = ticket.completionHints.length
      ? `完成条件：${ticket.completionHints.join("；")}`
      : "完成条件以该事项的正式验收记录为准。";
    row.append(name, state, hint);
    ticketList.append(row);
  });
}

function appendAudit(label, value) {
  if (value === null || value === undefined || value === "") return;
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = String(value);
  auditList.append(term, description);
}

function render(snapshot) {
  taskTitle.textContent = snapshot.task.name;
  taskStatus.textContent = snapshot.task.status;
  actualSummary.textContent = snapshot.actualProgress.summary;
  renderActivities(snapshot.actualProgress.activities);
  freshness.textContent = `页面更新 · ${formatTime(new Date().toISOString())}`;

  const pkg = snapshot.package;
  formalSummary.textContent = pkg ? pkg.formalSummary : "尚未关联";
  gateLabel.textContent = pkg ? pkg.gateLabel : "尚未关联";
  nextAction.textContent = pkg ? pkg.nextAction : "关联实施包后显示正式登记的下一动作。";
  blocker.hidden = !pkg?.blocker;
  blocker.textContent = pkg?.blocker ? `当前阻塞：${pkg.blocker}` : "";
  divergencePanel.hidden = !pkg?.discrepancy;
  divergence.textContent = pkg?.discrepancy || "";
  renderTickets(pkg?.tickets || []);

  clear(auditList);
  appendAudit("任务标识", snapshot.audit.taskId);
  appendAudit("工作目录", snapshot.audit.workspace);
  appendAudit("本地分支", snapshot.audit.branch);
  appendAudit("版本锚点", snapshot.audit.revision);
  appendAudit("已读取记录位置", snapshot.audit.rolloutOffset);
  appendAudit("实施包格式", pkg?.audit?.formatVersion);
  appendAudit("当前尝试", pkg?.audit?.attempt);
  appendAudit("正式状态更新时间", pkg?.audit?.stateModifiedAt);
}

async function getJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `请求失败：${response.status}`);
  return payload;
}

function packageStorageKey(taskId) {
  return `codex-progress-package:${taskId}`;
}

async function loadPackages(taskId) {
  packageSelect.disabled = true;
  clear(packageSelect);
  packageSelect.append(option("", "正在查找实施包…"));
  const { packages } = await getJson(`/api/tasks/${encodeURIComponent(taskId)}/packages`);
  clear(packageSelect);
  packageSelect.append(option("", packages.length ? "不关联实施包" : "没有发现实施包"));
  packages.forEach((item) => packageSelect.append(option(item.path, item.name)));

  const requested = new URLSearchParams(window.location.search).get("package");
  const saved = localStorage.getItem(packageStorageKey(taskId));
  const referenced = packages.filter((item) => item.referenced);
  const candidate = packages.find((item) => item.path === requested)
    || packages.find((item) => item.path === saved)
    || (referenced.length === 1 ? referenced[0] : null)
    || (packages.length === 1 ? packages[0] : null);
  packageSelect.value = candidate?.path || "";
  packageSelect.disabled = packages.length === 0;
}

function openEvents() {
  if (events) events.close();
  const packagePath = packageSelect.value;
  const query = packagePath ? `?package=${encodeURIComponent(packagePath)}` : "";
  setConnection("loading", "正在连接");
  events = new EventSource(`/api/tasks/${encodeURIComponent(selectedTask)}/events${query}`);
  events.addEventListener("snapshot", (event) => {
    render(JSON.parse(event.data));
    setConnection("live", "实时连接");
  });
  events.onerror = () => setConnection("error", "正在重连");
}

async function selectTask(taskId) {
  selectedTask = taskId;
  localStorage.setItem("codex-progress-task", taskId);
  await loadPackages(taskId);
  openEvents();
}

taskSelect.addEventListener("change", () => {
  selectTask(taskSelect.value).catch(showError);
});

packageSelect.addEventListener("change", () => {
  localStorage.setItem(packageStorageKey(selectedTask), packageSelect.value);
  openEvents();
});

function showError(error) {
  setConnection("error", "读取失败");
  actualSummary.textContent = error instanceof Error ? error.message : String(error);
}

async function boot() {
  const { tasks } = await getJson("/api/tasks");
  clear(taskSelect);
  if (!tasks.length) throw new Error("没有可读取的本地 Codex 任务。");
  tasks.forEach((task) => taskSelect.append(option(task.id, task.name)));
  const requested = new URLSearchParams(window.location.search).get("task");
  const saved = localStorage.getItem("codex-progress-task");
  const initial = tasks.find((task) => task.id === requested)
    || tasks.find((task) => task.id === saved)
    || tasks[0];
  taskSelect.value = initial.id;
  await selectTask(initial.id);
}

boot().catch(showError);
