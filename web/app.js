const data = window.PMO_CONTROL_TOWER_DATA;

let selectedStatus = "All";
let selectedLane = "All";

const colors = {
  Red: "#ff5c6c",
  Amber: "#ffd166",
  Green: "#a6e85d",
  blue: "#35a7ff",
  ink: "#f5f8fb",
  muted: "rgba(245,248,251,0.58)",
  line: "rgba(245,248,251,0.14)",
};

const formatNumber = (value) => Number(value || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
const formatPct = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;
const escapeHtml = (value) =>
  String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
const titleize = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
const cleanActionText = (value) =>
  String(value ?? "")
    .replace(/Escalate Blocker, Confirm (Owner|Lead), And Add Executive Visibility This Week\./gi, "Escalate blocker risk, assign a decision lane, and brief leadership this week.")
    .replace(/Move To PMO Watchlist, Validate Scope, (Owner|Lead), And Next Decision Date\./gi, "Move to the PMO watchlist, validate scope, and set the next decision date.")
    .replace(/Confirm (Owners|Owner|Leads|Lead)/gi, "Assign accountable leads")
    .replace(/\bOwners\b/g, "Leads")
    .replace(/\bOwner\b/g, "Lead");
const shorten = (value, length = 18) => {
  const text = String(value ?? "");
  return text.length > length ? `${text.slice(0, length - 1)}...` : text;
};

function setupCanvas(canvas) {
  const context = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = Math.max(1, width * ratio);
  canvas.height = Math.max(1, height * ratio);
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { context, width, height };
}

function setKpis() {
  const kpis = data.kpis;
  document.querySelector("#kpiPrograms").textContent = formatNumber(kpis.programs_analyzed);
  document.querySelector("#kpiItems").textContent = formatNumber(kpis.work_items_scored);
  document.querySelector("#kpiHighRisk").textContent = formatNumber(kpis.high_risk_work_items);
  document.querySelector("#kpiAuc").textContent = Number(kpis.model_roc_auc || 0).toFixed(2);
  document.querySelector("#atRiskPrograms").textContent = `${formatNumber(kpis.at_risk_programs)} At Risk`;
}

function filteredPrograms() {
  return data.programHealth.filter((program) => selectedStatus === "All" || program.program_status === selectedStatus);
}

function renderProgramHealth() {
  const rows = filteredPrograms();
  const container = document.querySelector("#programList");
  if (!rows.length) {
    container.innerHTML = "<div class='empty-state'>No Programs Match This Status Lens.</div>";
    return;
  }
  container.innerHTML = rows
    .map((program) => {
      const status = String(program.program_status || "Amber").toLowerCase();
      const score = Number(program.program_health_score || 0);
      return `
        <article class="program-row ${status}">
          <div>
            <strong>${escapeHtml(program.program)}</strong>
            <span>${escapeHtml(program.source_repo)} / ${escapeHtml(program.portfolio_domain)}</span>
          </div>
          <div>
            <div class="health-track"><i style="width:${Math.max(3, score)}%"></i></div>
            <small>${score.toFixed(1)} Health / ${Number(program.avg_delay_risk_score).toFixed(1)} Avg Risk / ${formatPct(program.open_rate)} Open</small>
          </div>
          <div>
            <b class="status-pill ${status}">${escapeHtml(program.program_status)}</b>
            <small>${formatNumber(program.high_risk_items)} High Risk</small>
          </div>
        </article>
      `;
    })
    .join("");
}

function buildStatusFilters() {
  document.querySelectorAll("#statusFilters button").forEach((button) => {
    button.addEventListener("click", () => {
      selectedStatus = button.dataset.status;
      document.querySelectorAll("#statusFilters button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      renderProgramHealth();
      drawRiskCanvas();
      drawPortfolioCanvas();
    });
  });
}

function actionRows() {
  const search = document.querySelector("#actionSearch").value.trim().toLowerCase();
  return data.actionQueue.filter((row) => {
    const laneMatch = selectedLane === "All" || row.decision_lane === selectedLane;
    const haystack = `${row.decision_lane} ${row.program} ${row.source_repo} ${row.title} ${row.risk_level} ${row.labels}`.toLowerCase();
    return laneMatch && haystack.includes(search);
  });
}

function renderActionQueue() {
  const rows = actionRows();
  const container = document.querySelector("#actionList");
  if (!rows.length) {
    container.innerHTML = "<div class='empty-state'>No Matching PMO Actions Found.</div>";
    return;
  }
  container.innerHTML = rows
    .map((row) => {
      const level = String(row.risk_level || "Low").toLowerCase();
      return `
        <article class="action-row ${level}">
          <div class="action-top">
            <strong>${escapeHtml(row.title)}</strong>
            <b class="risk-badge ${level}">${escapeHtml(row.risk_level)} / ${Number(row.delay_risk_score).toFixed(1)}</b>
          </div>
          <p>${escapeHtml(row.decision_lane)} - ${escapeHtml(row.program)}</p>
          <p>${escapeHtml(cleanActionText(row.recommended_action))}</p>
          <p>${escapeHtml(row.source_repo)} #${escapeHtml(row.item_number)} / ${formatNumber(row.age_days)} Days Old</p>
        </article>
      `;
    })
    .join("");
}

function buildLaneFilters() {
  document.querySelectorAll("#laneFilters button").forEach((button) => {
    button.addEventListener("click", () => {
      selectedLane = button.dataset.lane;
      document.querySelectorAll("#laneFilters button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      renderActionQueue();
    });
  });
  document.querySelector("#actionSearch").addEventListener("input", renderActionQueue);
}

function drawRiskCanvas() {
  const canvas = document.querySelector("#riskCanvas");
  const { context, width, height } = setupCanvas(canvas);
  context.clearRect(0, 0, width, height);

  const margin = { top: 30, right: 28, bottom: 44, left: 54 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const rows = filteredPrograms();

  context.strokeStyle = colors.line;
  context.lineWidth = 1;
  context.fillStyle = colors.muted;
  context.font = "12px Inter, sans-serif";

  for (let i = 0; i <= 4; i += 1) {
    const x = margin.left + (chartWidth * i) / 4;
    const y = margin.top + (chartHeight * i) / 4;
    context.beginPath();
    context.moveTo(x, margin.top);
    context.lineTo(x, height - margin.bottom);
    context.stroke();
    context.beginPath();
    context.moveTo(margin.left, y);
    context.lineTo(width - margin.right, y);
    context.stroke();
  }

  context.fillText("High Health", width - 98, height - 14);
  context.fillText("High Risk", 8, margin.top + 4);

  const points = rows.map((program) => {
    const health = Number(program.program_health_score || 0);
    const risk = Number(program.avg_delay_risk_score || 0);
    return {
      program,
      x: margin.left + (health / 100) * chartWidth,
      y: margin.top + chartHeight - (risk / 100) * chartHeight,
      statusColor: colors[program.program_status] || colors.blue,
      label: program.source_repo.split("/")[1],
    };
  });

  points.forEach((point) => {
    const { x, y, statusColor } = point;
    context.fillStyle = statusColor;
    context.beginPath();
    context.arc(x, y, 9, 0, Math.PI * 2);
    context.fill();
    context.strokeStyle = "rgba(8,11,16,0.82)";
    context.lineWidth = 2;
    context.stroke();
  });

  const placedLabels = [];
  const overlaps = (box) =>
    placedLabels.some(
      (placed) =>
        box.x < placed.x + placed.w &&
        box.x + box.w > placed.x &&
        box.y < placed.y + placed.h &&
        box.y + box.h > placed.y,
    );

  context.font = "800 11px Inter, sans-serif";
  points
    .sort((a, b) => a.y - b.y)
    .forEach((point) => {
      const text = point.label;
      const textWidth = context.measureText(text).width;
      const boxWidth = textWidth + 14;
      const boxHeight = 20;
      const rightSide = point.x + 14 + boxWidth < width - 12;
      const labelX = Math.max(8, Math.min(width - boxWidth - 8, rightSide ? point.x + 14 : point.x - boxWidth - 14));
      const candidates = [0, -18, 18, -36, 36, -54, 54, -72, 72];
      let labelY = point.y - boxHeight / 2;
      let chosenBox = null;
      for (const offset of candidates) {
        const nextY = Math.max(margin.top + 4, Math.min(height - margin.bottom - boxHeight - 4, point.y - boxHeight / 2 + offset));
        const box = { x: labelX, y: nextY, w: boxWidth, h: boxHeight };
        if (!overlaps(box)) {
          labelY = nextY;
          chosenBox = box;
          break;
        }
      }
      if (!chosenBox) {
        chosenBox = { x: labelX, y: labelY, w: boxWidth, h: boxHeight };
      }
      placedLabels.push(chosenBox);
      const connectorX = rightSide ? labelX : labelX + boxWidth;
      context.strokeStyle = "rgba(245,248,251,0.28)";
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(point.x, point.y);
      context.lineTo(connectorX, labelY + boxHeight / 2);
      context.stroke();
      context.lineWidth = 4;
      context.strokeStyle = "rgba(245,248,251,0.88)";
      context.strokeText(text, labelX + 7, labelY + 14);
      context.fillStyle = colors.ink;
      context.fillText(text, labelX + 7, labelY + 14);
    });
}

function drawFlowCanvas() {
  const canvas = document.querySelector("#flowCanvas");
  const { context, width, height } = setupCanvas(canvas);
  context.clearRect(0, 0, width, height);

  const grouped = data.flowTimeline.reduce((acc, row) => {
    if (!acc[row.month]) acc[row.month] = { month: row.month, created: 0, closed: 0, high: 0 };
    acc[row.month].created += Number(row.created_items || 0);
    acc[row.month].closed += Number(row.closed_items || 0);
    acc[row.month].high += Number(row.created_high_risk || 0);
    return acc;
  }, {});
  const rows = Object.values(grouped).sort((a, b) => String(a.month).localeCompare(String(b.month)));
  const maxValue = Math.max(...rows.map((row) => Math.max(row.created, row.closed)), 1);
  const margin = { top: 24, right: 24, bottom: 42, left: 48 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const slot = chartWidth / Math.max(rows.length, 1);
  const barWidth = Math.max(8, slot * 0.28);

  context.strokeStyle = colors.line;
  context.fillStyle = colors.muted;
  context.font = "12px Inter, sans-serif";
  for (let i = 0; i <= 4; i += 1) {
    const y = margin.top + chartHeight - (chartHeight * i) / 4;
    context.beginPath();
    context.moveTo(margin.left, y);
    context.lineTo(width - margin.right, y);
    context.stroke();
    context.fillText(formatNumber((maxValue * i) / 4), 8, y + 4);
  }

  rows.forEach((row, index) => {
    const x = margin.left + index * slot + slot * 0.22;
    const createdHeight = (row.created / maxValue) * chartHeight;
    const closedHeight = (row.closed / maxValue) * chartHeight;
    context.fillStyle = colors.blue;
    context.fillRect(x, margin.top + chartHeight - createdHeight, barWidth, createdHeight);
    context.fillStyle = colors.lime;
    context.fillRect(x + barWidth + 3, margin.top + chartHeight - closedHeight, barWidth, closedHeight);
    if (index % Math.ceil(rows.length / 6 || 1) === 0) {
      context.fillStyle = colors.muted;
      context.fillText(String(row.month).slice(5, 7), x, height - 15);
    }
  });

  context.fillStyle = colors.blue;
  context.fillRect(margin.left, 8, 10, 10);
  context.fillStyle = colors.ink;
  context.fillText("Created", margin.left + 16, 18);
  context.fillStyle = colors.lime;
  context.fillRect(margin.left + 92, 8, 10, 10);
  context.fillStyle = colors.ink;
  context.fillText("Closed", margin.left + 108, 18);
}

function drawPortfolioCanvas() {
  const canvas = document.querySelector("#portfolioCanvas");
  const { context, width, height } = setupCanvas(canvas);
  const programs = data.programHealth;
  const core = { x: width * 0.76, y: height * 0.5 };
  context.clearRect(0, 0, width, height);

  context.strokeStyle = "rgba(245,248,251,0.08)";
  for (let x = 0; x < width; x += 52) {
    context.beginPath();
    context.moveTo(x, 0);
    context.lineTo(x, height);
    context.stroke();
  }
  for (let y = 0; y < height; y += 52) {
    context.beginPath();
    context.moveTo(0, y);
    context.lineTo(width, y);
    context.stroke();
  }

  context.fillStyle = "rgba(53,167,255,0.1)";
  context.strokeStyle = "rgba(53,167,255,0.36)";
  context.lineWidth = 2;
  context.beginPath();
  context.arc(core.x, core.y, 72, 0, Math.PI * 2);
  context.fill();
  context.stroke();
  context.fillStyle = colors.ink;
  context.font = "900 12px Inter, sans-serif";
  context.fillText("PMO DECISION CORE", core.x - 62, core.y + 4);

  programs.forEach((program, index) => {
    const y = height * (0.18 + index * 0.145);
    const x = width * (0.5 + (index % 2) * 0.055);
    const statusColor = colors[program.program_status] || colors.blue;
    const risk = Number(program.avg_delay_risk_score || 0);
    const blockers = Number(program.blocker_signals || 0);
    const radius = 10 + Math.min(18, Number(program.total_work_items || 0) / 34);

    context.strokeStyle = statusColor;
    context.globalAlpha = 0.24 + Math.min(0.42, blockers / 900);
    context.lineWidth = 1.5 + Math.min(7, risk / 12);
    context.beginPath();
    context.moveTo(x + radius, y);
    context.bezierCurveTo(width * 0.52, y - 34, width * 0.62, core.y + (index - 2) * 18, core.x - 72, core.y);
    context.stroke();

    context.globalAlpha = 1;
    context.fillStyle = "rgba(8,11,16,0.82)";
    context.strokeStyle = statusColor;
    context.lineWidth = 2;
    context.beginPath();
    context.arc(x, y, radius, 0, Math.PI * 2);
    context.fill();
    context.stroke();
    context.fillStyle = statusColor;
    context.fillRect(x - radius, y + radius + 7, radius * 2 * Math.min(1, Number(program.program_health_score || 0) / 100), 4);
    context.font = "900 11px Inter, sans-serif";
    const label = shorten(program.source_repo.split("/")[1], 14);
    const labelWidth = context.measureText(label).width + 14;
    const labelX = Math.min(x + radius + 9, width - labelWidth - 10);
    context.lineWidth = 4;
    context.strokeStyle = "rgba(255,255,255,0.88)";
    context.strokeText(label, labelX + 7, y + 2);
    context.fillStyle = colors.ink;
    context.fillText(label, labelX + 7, y + 2);
    context.fillStyle = colors.muted;
    context.font = "800 10px Inter, sans-serif";
    context.fillText(`${program.program_status} / ${program.high_risk_items} High Risk`, labelX + 7, y + 16);
  });
}

function renderDependencyView() {
  document.querySelector("#dependencyList").innerHTML = data.dependencyView
    .slice(0, 10)
    .map(
      (row) => `
        <article class="dependency-row">
          <strong>${escapeHtml(row.dependency_signal)}</strong>
          <p>${escapeHtml(row.title)}</p>
          <p>${escapeHtml(row.source_repo)} #${escapeHtml(row.item_number)} / ${Number(row.delay_risk_score).toFixed(1)} Risk</p>
        </article>
      `,
    )
    .join("");
}

function renderBriefs() {
  document.querySelector("#briefList").innerHTML = data.statusBriefs
    .map(
      (row) => `
        <article class="brief-row">
          <strong>${escapeHtml(row.program)} / ${escapeHtml(row.program_status)}</strong>
          <p>${escapeHtml(cleanActionText(row.status_brief))}</p>
          <p>${escapeHtml(cleanActionText(row.recommended_focus))}</p>
        </article>
      `,
    )
    .join("");
}

function renderMetrics() {
  const preferred = ["ROC AUC", "Average Precision", "F1", "Risk Threshold", "Accuracy", "Observed Delay Rate"];
  document.querySelector("#metricList").innerHTML = data.modelMetrics
    .filter((row) => preferred.includes(row.metric))
    .map(
      (row) => `
        <div class="metric-row">
          <span>${escapeHtml(row.metric)}</span>
          <small>${Number(row.value).toLocaleString("en-US", { maximumFractionDigits: 4 })}</small>
        </div>
      `,
    )
    .join("");
}

function renderImportance() {
  const maxImportance = Math.max(...data.featureImportance.map((row) => Math.abs(Number(row.importance || 0))), 0.001);
  document.querySelector("#importanceList").innerHTML = data.featureImportance
    .slice(0, 9)
    .map((row) => {
      const width = Math.max(2, (Math.abs(Number(row.importance || 0)) / maxImportance) * 100);
      return `
        <div class="driver-row">
          <div>
            <span>${escapeHtml(titleize(row.feature))}</span>
            <small>${Number(row.importance || 0).toFixed(4)}</small>
          </div>
          <div class="driver-track"><i style="width:${width}%"></i></div>
        </div>
      `;
    })
    .join("");
}

function init() {
  if (!data) {
    document.body.innerHTML = "<main class='control-shell'><h1>Dashboard Data Missing</h1></main>";
    return;
  }
  setKpis();
  buildStatusFilters();
  buildLaneFilters();
  renderProgramHealth();
  renderActionQueue();
  renderDependencyView();
  renderBriefs();
  renderMetrics();
  renderImportance();
  drawPortfolioCanvas();
  drawRiskCanvas();
  drawFlowCanvas();
  window.addEventListener("resize", () => {
    drawPortfolioCanvas();
    drawRiskCanvas();
    drawFlowCanvas();
  });
}

init();
