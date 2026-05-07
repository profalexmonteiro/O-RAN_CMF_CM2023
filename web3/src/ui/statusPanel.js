import { configuredProfiles } from "../config/formConfig.js";
import { drawSparkline } from "./history.js";

const CMF_MODE_LABELS = {
    no_CM: "Sem CMF",
    prio_MRO: "Prioridade MRO",
    prio_MLB: "Prioridade MLB",
};

export function setRunningButtons(running) {
    const label = running ? "Parar Simulação" : "Iniciar Simulação";
    for (const id of ["start-button", "setup-start-button"]) {
        const btn = document.getElementById(id);
        if (!btn) continue;
        btn.textContent = label;
        btn.classList.toggle("running", running);
    }
}

export function updateMetrics(state, params, history) {
    const { time, metrics } = state;
    const inWarmup = time < params.statisticsIgnoreInitial && time < params.simTime;

    // Progress bar
    const simTime = params.simTime || 1;
    const warmupFrac = Math.min(params.statisticsIgnoreInitial / simTime, 1);
    const activeFrac = Math.max(0, Math.min((time - params.statisticsIgnoreInitial) / simTime, 1 - warmupFrac));
    const el = (id) => document.getElementById(id);

    const warmupSeg = el("progress-warmup-seg");
    const activeSeg = el("progress-active-seg");
    if (warmupSeg) warmupSeg.style.width = `${warmupFrac * 100}%`;
    if (activeSeg) activeSeg.style.width = `${activeFrac * 100}%`;

    const phaseLabel = el("progress-phase-label");
    if (phaseLabel) {
        if (inWarmup) {
            phaseLabel.textContent = `Aquecimento — ${time.toFixed(0)} / ${params.statisticsIgnoreInitial} s`;
            phaseLabel.className = "phase-badge warmup";
        } else {
            phaseLabel.textContent = state.running ? "Simulação ativa" : (state.completed ? "Concluída" : "Pausada");
            phaseLabel.className = `phase-badge ${state.completed ? "done" : "active"}`;
        }
    }
    const timeText = el("progress-time-text");
    if (timeText) timeText.textContent = `${time.toFixed(1)} / ${simTime.toFixed(0)} s`;

    // Metric values (dim during warm-up)
    const opacity = inWarmup ? "0.45" : "1";
    const metricsEl = document.querySelector(".metrics");
    if (metricsEl) metricsEl.style.opacity = opacity;

    el("metric-time").textContent = `${time.toFixed(1)} s`;
    el("metric-connected").textContent = metrics.connected.toString();
    el("metric-satisfaction").textContent = `${(metrics.satisfaction * 100).toFixed(1)}%`;
    el("metric-handovers").textContent = Math.trunc(metrics.handovers).toLocaleString("pt-BR");
    el("metric-pingpong").textContent = Math.trunc(metrics.pingpong).toLocaleString("pt-BR");
    el("metric-rlf").textContent = Math.trunc(metrics.rlf).toLocaleString("pt-BR");
    el("metric-blocked").textContent = Math.trunc(metrics.blocked).toLocaleString("pt-BR");
    el("metric-load").textContent = `${(metrics.avgLoad * 100).toFixed(1)}%`;

    el("status-message").textContent = state.running
        ? "Executando no navegador."
        : state.completed ? "Simulação concluída." : "Aguardando início.";
    el("scenario-summary").textContent =
        `${params.nBs} BS · ${params.nUsers} UEs · ${CMF_MODE_LABELS[params.cmfMode] ?? params.cmfMode} · ${params.bandwidthMhz} MHz`;

    // Sparklines
    if (history) {
        const sparkDefs = [
            { id: "spark-connected", key: "connected", color: "#457b9d" },
            { id: "spark-satisfaction", key: "satisfaction", color: "#16a34a" },
            { id: "spark-handovers", key: "handovers", color: "#7c3aed" },
            { id: "spark-pingpong", key: "pingpong", color: "#b45309" },
            { id: "spark-rlf", key: "rlf", color: "#dc2626" },
            { id: "spark-blocked", key: "blocked", color: "#c2410c" },
            { id: "spark-load", key: "avgLoad", color: "#0369a1" },
        ];
        for (const { id, key, color } of sparkDefs) {
            const canvas = el(id);
            if (canvas) drawSparkline(canvas, history.getSeries(key), color);
        }
    }
}

export function updateCmfPanel(state, params) {
    const ric = state.nearRtRic;
    if (!ric) return;
    const act = ric.lastActivity;
    const el = (id) => document.getElementById(id);

    const modeLabel = el("cmf-mode-label");
    if (modeLabel) modeLabel.textContent = `Modo: ${CMF_MODE_LABELS[params.cmfMode] ?? params.cmfMode}`;

    // xApp status badges
    const xappsRow = el("cmf-xapps-row");
    if (xappsRow) {
        const mode = params.cmfMode;
        const mroActive = mode !== "prio_MLB";
        const mlbActive = mode !== "prio_MRO";
        xappsRow.innerHTML = `
            <span class="xapp-badge ${mroActive ? "xapp-high" : "xapp-blocked"}">
                MRO ${mroActive ? (mode === "prio_MRO" ? "★ alta" : "normal") : "bloqueado"}
            </span>
            <span class="xapp-badge ${mlbActive ? "xapp-high" : "xapp-blocked"}">
                MLB ${mlbActive ? (mode === "prio_MLB" ? "★ alta" : "normal") : "bloqueado"}
            </span>`;
    }

    if (act.cycleTime < 0) return;
    const setText = (id, val) => { const e = el(id); if (e) e.textContent = val; };
    setText("cmf-cycle-time", `t = ${act.cycleTime.toFixed(0)} s`);
    setText("cmf-conflicts", act.conflictsDetected > 0 ? `${act.conflictsDetected} detectados` : "Nenhum");
    setText("cmf-blocked",
        act.decisionsBlocked > 0
            ? `${act.decisionsBlocked} (${params.cmfMode === "prio_MRO" ? "MLB" : params.cmfMode === "prio_MLB" ? "MRO" : "—"})`
            : "Nenhuma");
    setText("cmf-avg-ttt",
        act.avgTtt !== null ? `${(act.avgTtt * 1000).toFixed(1)} ms` : `${(params.ttt * 1000).toFixed(1)} ms (global)`);
    setText("cmf-avg-hys",
        act.avgHys !== null ? `${act.avgHys.toFixed(2)} dB` : `${params.hysteresis.toFixed(2)} dB (global)`);
    setText("cmf-avg-cio", `${act.avgCio.toFixed(2)} dB`);
}

export function updateRenderSummary(summary) {
    document.getElementById("gpu-status").textContent = summary;
    document.getElementById("render-summary").textContent = summary;
    const fallback = document.getElementById("fallback-message");
    fallback.textContent = "";
    fallback.hidden = true;
}

export function updateLegend(getField) {
    const legend = document.getElementById("legend");
    if (getField("color-scheme").value === "mobility") {
        legend.innerHTML = `
            <span><i class="dot vehicle"></i>Carros: azul</span>
            <span><i class="dot pedestrian"></i>Pedestres: vermelho</span>
            <span><i class="tower"></i>Antena (BS)</span>
        `;
        return;
    }
    const profiles = configuredProfiles(getField);
    const label = (p) => `${p.bitrateKbps.toFixed(0)} kbps (${(p.probability * 100).toFixed(0)}%)`;
    legend.innerHTML = `
        <span><i class="dot low"></i>Low bitrate: ${label(profiles[0])}</span>
        <span><i class="dot medium"></i>Medium bitrate: ${label(profiles[1])}</span>
        <span><i class="dot high"></i>High bitrate: ${label(profiles[2])}</span>
        <span><i class="tower"></i>Antena (BS) — cor indica carga</span>
    `;
}
