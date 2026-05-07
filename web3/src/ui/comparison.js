const MODES = ["no_CM", "prio_MRO", "prio_MLB"];
const MODE_LABELS = { no_CM: "Sem CMF", prio_MRO: "Prioridade MRO", prio_MLB: "Prioridade MLB" };

export class ComparisonController {
    constructor() {
        this.results = [];
        this.currentIndex = -1;
        this._setMode = null;
        this._runSimulation = null;
        this.onProgress = null;   // (label, current, total) => void
        this.onComplete = null;   // (results) => void
    }

    get isRunning() {
        return this.currentIndex >= 0;
    }

    get currentModeLabel() {
        return this.isRunning ? MODE_LABELS[MODES[this.currentIndex]] : null;
    }

    start(setMode, runSimulation) {
        this._setMode = setMode;
        this._runSimulation = runSimulation;
        this.results = [];
        this.currentIndex = 0;
        this._launchCurrent();
    }

    // Called by the animation loop when a simulation completes (state.completed = true)
    onSimulationComplete(metrics) {
        if (!this.isRunning) return false;
        const mode = MODES[this.currentIndex];
        this.results.push({ mode, label: MODE_LABELS[mode], metrics: { ...metrics } });
        this.currentIndex++;
        if (this.currentIndex < MODES.length) {
            this._launchCurrent();
        } else {
            this.currentIndex = -1;
            this.onComplete?.(this.results);
        }
        return true;
    }

    _launchCurrent() {
        const mode = MODES[this.currentIndex];
        this._setMode(mode);
        this.onProgress?.(MODE_LABELS[mode], this.currentIndex + 1, MODES.length);
        this._runSimulation();
    }
}

const METRIC_DEFS = [
    { key: "satisfaction", label: "Satisfação", fmt: (v) => `${(v * 100).toFixed(1)}%`, higherBetter: true },
    { key: "handovers", label: "Handovers", fmt: (v) => Math.trunc(v).toLocaleString("pt-BR"), higherBetter: false },
    { key: "pingpong", label: "Ping-pong HOs", fmt: (v) => Math.trunc(v).toLocaleString("pt-BR"), higherBetter: false },
    { key: "rlf", label: "RLFs", fmt: (v) => Math.trunc(v).toLocaleString("pt-BR"), higherBetter: false },
    { key: "blocked", label: "Bloqueios (CB)", fmt: (v) => Math.trunc(v).toLocaleString("pt-BR"), higherBetter: false },
    { key: "avgLoad", label: "Load médio BS", fmt: (v) => `${(v * 100).toFixed(1)}%`, higherBetter: null },
];

export function renderComparisonTable(results) {
    if (!results || results.length === 0) return "";

    const baseMetrics = results[0].metrics;

    const headerCells = results.map((r) => `<th>${r.label}</th>`).join("");
    const rows = METRIC_DEFS.map((def) => {
        const values = results.map((r) => r.metrics[def.key] ?? 0);
        const base = values[0];
        const cells = values.map((v, i) => {
            const fmt = def.fmt(v);
            let arrow = "";
            if (i > 0 && def.higherBetter !== null) {
                const delta = v - base;
                const pct = base !== 0 ? (delta / base) * 100 : 0;
                if (Math.abs(pct) >= 0.5) {
                    const improved = delta > 0 ? def.higherBetter : !def.higherBetter;
                    arrow = improved
                        ? `<span class="cmp-arrow good">▲ ${Math.abs(pct).toFixed(1)}%</span>`
                        : `<span class="cmp-arrow bad">▼ ${Math.abs(pct).toFixed(1)}%</span>`;
                }
            }
            return `<td>${fmt}${arrow}</td>`;
        });
        return `<tr><td class="cmp-row-label">${def.label}</td>${cells.join("")}</tr>`;
    });

    return `
        <table class="cmp-table">
            <thead><tr><th>Indicador</th>${headerCells}</tr></thead>
            <tbody>${rows.join("")}</tbody>
        </table>`;
}

export function buildCsvFromResults(results) {
    const headers = ["Indicador", ...results.map((r) => r.label)];
    const rows = METRIC_DEFS.map((def) => [
        def.label,
        ...results.map((r) => {
            const v = r.metrics[def.key] ?? 0;
            return def.key === "satisfaction" || def.key === "avgLoad"
                ? (v * 100).toFixed(2)
                : Math.trunc(v).toString();
        }),
    ]);
    return [headers, ...rows].map((r) => r.join(",")).join("\n");
}
