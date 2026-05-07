import { readParams } from "./src/config/formConfig.js";
import { RendererManager } from "./src/rendering/rendererManager.js";
import { SimulationEngine } from "./src/simulation/engine.js";
import { ComparisonController, buildCsvFromResults, renderComparisonTable } from "./src/ui/comparison.js";
import { bindControls } from "./src/ui/controls.js";
import { $ } from "./src/ui/dom.js";
import { MetricsHistory } from "./src/ui/history.js";
import { setRunningButtons, updateCmfPanel, updateMetrics, updateRenderSummary } from "./src/ui/statusPanel.js";

const getField = (id) => $(id);
const readCurrentParams = () => readParams(getField);

const engine = new SimulationEngine(readCurrentParams);
const renderer = new RendererManager($("scene"), $("tower-layer"));
const history = new MetricsHistory();
const comparison = new ComparisonController();

// ── Comparison UI helpers ────────────────────────────────────────────────────

function setCompareMode(mode) {
    const field = getField("cmf-mode");
    if (field) field.value = mode;
}

function showComparisonProgress(label, current, total) {
    const section = document.getElementById("comparison-section");
    const progressDiv = document.getElementById("comparison-progress");
    const statusText = document.getElementById("comparison-status-text");
    const fill = document.getElementById("comparison-progress-fill");
    const resultsDiv = document.getElementById("comparison-results");
    if (!section) return;
    section.hidden = false;
    progressDiv.hidden = false;
    if (resultsDiv) resultsDiv.hidden = true;
    if (statusText) statusText.textContent = `Rodando modo ${current}/${total}: ${label}…`;
    if (fill) fill.style.width = `${((current - 1) / total) * 100}%`;
}

function showComparisonResults(results) {
    const progressDiv = document.getElementById("comparison-progress");
    const fill = document.getElementById("comparison-progress-fill");
    const resultsDiv = document.getElementById("comparison-results");
    if (progressDiv) progressDiv.hidden = true;
    if (fill) fill.style.width = "100%";
    if (!resultsDiv) return;
    resultsDiv.hidden = false;
    resultsDiv.innerHTML = renderComparisonTable(results);

    const exportBtn = document.getElementById("export-csv-button");
    if (exportBtn) {
        exportBtn.onclick = () => {
            const csv = buildCsvFromResults(results);
            const blob = new Blob([csv], { type: "text/csv" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "oran-cmf-comparison.csv";
            a.click();
            URL.revokeObjectURL(url);
        };
    }
}

let comparisonJustFinished = false;
comparison.onProgress = showComparisonProgress;
comparison.onComplete = (results) => {
    comparisonJustFinished = true;
    showComparisonResults(results);
    setRunningButtons(false);
};

// ── Main loop ────────────────────────────────────────────────────────────────

function refresh() {
    const params = readCurrentParams();
    history.maybeRecord(engine.state.time, engine.state.metrics);
    updateMetrics(engine.state, params, history);
    updateCmfPanel(engine.state, params);
    renderer.render(engine.state, params);
}

let prevRunning = false;

function animationLoop(now) {
    engine.frame(now);

    const justFinished = prevRunning && !engine.state.running && engine.state.completed;
    prevRunning = engine.state.running;

    if (justFinished) {
        if (comparison.isRunning) {
            comparison.onSimulationComplete(engine.state.metrics);
        }
        // Show per-run summary only for standalone runs (not inside comparison)
        const showSummary = !comparison.isRunning && !comparisonJustFinished;
        comparisonJustFinished = false;
        if (showSummary) {
            const section = document.getElementById("end-summary-section");
            if (section) showEndSummary(engine.state.metrics, readCurrentParams());
        }
    }

    setRunningButtons(engine.state.running);
    refresh();
    requestAnimationFrame(animationLoop);
}

function showEndSummary(metrics, params) {
    const section = document.getElementById("end-summary-section");
    if (!section) return;
    section.hidden = false;
    const label = { no_CM: "Sem CMF", prio_MRO: "Prioridade MRO", prio_MLB: "Prioridade MLB" }[params.cmfMode] ?? params.cmfMode;
    section.innerHTML = `
        <div class="end-summary-card">
            <h3>Resumo — ${label}</h3>
            <table class="cmp-table">
                <tbody>
                    <tr><td>Satisfação média</td><td>${(metrics.satisfaction * 100).toFixed(1)}%</td></tr>
                    <tr><td>Handovers</td><td>${Math.trunc(metrics.handovers).toLocaleString("pt-BR")}</td></tr>
                    <tr><td>Ping-pong HOs</td><td>${Math.trunc(metrics.pingpong).toLocaleString("pt-BR")}</td></tr>
                    <tr><td>RLFs</td><td>${Math.trunc(metrics.rlf).toLocaleString("pt-BR")}</td></tr>
                    <tr><td>Bloqueios (CB)</td><td>${Math.trunc(metrics.blocked).toLocaleString("pt-BR")}</td></tr>
                    <tr><td>Load médio BS</td><td>${(metrics.avgLoad * 100).toFixed(1)}%</td></tr>
                </tbody>
            </table>
        </div>`;
}

async function main() {
    bindControls({
        getField,
        engine,
        renderer,
        refresh,
        history,
        comparison,
        setCompareMode,
        showComparisonProgress,
    });
    renderer.resize();
    updateRenderSummary(await renderer.init());
    renderer.resize();
    refresh();
    requestAnimationFrame(animationLoop);
}

main();
