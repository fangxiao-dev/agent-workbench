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
const flowLayout = document.querySelector("#flow-layout");
const flowCanvas = document.querySelector("#flow-canvas");
const flowStages = document.querySelector("#flow-stages");
const dependencyLines = document.querySelector("#dependency-lines");
const ticketTooltip = document.querySelector("#ticket-tooltip");
const tooltipCode = document.querySelector("#tooltip-code");
const tooltipName = document.querySelector("#tooltip-name");
const tooltipState = document.querySelector("#tooltip-state");
const tooltipDependencies = document.querySelector("#tooltip-dependencies");
const tooltipHints = document.querySelector("#tooltip-hints");
const ticketEmpty = document.querySelector("#ticket-empty");
const auditList = document.querySelector("#audit-list");

let events = null;
let selectedTask = null;
let selectedTicketId = null;
let currentTickets = [];
let ticketSignature = "";

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
  items.slice(0, 5).forEach((item, index) => {
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

function ticketDepth(ticket, byId, cache, visiting = new Set()) {
  if (cache.has(ticket.id)) return cache.get(ticket.id);
  if (visiting.has(ticket.id)) return 0;
  visiting.add(ticket.id);
  const parents = ticket.dependencies.map((id) => byId.get(id)).filter(Boolean);
  const depth = parents.length
    ? 1 + Math.max(...parents.map((parent) => ticketDepth(parent, byId, cache, visiting)))
    : 0;
  visiting.delete(ticket.id);
  cache.set(ticket.id, depth);
  return depth;
}

function stageLabel(depth, maxDepth) {
  if (depth === 0) return "流程起点";
  if (depth === maxDepth) return "最终收口";
  return `阶段 ${depth + 1}`;
}

function drawDependencyLines() {
  clear(dependencyLines);
  if (!currentTickets.length) return;
  const canvasRect = flowCanvas.getBoundingClientRect();
  dependencyLines.setAttribute("viewBox", `0 0 ${canvasRect.width} ${canvasRect.height}`);
  dependencyLines.setAttribute("width", String(canvasRect.width));
  dependencyLines.setAttribute("height", String(canvasRect.height));

  const namespace = "http://www.w3.org/2000/svg";
  const definitions = document.createElementNS(namespace, "defs");
  const marker = document.createElementNS(namespace, "marker");
  marker.setAttribute("id", "flow-arrow");
  marker.setAttribute("viewBox", "0 0 10 10");
  marker.setAttribute("refX", "8");
  marker.setAttribute("refY", "5");
  marker.setAttribute("markerWidth", "6");
  marker.setAttribute("markerHeight", "6");
  marker.setAttribute("orient", "auto-start-reverse");
  const arrow = document.createElementNS(namespace, "path");
  arrow.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
  marker.append(arrow);
  definitions.append(marker);
  dependencyLines.append(definitions);

  currentTickets.forEach((ticket) => {
    const target = flowStages.querySelector(`[data-ticket-id="${ticket.id}"]`);
    if (!target) return;
    ticket.dependencies.forEach((dependencyId) => {
      const source = flowStages.querySelector(`[data-ticket-id="${dependencyId}"]`);
      if (!source) return;
      const from = source.getBoundingClientRect();
      const to = target.getBoundingClientRect();
      const x1 = from.left + from.width / 2 - canvasRect.left;
      const y1 = from.bottom - canvasRect.top;
      const x2 = to.left + to.width / 2 - canvasRect.left;
      const y2 = to.top - canvasRect.top;
      const bend = Math.max(24, (y2 - y1) * 0.48);
      const path = document.createElementNS(namespace, "path");
      path.setAttribute("d", `M ${x1} ${y1} C ${x1} ${y1 + bend}, ${x2} ${y2 - bend}, ${x2} ${y2}`);
      path.setAttribute("marker-end", "url(#flow-arrow)");
      path.classList.add("dependency-edge");
      if (ticket.id === selectedTicketId || dependencyId === selectedTicketId) {
        path.classList.add("is-related");
      }
      dependencyLines.append(path);
    });
  });
}

function selectTicket(ticketId) {
  selectedTicketId = ticketId;
  const selected = currentTickets.find((ticket) => ticket.id === ticketId);
  if (!selected) return;
  const dependents = currentTickets.filter((ticket) => ticket.dependencies.includes(ticketId));
  const related = new Set([...selected.dependencies, ...dependents.map((ticket) => ticket.id), ticketId]);
  flowStages.querySelectorAll(".flow-node").forEach((node) => {
    const active = node.dataset.ticketId === ticketId;
    node.setAttribute("aria-pressed", String(active));
    node.classList.toggle("is-dimmed", !related.has(node.dataset.ticketId));
  });

  requestAnimationFrame(drawDependencyLines);
}

function ticketRelationship(ticket) {
  const dependents = currentTickets.filter((item) => item.dependencies.includes(ticket.id));
  const parentNames = ticket.dependencies.map((id) => currentTickets.find((item) => item.id === id)?.name || id);
  const childNames = dependents.map((item) => item.name);
  const relationship = [];
  relationship.push(parentNames.length ? `需要先完成：${parentNames.join("、")}` : "这是当前流程的起点");
  if (childNames.length) relationship.push(`完成后释放：${childNames.join("、")}`);
  return relationship.join("。") + "。";
}

function showTicketTooltip(ticket, anchor) {
  tooltipCode.textContent = ticket.id;
  tooltipName.textContent = ticket.name;
  tooltipState.className = `state-badge ${ticket.state.toLowerCase()}`;
  tooltipState.textContent = stateLabel(ticket.state);
  tooltipDependencies.textContent = ticketRelationship(ticket);
  clear(tooltipHints);
  const hints = ticket.completionHints.length
    ? ticket.completionHints
    : ["完成条件以该事项的正式验收记录为准。"];
  hints.forEach((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    tooltipHints.append(item);
  });

  ticketTooltip.hidden = false;
  ticketTooltip.style.visibility = "hidden";
  const anchorRect = anchor.getBoundingClientRect();
  const tooltipRect = ticketTooltip.getBoundingClientRect();
  let left = anchorRect.right + 12;
  if (left + tooltipRect.width > window.innerWidth - 12) {
    left = anchorRect.left - tooltipRect.width - 12;
  }
  left = Math.max(12, Math.min(left, window.innerWidth - tooltipRect.width - 12));
  const top = Math.max(
    12,
    Math.min(anchorRect.top + anchorRect.height / 2 - tooltipRect.height / 2, window.innerHeight - tooltipRect.height - 12),
  );
  ticketTooltip.style.left = `${left}px`;
  ticketTooltip.style.top = `${top}px`;
  ticketTooltip.style.visibility = "visible";
}

function hideTicketTooltip() {
  ticketTooltip.hidden = true;
}

function activateTicket(ticket, node) {
  showTicketTooltip(ticket, node);
}

function populateTooltipEvents(ticket, node) {
  node.setAttribute("aria-describedby", "ticket-tooltip");
  node.addEventListener("mouseenter", () => activateTicket(ticket, node));
  node.addEventListener("mouseleave", hideTicketTooltip);
  node.addEventListener("focus", () => activateTicket(ticket, node));
  node.addEventListener("blur", hideTicketTooltip);
  node.addEventListener("click", () => activateTicket(ticket, node));
}

function renderTickets(tickets, currentTicketId) {
  const nextSignature = JSON.stringify({ tickets, currentTicketId });
  if (nextSignature === ticketSignature) return;
  ticketSignature = nextSignature;
  currentTickets = tickets;
  clear(flowStages);
  clear(dependencyLines);
  ticketEmpty.hidden = tickets.length > 0;
  flowLayout.hidden = tickets.length === 0;
  if (!tickets.length) {
    selectedTicketId = null;
    hideTicketTooltip();
    return;
  }

  const byId = new Map(tickets.map((ticket) => [ticket.id, ticket]));
  const depths = new Map();
  tickets.forEach((ticket) => ticketDepth(ticket, byId, depths));
  const maxDepth = Math.max(...depths.values());
  flowCanvas.style.minWidth = "0";
  flowCanvas.style.minHeight = `${Math.max(660, (maxDepth + 1) * 108)}px`;
  flowStages.style.gridTemplateColumns = "1fr";
  flowStages.style.gridTemplateRows = `repeat(${maxDepth + 1}, minmax(86px, auto))`;

  for (let depth = 0; depth <= maxDepth; depth += 1) {
    const stage = document.createElement("section");
    stage.className = "flow-stage";
    const stageTickets = tickets.filter((ticket) => depths.get(ticket.id) === depth);
    stage.style.setProperty("--node-count", String(stageTickets.length));
    const label = document.createElement("h3");
    label.textContent = stageLabel(depth, maxDepth);
    stage.append(label);
    stageTickets.forEach((ticket) => {
      const node = document.createElement("button");
      node.type = "button";
      node.className = `flow-node ${ticket.state.toLowerCase()}`;
      node.dataset.ticketId = ticket.id;
      node.setAttribute("aria-pressed", "false");
      node.setAttribute("aria-label", `${ticket.name}，${stateLabel(ticket.state)}`);
      const code = document.createElement("span");
      code.className = "flow-node-code";
      code.textContent = ticket.id;
      const title = document.createElement("span");
      title.className = "flow-node-title";
      title.textContent = ticket.name;
      node.append(code, title);
      populateTooltipEvents(ticket, node);
      stage.append(node);
    });
    flowStages.append(stage);
  }

  const initial = tickets.find((ticket) => ticket.id === currentTicketId)
    || tickets.find((ticket) => ticket.state !== "SATISFIED")
    || tickets[0];
  requestAnimationFrame(() => selectTicket(initial.id));
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
  renderTickets(pkg?.tickets || [], pkg?.currentTicketId || null);

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

window.addEventListener("resize", () => {
  hideTicketTooltip();
  requestAnimationFrame(drawDependencyLines);
});
window.addEventListener("scroll", hideTicketTooltip, true);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") hideTicketTooltip();
});
