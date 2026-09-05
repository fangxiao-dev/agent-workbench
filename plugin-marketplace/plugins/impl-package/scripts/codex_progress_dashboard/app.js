"use strict";

const packageSelect = document.querySelector("#package-select");
const taskReadout = document.querySelector("#task-readout");
const connection = document.querySelector("#connection");
const connectionLabel = document.querySelector("#connection-label");
const taskTitle = document.querySelector("#task-title");
const taskStatus = document.querySelector("#task-status");
const formalSummary = document.querySelector("#formal-summary");
const gateLabel = document.querySelector("#gate-label");
const actualSummary = document.querySelector("#actual-summary");
const activityList = document.querySelector("#activity-list");
const freshness = document.querySelector("#freshness");
const flowLayout = document.querySelector("#flow-layout");
const flowCanvas = document.querySelector("#flow-canvas");
const flowStages = document.querySelector("#flow-stages");
const dependencyLines = document.querySelector("#dependency-lines");
const ticketTooltip = document.querySelector("#ticket-tooltip");
const tooltipCode = document.querySelector("#tooltip-code");
const tooltipName = document.querySelector("#tooltip-name");
const tooltipState = document.querySelector("#tooltip-state");
const tooltipActive = document.querySelector("#tooltip-active");
const tooltipActiveList = document.querySelector("#tooltip-active-list");
const tooltipResult = document.querySelector("#tooltip-result");
const tooltipResultTime = document.querySelector("#tooltip-result-time");
const tooltipResultSummary = document.querySelector("#tooltip-result-summary");
const tooltipHints = document.querySelector("#tooltip-hints");
const ticketEmpty = document.querySelector("#ticket-empty");
const monitorPanel = document.querySelector("#monitor-panel");
const monitorTime = document.querySelector("#monitor-time");
const monitorLevel = document.querySelector("#monitor-level");
const monitorSummary = document.querySelector("#monitor-summary");
const monitorEvaluation = document.querySelector("#monitor-evaluation");
const monitorProgress = document.querySelector("#monitor-progress");
const monitorImprovementsRow = document.querySelector("#monitor-improvements-row");
const monitorImprovements = document.querySelector("#monitor-improvements");
const monitorNext = document.querySelector("#monitor-next");
const monitorOwnerRow = document.querySelector("#monitor-owner-row");
const monitorOwner = document.querySelector("#monitor-owner");
const monitorThread = document.querySelector("#monitor-thread");
const monitorObservations = document.querySelector("#monitor-observations");
const monitorObservationCount = document.querySelector("#monitor-observation-count");
const monitorObservationDialog = document.querySelector("#monitor-observation-dialog");
const monitorObservationDialogCount = document.querySelector("#monitor-observation-dialog-count");
const monitorObservationClose = document.querySelector("#monitor-observation-close");
const monitorObservationList = document.querySelector("#monitor-observation-list");
const observationFilterButtons = [...document.querySelectorAll("[data-observation-filter]")];
const observationFilterAllCount = document.querySelector("#observation-filter-all-count");
const observationFilterPatternCount = document.querySelector("#observation-filter-pattern-count");
const observationFilterSpecificCount = document.querySelector("#observation-filter-specific-count");
const reviewStatsUnique = document.querySelector("#review-stats-unique");
const reviewStatsClosed = document.querySelector("#review-stats-closed");
const reviewChart = document.querySelector("#review-chart");
const reviewBar = document.querySelector("#review-bar");
const reviewBarDetail = document.querySelector("#review-bar-detail");
const auditList = document.querySelector("#audit-list");

let events = null;
let selectedTask = null;
let selectedPackage = null;
let packageGroups = [];
let selectedTicketId = null;
let previewTicketId = null;
let currentTickets = [];
let ticketSignature = "";
let currentObservations = [];
let pendingObservations = null;
let observationSignature = "";
let editingObservationId = null;
let observationFilter = "all";

function clear(node) {
  while (node.firstChild) node.firstChild.remove();
}

function closeObservationDialog() {
  cancelObservationEdit();
  if (monitorObservationDialog.open) monitorObservationDialog.close();
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

function formatCompactTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "时间未知";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function stateLabel(value, runtimeState = null) {
  if (runtimeState === "DEVELOPING") return "开发中";
  if (runtimeState === "INVESTIGATING") return "调研中";
  if (runtimeState === "READY") return "可启动";
  return {
    SATISFIED: "已验收",
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

  const highlightedTicketIds = new Set(
    previewTicketId
      ? [previewTicketId]
      : currentTickets.filter((ticket) => ticket.runtimeState === "DEVELOPING").map((ticket) => ticket.id),
  );

  const edges = [];
  currentTickets.forEach((ticket) => {
    const target = flowStages.querySelector(`[data-ticket-id="${ticket.id}"]`);
    if (!target) return;
    ticket.dependencies.forEach((dependencyId) => {
      const source = flowStages.querySelector(`[data-ticket-id="${dependencyId}"]`);
      if (!source) return;
      const isRelated = highlightedTicketIds.has(ticket.id) || highlightedTicketIds.has(dependencyId);
      edges.push({ source, target, isRelated });
    });
  });
  // Draw unrelated edges first so the highlighted (related) ones always paint on top.
  [...edges.filter((edge) => !edge.isRelated), ...edges.filter((edge) => edge.isRelated)].forEach(({ source, target, isRelated }) => {
    const from = source.getBoundingClientRect();
    const to = target.getBoundingClientRect();
    const x1 = from.left + from.width / 2 - canvasRect.left;
    const y1 = from.bottom - canvasRect.top;
    const x2 = to.left + to.width / 2 - canvasRect.left;
    const y2 = to.top - canvasRect.top;
    const bend = Math.max(18, (y2 - y1) * 0.4);
    const path = document.createElementNS(namespace, "path");
    path.setAttribute("d", `M ${x1} ${y1} C ${x1} ${y1 + bend}, ${x2} ${y2 - bend}, ${x2} ${y2}`);
    path.setAttribute("marker-end", "url(#flow-arrow)");
    path.classList.add("dependency-edge");
    if (isRelated) path.classList.add("is-related");
    dependencyLines.append(path);
  });
}

function directRelations(ticketId) {
  const ticket = currentTickets.find((item) => item.id === ticketId);
  if (!ticket) return new Set();
  const dependents = currentTickets.filter((item) => item.dependencies.includes(ticketId));
  return new Set([...ticket.dependencies, ...dependents.map((item) => item.id), ticketId]);
}

function updateTicketHighlights() {
  const highlighted = new Set();
  const focusTicketIds = previewTicketId
    ? [previewTicketId]
    : currentTickets.filter((ticket) => ticket.runtimeState === "DEVELOPING").map((ticket) => ticket.id);
  focusTicketIds.forEach((ticketId) => directRelations(ticketId).forEach((relatedId) => highlighted.add(relatedId)));
  const visible = new Set(highlighted);
  currentTickets
    .filter((ticket) => ["READY", "DEVELOPING", "INVESTIGATING"].includes(ticket.runtimeState))
    .forEach((ticket) => visible.add(ticket.id));
  flowStages.querySelectorAll(".flow-node").forEach((node) => {
    const ticketId = node.dataset.ticketId;
    const ticket = currentTickets.find((item) => item.id === ticketId);
    node.setAttribute(
      "aria-pressed",
      String(ticketId === selectedTicketId && ticket?.runtimeState === "DEVELOPING"),
    );
    node.classList.toggle("is-preview", ticketId === previewTicketId);
    node.classList.toggle(
      "is-linked-preview",
      Boolean(previewTicketId && ticketId !== previewTicketId && highlighted.has(ticketId)),
    );
    node.classList.toggle("is-dimmed", !visible.has(ticketId));
  });
  requestAnimationFrame(drawDependencyLines);
}

function selectTicket(ticketId) {
  selectedTicketId = ticketId;
  previewTicketId = null;
  updateTicketHighlights();
}

function previewTicket(ticketId) {
  previewTicketId = ticketId;
  updateTicketHighlights();
}

function clearTicketPreview() {
  if (!previewTicketId) return;
  previewTicketId = null;
  updateTicketHighlights();
}

function trailOutcomeLabel(outcome) {
  return {
    RUNNING: "进行中",
    DONE: "已返回",
    INCOMPLETE: "未完成",
    EVIDENCE_GAP: "证据不足",
    BLOCKED: "已阻塞",
    PASS: "已通过",
    FAIL: "未通过",
  }[String(outcome).toUpperCase()] || outcome || "状态未知";
}

function showTicketTooltip(ticket, anchor) {
  tooltipCode.textContent = ticket.id;
  tooltipName.textContent = ticket.name;
  tooltipState.className = `state-badge ${(ticket.runtimeState || ticket.state).toLowerCase()}`;
  tooltipState.textContent = stateLabel(ticket.state, ticket.runtimeState);
  clear(tooltipActiveList);
  const activeActions = Array.isArray(ticket.activeActions) ? ticket.activeActions : [];
  tooltipActive.hidden = !activeActions.length;
  activeActions.forEach((action) => {
    const item = document.createElement("li");
    const label = document.createElement("span");
    const time = document.createElement("time");
    label.textContent = action.label;
    time.dateTime = action.at || "";
    time.textContent = action.at ? formatCompactTime(action.at) : "时间未知";
    item.append(label, time);
    tooltipActiveList.append(item);
  });
  const result = ticket.latestResult;
  tooltipResult.hidden = !result;
  tooltipResultTime.dateTime = result?.at || "";
  tooltipResultTime.textContent = result?.at ? formatCompactTime(result.at) : "时间未知";
  tooltipResultSummary.textContent = result
    ? `${trailOutcomeLabel(result.outcome)} · ${result.summary}`
    : "";
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
  positionTicketTooltip(anchor);
}

function positionTicketTooltip(anchor) {
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
  previewTicket(ticket.id);
  showTicketTooltip(ticket, node);
}

function deactivateTicket() {
  clearTicketPreview();
  hideTicketTooltip();
}

function populateTooltipEvents(ticket, node) {
  node.setAttribute("aria-describedby", "ticket-tooltip");
  node.addEventListener("mouseenter", () => activateTicket(ticket, node));
  node.addEventListener("mouseleave", deactivateTicket);
  node.addEventListener("focus", () => activateTicket(ticket, node));
  node.addEventListener("blur", deactivateTicket);
  node.addEventListener("click", () => activateTicket(ticket, node));
}

function orderStagesByBarycenter(tickets, depths, maxDepth) {
  const dependents = new Map(tickets.map((ticket) => [ticket.id, []]));
  tickets.forEach((ticket) => ticket.dependencies.forEach((depId) => {
    if (dependents.has(depId)) dependents.get(depId).push(ticket.id);
  }));

  const stages = [];
  for (let depth = 0; depth <= maxDepth; depth += 1) {
    stages.push(tickets.filter((ticket) => depths.get(ticket.id) === depth));
  }

  const columnOf = new Map();
  const refreshColumns = () => {
    columnOf.clear();
    stages.forEach((stageTickets) => stageTickets.forEach((ticket, index) => columnOf.set(ticket.id, index)));
  };
  refreshColumns();

  const barycenter = (relatedIds, originalIndex) => {
    const positions = relatedIds.map((id) => columnOf.get(id)).filter((value) => value !== undefined);
    return positions.length ? positions.reduce((sum, value) => sum + value, 0) / positions.length : originalIndex;
  };

  const sortStage = (stageTickets, relate) => stageTickets
    .map((ticket, index) => ({ ticket, score: barycenter(relate(ticket), index), index }))
    .sort((a, b) => (a.score - b.score) || (a.index - b.index))
    .map((entry) => entry.ticket);

  const SWEEPS = 4;
  for (let sweep = 0; sweep < SWEEPS; sweep += 1) {
    if (sweep % 2 === 0) {
      for (let depth = 1; depth <= maxDepth; depth += 1) {
        stages[depth] = sortStage(stages[depth], (ticket) => ticket.dependencies);
        refreshColumns();
      }
    } else {
      for (let depth = maxDepth - 1; depth >= 0; depth -= 1) {
        stages[depth] = sortStage(stages[depth], (ticket) => dependents.get(ticket.id) || []);
        refreshColumns();
      }
    }
  }

  return stages;
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
    previewTicketId = null;
    hideTicketTooltip();
    return;
  }

  const byId = new Map(tickets.map((ticket) => [ticket.id, ticket]));
  const depths = new Map();
  tickets.forEach((ticket) => ticketDepth(ticket, byId, depths));
  const maxDepth = Math.max(...depths.values());
  flowCanvas.style.minWidth = "0";
  const stages = orderStagesByBarycenter(tickets, depths, maxDepth);

  for (let depth = 0; depth <= maxDepth; depth += 1) {
    const stage = document.createElement("section");
    stage.className = "flow-stage";
    const stageTickets = stages[depth];
    const row = document.createElement("div");
    row.className = "flow-stage-row";
    stageTickets.forEach((ticket) => {
      const node = document.createElement("button");
      node.type = "button";
      const runtimeClass = ticket.runtimeState ? ` is-${ticket.runtimeState.toLowerCase()}` : "";
      node.className = `flow-node ${ticket.state.toLowerCase()}${runtimeClass}`;
      node.dataset.ticketId = ticket.id;
      node.setAttribute("aria-pressed", "false");
      node.setAttribute("aria-label", `${ticket.name}，${stateLabel(ticket.state, ticket.runtimeState)}`);
      const head = document.createElement("span");
      head.className = "flow-node-head";
      const code = document.createElement("span");
      code.className = "flow-node-code";
      code.textContent = ticket.id;
      const badge = document.createElement("span");
      badge.className = `state-badge ${(ticket.runtimeState || ticket.state).toLowerCase()}`;
      badge.textContent = stateLabel(ticket.state, ticket.runtimeState);
      head.append(code, badge);
      const title = document.createElement("span");
      title.className = "flow-node-title";
      title.textContent = ticket.name;
      node.append(head, title);
      populateTooltipEvents(ticket, node);
      row.append(node);
    });
    stage.append(row);
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

function renderMonitor(monitor) {
  if (!monitor) {
    monitorPanel.dataset.level = "waiting";
    monitorTime.removeAttribute("datetime");
    monitorTime.textContent = "尚无记录";
    monitorLevel.className = "monitor-level waiting";
    monitorLevel.textContent = "暂无匹配监控";
    monitorSummary.hidden = false;
    monitorSummary.textContent = "当前项目和任务包暂无匹配监控记录。";
    monitorEvaluation.hidden = true;
    monitorThread.hidden = true;
    monitorThread.textContent = "";
    monitorObservations.hidden = true;
    closeObservationDialog();
    clear(monitorObservationList);
    currentObservations = [];
    pendingObservations = null;
    observationSignature = "";
    return;
  }
  const labels = {
    normal: "运行正常",
    attention: "值得关注",
    abnormal: "明显异常",
  };
  monitorPanel.dataset.level = monitor.level;
  monitorTime.dateTime = monitor.observedAt;
  monitorTime.textContent = formatCompactTime(monitor.observedAt);
  monitorLevel.className = `monitor-level ${monitor.level}`;
  monitorLevel.textContent = labels[monitor.level];
  const evaluation = monitor.evaluation;
  monitorSummary.hidden = Boolean(evaluation);
  monitorEvaluation.hidden = !evaluation;
  if (evaluation) {
    monitorProgress.textContent = evaluation.progress;
    monitorNext.textContent = evaluation.next;
    clear(monitorImprovements);
    const improvements = Array.isArray(evaluation.improvements) ? evaluation.improvements : [];
    monitorImprovementsRow.hidden = !improvements.length;
    improvements.forEach((item) => {
      const row = document.createElement("li");
      row.textContent = item;
      monitorImprovements.append(row);
    });
    const hasOwnerDecision = evaluation.owner && !/^(暂无|无|none)$/i.test(evaluation.owner.trim());
    monitorOwnerRow.hidden = !hasOwnerDecision;
    monitorOwner.textContent = hasOwnerDecision ? evaluation.owner : "";
  } else {
    monitorSummary.textContent = monitor.summary;
  }
  monitorThread.hidden = false;
  monitorThread.textContent = monitor.monitorThreadId;

  const observations = Array.isArray(monitor.observations) ? monitor.observations : [];
  monitorObservations.hidden = !observations.length;
  if (!observations.length) closeObservationDialog();
  monitorObservationCount.textContent = observations.length ? `· ${observations.length}` : "";
  monitorObservationDialogCount.textContent = observations.length ? `· ${observations.length}` : "";
  const nextSignature = JSON.stringify(observations);
  if (editingObservationId) {
    pendingObservations = observations;
  } else if (nextSignature !== observationSignature) {
    renderObservationList(observations);
  }
}

function renderObservationList(observations) {
  currentObservations = observations;
  observationSignature = JSON.stringify(observations);
  clear(monitorObservationList);
  const counts = observations.reduce((result, item) => {
    if (observationKind(item) === "pattern") result.pattern += 1;
    else result.specific += 1;
    return result;
  }, { pattern: 0, specific: 0 });
  observationFilterAllCount.textContent = String(observations.length);
  observationFilterPatternCount.textContent = String(counts.pattern);
  observationFilterSpecificCount.textContent = String(counts.specific);
  observationFilterButtons.forEach((button) => {
    button.disabled = Boolean(editingObservationId);
    button.setAttribute("aria-pressed", String(button.dataset.observationFilter === observationFilter));
  });
  const visible = observationFilter === "all"
    ? observations
    : observations.filter((item) => observationKind(item) === observationFilter);
  if (!visible.length) {
    const empty = document.createElement("li");
    empty.className = "observation-filter-empty";
    empty.textContent = "该分类暂无用户纠偏。";
    monitorObservationList.append(empty);
    return;
  }
  visible.forEach((item) => {
    const row = document.createElement("li");
    const time = document.createElement("time");
    const body = document.createElement("div");
    const heading = document.createElement("div");
    const kind = document.createElement("span");
    const edit = document.createElement("button");
    time.dateTime = item.observedAt;
    time.textContent = formatCompactTime(item.observedAt);
    body.className = "observation-body";
    heading.className = "observation-heading";
    const itemKind = observationKind(item);
    kind.className = `observation-kind ${itemKind}`;
    kind.textContent = itemKind === "pattern" ? "Pattern" : "具体动作";
    edit.type = "button";
    edit.className = "observation-edit";
    edit.textContent = "编辑";
    edit.disabled = Boolean(editingObservationId);
    edit.setAttribute("aria-label", "编辑这条纠偏的正文");
    edit.addEventListener("click", () => {
      editingObservationId = item.id;
      pendingObservations = null;
      renderObservationList(currentObservations);
      monitorObservationList.querySelector("textarea")?.focus();
    });
    heading.append(kind, edit);
    body.append(heading);
    if (editingObservationId === item.id) {
      body.append(createObservationEditor(item));
    } else {
      const content = document.createElement("p");
      content.textContent = item.content;
      body.append(content);
    }
    row.append(time, body);
    monitorObservationList.append(row);
  });
}

function observationKind(item) {
  return item.kind === "pattern" ? "pattern" : "specific";
}

const reviewTracks = [
  { name: "Track A", className: "track-a", label: "A · Code" },
  { name: "Track B", className: "track-b", label: "B · Standards" },
  { name: "Track C", className: "track-c", label: "C · Spec" },
  { name: "Track D", className: "track-d", label: "D · Safety" },
];

function reviewCount(value) {
  return Number.isSafeInteger(value) && value >= 0 ? String(value) : "—";
}

function reviewStatsSource(value) {
  if (!value || typeof value !== "object") return {};
  return value.totals && typeof value.totals === "object" ? value.totals : value;
}

function reviewTrackCounts(reviewStats, trackName) {
  const source = reviewStatsSource(reviewStats?.tracks?.[trackName]);
  return {
    caught: Number.isSafeInteger(source.caught) && source.caught >= 0 ? source.caught : 0,
    open: Number.isSafeInteger(source.open) && source.open >= 0 ? source.open : 0,
  };
}

function renderReviewStats(reviewStats) {
  const totals = reviewStatsSource(reviewStats);
  const unique = Number.isSafeInteger(totals.unique) && totals.unique >= 0 ? totals.unique : 0;
  const closed = Number.isSafeInteger(totals.closed) && totals.closed >= 0 ? totals.closed : 0;
  const coverage = reviewStats?.coverage || {};
  const hasLegacyActivity = coverage.reviewActivityRows > 0 && coverage.summaries === 0;
  reviewStatsUnique.textContent = hasLegacyActivity ? "—" : reviewCount(unique);
  reviewStatsClosed.textContent = hasLegacyActivity ? "—" : reviewCount(closed);
  const trackRows = reviewTracks.map((track) => ({
    ...track,
    counts: reviewTrackCounts(reviewStats, track.name),
  }));
  const contributionTotal = trackRows.reduce((sum, track) => sum + track.counts.caught, 0);
  clear(reviewBar);
  trackRows.forEach((track) => {
    const rawShare = contributionTotal > 0 ? (track.counts.caught / contributionTotal) * 100 : 25;
    const share = Math.max(rawShare, 4);
    const sharePct = contributionTotal > 0 ? Math.round(rawShare) : 0;
    const tooltip = `${track.label} · 捕获 ${track.counts.caught} · 开放 ${track.counts.open} · ${sharePct}%`;

    const segment = document.createElement("span");
    segment.className = `review-bar-segment ${track.className}`;
    segment.style.flex = `${share} 0 0%`;
    segment.tabIndex = 0;
    segment.setAttribute("aria-label", tooltip);
    segment.addEventListener("pointerenter", () => { reviewBarDetail.textContent = tooltip; });
    segment.addEventListener("pointerleave", () => { reviewBarDetail.textContent = ""; });
    segment.addEventListener("focus", () => { reviewBarDetail.textContent = tooltip; });
    segment.addEventListener("blur", () => { reviewBarDetail.textContent = ""; });

    const label = document.createElement("span");
    label.className = "review-bar-label";
    label.textContent = track.label;
    segment.append(label);

    reviewBar.append(segment);
  });
  reviewChart.dataset.empty = contributionTotal === 0 ? "true" : "false";
  reviewBarDetail.textContent = "";
}

function createObservationEditor(item) {
  const editor = document.createElement("div");
  const textarea = document.createElement("textarea");
  const actions = document.createElement("div");
  const error = document.createElement("p");
  const save = document.createElement("button");
  const cancel = document.createElement("button");
  editor.className = "observation-editor";
  textarea.value = item.content;
  textarea.maxLength = 2000;
  textarea.rows = 7;
  textarea.setAttribute("aria-label", "纠偏正文");
  actions.className = "observation-editor-actions";
  error.className = "observation-editor-error";
  error.setAttribute("aria-live", "polite");
  save.type = "button";
  save.className = "observation-save";
  save.textContent = "保存";
  cancel.type = "button";
  cancel.className = "observation-cancel";
  cancel.textContent = "取消";
  save.addEventListener("click", () => saveObservation(item, textarea, save, cancel, error));
  cancel.addEventListener("click", cancelObservationEdit);
  actions.append(save, cancel);
  editor.append(textarea, error, actions);
  return editor;
}

function cancelObservationEdit() {
  if (!editingObservationId) return;
  editingObservationId = null;
  const observations = pendingObservations || currentObservations;
  pendingObservations = null;
  renderObservationList(observations);
}

async function saveObservation(item, textarea, save, cancel, error) {
  const content = textarea.value.trim();
  if (!content) {
    error.textContent = "正文不能为空。";
    textarea.focus();
    return;
  }
  textarea.disabled = true;
  save.disabled = true;
  cancel.disabled = true;
  save.textContent = "保存中…";
  error.textContent = "";
  try {
    const query = `?package=${encodeURIComponent(selectedPackage.path)}`;
    const response = await fetch(`/api/tasks/${encodeURIComponent(selectedTask)}/observation${query}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: item.id, content, revision: item.revision }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `保存失败：${response.status}`);
    editingObservationId = null;
    pendingObservations = null;
    renderObservationList(currentObservations.map((candidate) => (
      candidate.id === item.id ? payload.observation : candidate
    )));
  } catch (caught) {
    textarea.disabled = false;
    save.disabled = false;
    cancel.disabled = false;
    save.textContent = "保存";
    error.textContent = caught instanceof Error ? caught.message : String(caught);
    textarea.focus();
  }
}

function render(snapshot) {
  taskReadout.textContent = snapshot.task.name;
  taskTitle.textContent = snapshot.task.name;
  taskStatus.textContent = snapshot.task.status;
  actualSummary.textContent = snapshot.actualProgress.summary;
  renderActivities(snapshot.actualProgress.activities);
  freshness.textContent = `页面更新 · ${formatTime(new Date().toISOString())}`;

  const pkg = snapshot.package;
  formalSummary.textContent = pkg ? pkg.formalSummary : "尚未关联";
  gateLabel.textContent = pkg ? pkg.gateLabel : "尚未关联";
  renderTickets(pkg?.tickets || [], pkg?.currentTicketId || null);
  renderReviewStats(pkg?.reviewStats || null);
  renderMonitor(snapshot.monitor);

  clear(auditList);
  appendAudit("任务标识", snapshot.audit.taskId);
  appendAudit("工作目录", snapshot.audit.workspace);
  appendAudit("本地分支", snapshot.audit.branch);
  appendAudit("版本锚点", snapshot.audit.revision);
  appendAudit("已读取记录位置", snapshot.audit.rolloutOffset);
  appendAudit("任务包格式", pkg?.audit?.formatVersion);
  appendAudit("当前尝试", pkg?.audit?.attempt);
  appendAudit("正式状态更新时间", pkg?.audit?.stateModifiedAt);
}

async function getJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `请求失败：${response.status}`);
  return payload;
}

function groupPackages(tasks) {
  const groups = new Map();
  tasks.forEach((task) => {
    const pkg = task.currentPackage;
    const existing = groups.get(pkg.identity);
    if (existing) {
      existing.tasks.push(task);
      return;
    }
    groups.set(pkg.identity, {
      identity: pkg.identity,
      name: pkg.name,
      path: pkg.path,
      workspaceName: pkg.workspaceName,
      task,
      tasks: [task],
    });
  });
  return [...groups.values()];
}

function selectPackage(identity) {
  const group = packageGroups.find((item) => item.identity === identity);
  if (!group) return;
  selectedPackage = group;
  selectedTask = group.task.id;
  packageSelect.value = group.identity;
  taskReadout.textContent = group.task.name;
  localStorage.setItem("codex-progress-package", group.identity);
  const url = new URL(window.location.href);
  url.searchParams.set("task", selectedTask);
  url.searchParams.set("package", group.path);
  window.history.replaceState(null, "", url);
  openEvents();
}

function openEvents() {
  if (events) events.close();
  const packagePath = selectedPackage?.path || "";
  const query = packagePath ? `?package=${encodeURIComponent(packagePath)}` : "";
  const separator = query ? "&" : "?";
  setConnection("loading", "正在连接");
  events = new EventSource(`/api/tasks/${encodeURIComponent(selectedTask)}/events${query}${separator}stream=${Date.now()}`);
  events.addEventListener("snapshot", (event) => {
    render(JSON.parse(event.data));
    setConnection("live", "实时连接");
  });
  events.onerror = () => setConnection("error", "正在重连");
}

packageSelect.addEventListener("change", () => {
  selectPackage(packageSelect.value);
});

monitorObservations.addEventListener("click", () => {
  observationFilter = "all";
  renderObservationList(currentObservations);
  monitorObservationDialog.showModal();
  monitorObservationClose.focus();
});

observationFilterButtons.forEach((button) => {
  button.addEventListener("click", () => {
    if (editingObservationId) return;
    observationFilter = button.dataset.observationFilter;
    renderObservationList(currentObservations);
  });
});

monitorObservationClose.addEventListener("click", closeObservationDialog);
monitorObservationDialog.addEventListener("click", (event) => {
  if (event.target === monitorObservationDialog) closeObservationDialog();
});

function showError(error) {
  setConnection("error", "读取失败");
  actualSummary.textContent = error instanceof Error ? error.message : String(error);
}

async function boot() {
  const params = new URLSearchParams(window.location.search);
  const requestedTask = params.get("task");
  const requestedPath = params.get("package");
  const { tasks } = await getJson("/api/tasks");
  if (!tasks.length) throw new Error("没有匹配到含当前任务包的项目。");
  packageGroups = groupPackages(tasks);
  const duplicateNames = new Map();
  packageGroups.forEach((group) => {
    duplicateNames.set(group.name, (duplicateNames.get(group.name) || 0) + 1);
  });
  clear(packageSelect);
  packageGroups.forEach((group) => {
    const label = duplicateNames.get(group.name) > 1
      ? `${group.name} · ${group.workspaceName}`
      : group.name;
    packageSelect.append(option(group.identity, label));
  });
  packageSelect.disabled = packageGroups.length === 0;
  const requestedGroup = packageGroups.find((group) => (
    group.path === requestedPath && group.tasks.some((task) => task.id === requestedTask)
  )) || packageGroups.find((group) => group.path === requestedPath);
  const saved = localStorage.getItem("codex-progress-package");
  const initial = requestedGroup
    || packageGroups.find((group) => group.identity === saved)
    || packageGroups[0];
  localStorage.removeItem("codex-progress-task");
  selectPackage(initial.identity);
}

boot().catch(showError);

window.addEventListener("resize", () => {
  clearTicketPreview();
  hideTicketTooltip();
  requestAnimationFrame(drawDependencyLines);
});
window.addEventListener("scroll", () => {
  clearTicketPreview();
  hideTicketTooltip();
}, true);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeObservationDialog();
    clearTicketPreview();
    hideTicketTooltip();
  }
});
