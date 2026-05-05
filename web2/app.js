const fieldsGrid = document.querySelector("#fieldsGrid");
const startBtn = document.querySelector("#startBtn");
const resetBtn = document.querySelector("#resetBtn");
const searchInput = document.querySelector("#searchInput");
const statusPill = document.querySelector("#statusPill");
const progressBar = document.querySelector("#progressBar");
const progressText = document.querySelector("#progressText");
const scenarioSummary = document.querySelector("#scenarioSummary");
const quickGnbs = document.querySelector("#quick_gnbs");
const quickUes = document.querySelector("#quick_ues");
const quickSteps = document.querySelector("#quick_steps");
const metricsGrid = document.querySelector("#metricsGrid");
const summaryBody = document.querySelector("#summaryBody");
const metricSelect = document.querySelector("#metricSelect");
const methodLegend = document.querySelector("#methodLegend");
const chart = document.querySelector("#chart");
const downloadBtn = document.querySelector("#downloadBtn");
const networkCanvas = document.querySelector("#networkCanvas");
const canvasEmpty = document.querySelector("#canvasEmpty");
const topologyStats = document.querySelector("#topologyStats");

let configFields = [];
let lastState = null;
let pollTimer = null;
let topology = null;
let topologyFrame = null;
let lastTopologyTick = 0;
let activeGroup = "all";

const metricLabels = {
  energy_efficiency_gb_per_j: "Eficiencia energetica",
  link_failures: "Falhas de link",
  total_handovers: "Handovers totais",
  pingpong_handovers: "Ping-pong",
};

const serviceColors = {
  eMBB: "#2563eb",
  URLLC: "#dc2626",
  mMTC: "#16a34a",
};

const methodColors = {
  NC: "#64748b",
  SBD: "#2563eb",
  "P-ES": "#16a34a",
  "P-MRO": "#dc2626",
  QACM: "#7c3aed",
};

const fieldUx = {
  n_gnbs: ["Rede", "network", "gNB"],
  n_ues: ["UEs", "network", "UE"],
  sim_time_s: ["Tempo simulado", "network", "s"],
  dt_s: ["Passo temporal", "network", "s"],
  adjustment_interval_s: ["Intervalo de ajuste", "network", "s"],
  frequency_mhz: ["Frequencia", "radio", "MHz"],
  rsrp_threshold_dbm: ["Limiar RSRP", "radio", "dBm"],
  txp_default_dbm: ["TXP padrao", "radio", "dBm"],
  txp_es_dbm: ["TXP ES", "radio", "dBm"],
  txp_mro_dbm: ["TXP MRO", "radio", "dBm"],
  cio_db: ["CIO", "mobility", "dB"],
  hys_db: ["Histerese", "mobility", "dB"],
  ttt_ms: ["TTT", "mobility", "ms"],
  ret_deg: ["RET", "radio", "deg"],
  area_size_m: ["Area quadrada", "network", "m"],
  noise_floor_dbm: ["Piso de ruido", "radio", "dBm"],
  bandwidth_hz: ["Largura de banda", "radio", "Hz"],
  static_power_w: ["Potencia estatica", "energy", "W"],
  pa_efficiency: ["Eficiencia PA", "energy", ""],
  pingpong_window_s: ["Janela ping-pong", "mobility", "s"],
  qacm_link_failure_target: ["Alvo QACM", "qos", "falhas"],
};

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    document.querySelector(`#${button.dataset.tab}`).classList.add("active");
  });
});

function fmt(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const number = Number(value);
  if (Math.abs(number) >= 1000) return number.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
  if (Math.abs(number) >= 10) return number.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  return number.toLocaleString("pt-BR", { maximumFractionDigits: 5 });
}

function decorateFields(fields) {
  return fields.map((field) => {
    const ux = fieldUx[field.name] || [field.label, "network", ""];
    return {
      ...field,
      label: ux[0],
      group: ux[1],
      unit: ux[2],
      category: ux[1].toUpperCase(),
    };
  });
}

function renderFields(filter = "") {
  const query = filter.trim().toLowerCase();
  fieldsGrid.innerHTML = "";

  configFields
    .filter((field) => activeGroup === "all" || field.group === activeGroup)
    .filter((field) => field.name.toLowerCase().includes(query) || field.label.toLowerCase().includes(query))
    .forEach((field) => {
      const card = document.createElement("div");
      card.className = "field-card";
      card.innerHTML = `
        <label>
          <span class="field-label-row">
            <span>${field.label}</span>
            ${field.unit ? `<span class="unit-badge">${field.unit}</span>` : ""}
          </span>
          <input
            data-config-name="${field.name}"
            type="number"
            step="${field.type === "int" ? "1" : "any"}"
            value="${field.value}"
          />
        </label>
        <div class="field-meta">${field.name} / ${field.category}</div>
      `;
      fieldsGrid.appendChild(card);
    });
}

function getField(name) {
  return configFields.find((item) => item.name === name);
}

function setFieldValue(name, value) {
  const field = getField(name);
  if (!field) return;
  field.value = value;
  const input = fieldsGrid.querySelector(`[data-config-name="${name}"]`);
  if (input) input.value = value;
}

function currentSteps() {
  const dt = getConfigValue("dt_s", 0.1);
  const simTime = getConfigValue("sim_time_s", 600);
  return dt > 0 ? Math.max(1, Math.round(simTime / dt)) : 1;
}

function syncQuickControlsFromConfig() {
  if (!configFields.length) return;
  quickGnbs.value = Math.max(1, Math.round(getConfigValue("n_gnbs", 4)));
  quickUes.value = Math.max(1, Math.round(getConfigValue("n_ues", 100)));
  quickSteps.value = currentSteps();
}

function syncConfigFromQuickControls() {
  const gnbs = Math.max(1, Math.round(Number(quickGnbs.value || 1)));
  const ues = Math.max(1, Math.round(Number(quickUes.value || 1)));
  const steps = Math.max(1, Math.round(Number(quickSteps.value || 1)));
  const dt = Math.max(Number(getConfigValue("dt_s", 0.1)), 0.000001);

  quickGnbs.value = gnbs;
  quickUes.value = ues;
  quickSteps.value = steps;

  setFieldValue("n_gnbs", gnbs);
  setFieldValue("n_ues", ues);
  setFieldValue("sim_time_s", Number((steps * dt).toFixed(6)));
}

function collectPayload() {
  syncConfigFromQuickControls();
  const config = {};
  configFields.forEach((field) => {
    config[field.name] = field.type === "int" ? parseInt(field.value, 10) : parseFloat(field.value);
  });

  const methods = Array.from(document.querySelectorAll(".method-check:checked")).map((option) => option.value);
  return {
    repetitions: parseInt(document.querySelector("#repetitions").value, 10),
    base_seed: parseInt(document.querySelector("#base_seed").value, 10),
    methods,
    config,
  };
}

function getConfigValue(name, fallback = 0) {
  const field = getField(name);
  const value = Number(field?.value);
  return Number.isFinite(value) ? value : fallback;
}

function renderScenarioSummary() {
  if (!configFields.length) return;
  const repetitions = Number(document.querySelector("#repetitions").value || 0);
  const methods = document.querySelectorAll(".method-check:checked").length;
  const nUes = getConfigValue("n_ues");
  const nGnbs = getConfigValue("n_gnbs");
  const steps = currentSteps();
  const runs = repetitions * methods;

  scenarioSummary.innerHTML = `
    <div><strong>${fmt(nGnbs)}</strong><span>gNBs</span></div>
    <div><strong>${fmt(nUes)}</strong><span>UEs</span></div>
    <div><strong>${fmt(steps)}</strong><span>steps/run</span></div>
    <div><strong>${fmt(runs)}</strong><span>execucoes</span></div>
  `;
}

function setProgress(state) {
  const total = state.total || 0;
  const completed = state.completed || 0;
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
  progressBar.style.width = `${percent}%`;
  progressText.textContent = state.message || `${completed}/${total} simulacoes completas`;
  statusPill.textContent = state.running ? "Running" : state.status || "Idle";
  statusPill.dataset.status = state.running ? "running" : (state.status || "idle").toLowerCase();
}

function renderMetrics(summary) {
  const rows = Object.entries(summary || {});
  if (!rows.length) {
    metricsGrid.innerHTML = `
      <article class="metric-card empty"><div class="metric-label">Eficiencia</div><div class="metric-value">-</div></article>
      <article class="metric-card empty"><div class="metric-label">Falhas</div><div class="metric-value">-</div></article>
      <article class="metric-card empty"><div class="metric-label">Handovers</div><div class="metric-value">-</div></article>
      <article class="metric-card empty"><div class="metric-label">Ping-pong</div><div class="metric-value">-</div></article>
    `;
    return;
  }

  const bestEnergy = rows.reduce((best, row) => {
    const value = row[1].energy_efficiency_gb_per_j.mean;
    return value > best.value ? { method: row[0], value } : best;
  }, { method: "-", value: -Infinity });

  const minFailures = rows.reduce((best, row) => {
    const value = row[1].link_failures.mean;
    return value < best.value ? { method: row[0], value } : best;
  }, { method: "-", value: Infinity });

  const minHandovers = rows.reduce((best, row) => {
    const value = row[1].total_handovers.mean;
    return value < best.value ? { method: row[0], value } : best;
  }, { method: "-", value: Infinity });

  const minPingpong = rows.reduce((best, row) => {
    const value = row[1].pingpong_handovers.mean;
    return value < best.value ? { method: row[0], value } : best;
  }, { method: "-", value: Infinity });

  const cards = [
    ["Maior eficiencia", `${bestEnergy.method} / ${fmt(bestEnergy.value)}`],
    ["Menos falhas", `${minFailures.method} / ${fmt(minFailures.value)}`],
    ["Menos handovers", `${minHandovers.method} / ${fmt(minHandovers.value)}`],
    ["Menos ping-pong", `${minPingpong.method} / ${fmt(minPingpong.value)}`],
  ];

  metricsGrid.innerHTML = cards.map(([label, value]) => `
    <article class="metric-card">
      <div class="metric-label">${label}</div>
      <div class="metric-value">${value}</div>
    </article>
  `).join("");
}

function renderTable(summary) {
  const rows = Object.entries(summary || {});
  if (!rows.length) {
    summaryBody.innerHTML = `<tr><td colspan="5">Execute uma simulacao para visualizar as saidas.</td></tr>`;
    return;
  }

  summaryBody.innerHTML = rows.map(([method, values]) => `
    <tr>
      <td><strong>${method}</strong></td>
      <td>${fmt(values.energy_efficiency_gb_per_j.mean)}</td>
      <td>${fmt(values.link_failures.mean)}</td>
      <td>${fmt(values.total_handovers.mean)}</td>
      <td>${fmt(values.pingpong_handovers.mean)}</td>
    </tr>
  `).join("");
}

function renderChart(summary) {
  const metric = metricSelect.value;
  const rows = Object.entries(summary || {});
  if (!rows.length) {
    methodLegend.innerHTML = "";
    chart.innerHTML = `<p class="field-meta">Sem dados para o grafico.</p>`;
    return;
  }

  const values = rows.map(([method, data]) => ({ method, value: data[metric].mean }));
  const max = Math.max(...values.map((row) => row.value), 1e-9);
  methodLegend.innerHTML = values.map((row) => `
    <span><i style="background:${methodColors[row.method] || "#64748b"}"></i>${row.method}</span>
  `).join("");

  chart.innerHTML = `
    <div class="field-meta">${metricLabels[metric]} por media das repeticoes</div>
    ${values.map((row) => `
      <div class="bar-row">
        <div class="bar-label">${row.method}</div>
        <div class="bar-track">
          <div class="bar-fill" style="width:${Math.max(3, (row.value / max) * 100)}%; background:${methodColors[row.method] || "#2563eb"}"></div>
        </div>
        <div class="bar-value">${fmt(row.value)}</div>
      </div>
    `).join("")}
  `;
}

function renderOutputs(state) {
  const summary = state.results?.summary || {};
  renderMetrics(summary);
  renderTable(summary);
  renderChart(summary);
  syncTopology(state.topology);
}

function cloneTopology(nextTopology) {
  return {
    area_size_m: Number(nextTopology.area_size_m || 1000),
    dt_s: Number(nextTopology.dt_s || 0.1),
    gnbs: (nextTopology.gnbs || []).map((item) => ({ ...item })),
    ues: (nextTopology.ues || []).map((item) => ({ ...item })),
  };
}

function syncTopology(nextTopology) {
  if (!nextTopology?.gnbs?.length || !nextTopology?.ues?.length) return;
  topology = cloneTopology(nextTopology);
  canvasEmpty.style.display = "none";
  renderTopologyStats();
  if (!topologyFrame) {
    lastTopologyTick = performance.now();
    topologyFrame = requestAnimationFrame(animateTopology);
  }
}

function renderTopologyStats() {
  if (!topology) return;
  topologyStats.innerHTML = `
    <span>gNBs: ${topology.gnbs.length}</span>
    <span>UEs: ${topology.ues.length}</span>
    <span>Area: ${fmt(topology.area_size_m)} m</span>
    <span>Tempo: ${fmt(getConfigValue("sim_time_s"))} s</span>
  `;
}

function resizeCanvasForDisplay() {
  const rect = networkCanvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.floor(rect.width * ratio));
  const height = Math.max(1, Math.floor(rect.height * ratio));
  if (networkCanvas.width !== width || networkCanvas.height !== height) {
    networkCanvas.width = width;
    networkCanvas.height = height;
  }
  return { width, height, ratio };
}

function worldToCanvas(x, y, width, height, padding, areaSize) {
  const span = Math.max(areaSize, 1);
  return {
    x: padding + (x / span) * (width - padding * 2),
    y: padding + (y / span) * (height - padding * 2),
  };
}

function stepTopology(deltaSeconds) {
  if (!topology) return;
  const areaSize = topology.area_size_m;
  const speedScale = 18;

  topology.ues.forEach((ue) => {
    ue.x += ue.vx * deltaSeconds * speedScale;
    ue.y += ue.vy * deltaSeconds * speedScale;

    if (ue.x < 0) {
      ue.x = -ue.x;
      ue.vx *= -1;
    }
    if (ue.y < 0) {
      ue.y = -ue.y;
      ue.vy *= -1;
    }
    if (ue.x > areaSize) {
      ue.x = 2 * areaSize - ue.x;
      ue.vx *= -1;
    }
    if (ue.y > areaSize) {
      ue.y = 2 * areaSize - ue.y;
      ue.vy *= -1;
    }
  });
}

function drawGrid(ctx, width, height, padding) {
  ctx.strokeStyle = "#dbe4ef";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const x = padding + ((width - padding * 2) * i) / 4;
    const y = padding + ((height - padding * 2) * i) / 4;
    ctx.beginPath();
    ctx.moveTo(x, padding);
    ctx.lineTo(x, height - padding);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(width - padding, y);
    ctx.stroke();
  }
}

function drawCellTower(ctx, x, y, ratio) {
  const mastHeight = 28 * ratio;
  const mastTop = y - mastHeight * 0.52;
  const mastBottom = y + mastHeight * 0.42;

  ctx.save();
  ctx.strokeStyle = "#7c2d12";
  ctx.fillStyle = "#c2410c";
  ctx.lineWidth = 2.2 * ratio;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  ctx.beginPath();
  ctx.moveTo(x, mastTop);
  ctx.lineTo(x, mastBottom);
  ctx.stroke();

  ctx.beginPath();
  ctx.moveTo(x, y - 3 * ratio);
  ctx.lineTo(x - 10 * ratio, mastBottom);
  ctx.moveTo(x, y - 3 * ratio);
  ctx.lineTo(x + 10 * ratio, mastBottom);
  ctx.stroke();

  ctx.beginPath();
  ctx.moveTo(x - 12 * ratio, mastBottom);
  ctx.lineTo(x + 12 * ratio, mastBottom);
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(x, mastTop, 3.2 * ratio, 0, Math.PI * 2);
  ctx.fill();

  ctx.strokeStyle = "rgba(194, 65, 12, 0.78)";
  [9, 16].forEach((radius) => {
    const r = radius * ratio;
    ctx.beginPath();
    ctx.arc(x, mastTop + 1 * ratio, r, -0.92, -0.22);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(x, mastTop + 1 * ratio, r, Math.PI + 0.22, Math.PI + 0.92);
    ctx.stroke();
  });

  ctx.restore();
}

function drawTopology() {
  if (!topology) return;
  const ctx = networkCanvas.getContext("2d");
  const { width, height, ratio } = resizeCanvasForDisplay();
  const padding = 34 * ratio;
  const areaSize = topology.area_size_m;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#f8fafc";
  ctx.fillRect(0, 0, width, height);

  drawGrid(ctx, width, height, padding);

  ctx.strokeStyle = "#94a3b8";
  ctx.lineWidth = 2 * ratio;
  ctx.strokeRect(padding, padding, width - padding * 2, height - padding * 2);

  topology.ues.forEach((ue) => {
    const point = worldToCanvas(ue.x, ue.y, width, height, padding, areaSize);
    ctx.beginPath();
    ctx.fillStyle = serviceColors[ue.service] || "#64748b";
    ctx.globalAlpha = 0.86;
    ctx.arc(point.x, point.y, 3.8 * ratio, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.globalAlpha = 1;

  topology.gnbs.forEach((gnb) => {
    const point = worldToCanvas(gnb.x, gnb.y, width, height, padding, areaSize);
    drawCellTower(ctx, point.x, point.y, ratio);

    ctx.fillStyle = "#111827";
    ctx.font = `${11 * ratio}px Segoe UI, Arial`;
    ctx.fillText(`gNB ${gnb.id}`, point.x + 10 * ratio, point.y - 10 * ratio);

    ctx.strokeStyle = "rgba(194, 65, 12, 0.16)";
    ctx.lineWidth = 1 * ratio;
    ctx.beginPath();
    ctx.arc(point.x, point.y, 72 * ratio, 0, Math.PI * 2);
    ctx.stroke();
  });
}

function animateTopology(now) {
  const deltaSeconds = Math.min((now - lastTopologyTick) / 1000, 0.08);
  lastTopologyTick = now;
  stepTopology(deltaSeconds);
  drawTopology();
  topologyFrame = requestAnimationFrame(animateTopology);
}

async function loadConfig() {
  const response = await fetch("/api/config");
  const data = await response.json();
  configFields = decorateFields(data.fields);
  syncQuickControlsFromConfig();
  renderFields();
  renderScenarioSummary();
}

async function loadState() {
  const response = await fetch("/api/state");
  const state = await response.json();
  lastState = state;
  setProgress(state);
  renderOutputs(state);
  startBtn.disabled = Boolean(state.running);

  if (!state.running && pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function startSimulation() {
  const payload = collectPayload();
  if (!payload.methods.length) {
    progressText.textContent = "Selecione pelo menos um metodo.";
    return;
  }

  const response = await fetch("/api/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    progressText.textContent = data.error || "Nao foi possivel iniciar.";
    return;
  }

  statusPill.textContent = data.status;
  await loadState();
  pollTimer = setInterval(loadState, 900);
}

async function resetDefaults() {
  await loadConfig();
  document.querySelector("#repetitions").value = 10;
  document.querySelector("#base_seed").value = 42;
  document.querySelectorAll(".method-check").forEach((item) => {
    item.checked = true;
  });
  syncQuickControlsFromConfig();
  renderScenarioSummary();
}

function downloadCsv() {
  if (!lastState?.results?.csv) return;
  const blob = new Blob([lastState.results.csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "results_oran_mro_es_web.csv";
  a.click();
  URL.revokeObjectURL(url);
}

searchInput.addEventListener("input", () => renderFields(searchInput.value));
document.querySelectorAll(".filter-pill").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".filter-pill").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    activeGroup = button.dataset.group;
    renderFields(searchInput.value);
  });
});
fieldsGrid.addEventListener("input", (event) => {
  const name = event.target.dataset.configName;
  if (!name) return;
  const field = configFields.find((item) => item.name === name);
  if (field) field.value = event.target.value;
  if (["n_gnbs", "n_ues", "sim_time_s", "dt_s"].includes(name)) {
    syncQuickControlsFromConfig();
  }
  renderScenarioSummary();
  renderTopologyStats();
});
document.querySelector("#repetitions").addEventListener("input", renderScenarioSummary);
quickGnbs.addEventListener("input", () => {
  syncConfigFromQuickControls();
  renderScenarioSummary();
  renderTopologyStats();
});
quickUes.addEventListener("input", () => {
  syncConfigFromQuickControls();
  renderScenarioSummary();
  renderTopologyStats();
});
quickSteps.addEventListener("input", () => {
  syncConfigFromQuickControls();
  renderScenarioSummary();
  renderTopologyStats();
});
document.querySelectorAll(".method-check").forEach((item) => item.addEventListener("change", renderScenarioSummary));
startBtn.addEventListener("click", startSimulation);
resetBtn.addEventListener("click", resetDefaults);
metricSelect.addEventListener("change", () => renderChart(lastState?.results?.summary || {}));
downloadBtn.addEventListener("click", downloadCsv);

loadConfig();
loadState();
