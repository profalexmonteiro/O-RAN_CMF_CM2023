import { numberValue } from "../config/formConfig.js";
import { presets } from "../config/presets.js";
import { switchTab } from "./dom.js";
import { setRunningButtons, updateLegend } from "./statusPanel.js";

export function bindControls({ getField, engine, renderer, refresh, history, comparison, setCompareMode }) {
    const reset = () => {
        engine.reset();
        history?.clear();
        setRunningButtons(false);
        updateLegend(getField);
        // Hide end-summary when resetting
        const endSection = document.getElementById("end-summary-section");
        if (endSection) endSection.hidden = true;
        refresh();
    };

    const toggleSimulation = () => {
        const running = engine.toggleRunning();
        setRunningButtons(running);
        if (running) switchTab("visual", () => renderer.resize());
        refresh();
    };

    const startComparison = () => {
        if (comparison.isRunning) return;
        // Hide any previous results first
        const section = document.getElementById("comparison-section");
        if (section) section.hidden = false;
        const resultsDiv = document.getElementById("comparison-results");
        if (resultsDiv) resultsDiv.hidden = true;
        const endSection = document.getElementById("end-summary-section");
        if (endSection) endSection.hidden = true;

        switchTab("visual", () => renderer.resize());

        comparison.start(
            (mode) => {
                setCompareMode(mode);
                engine.reset();
                history?.clear();
            },
            () => {
                engine.setRunning(true);
                setRunningButtons(true);
            },
        );
    };

    getField("start-button").addEventListener("click", toggleSimulation);
    getField("setup-start-button").addEventListener("click", toggleSimulation);
    getField("reset-button").addEventListener("click", reset);
    getField("tab-setup").addEventListener("click", () => switchTab("setup", () => renderer.resize()));
    getField("tab-visual").addEventListener("click", () => switchTab("visual", () => renderer.resize()));
    getField("setup-visual-shortcut").addEventListener("click", () => switchTab("visual", () => renderer.resize()));

    const compareBtn = document.getElementById("compare-button");
    if (compareBtn) compareBtn.addEventListener("click", startComparison);
    const compareSetupBtn = document.getElementById("compare-setup-button");
    if (compareSetupBtn) compareSetupBtn.addEventListener("click", startComparison);

    getField("preset").addEventListener("change", () => {
        const selected = presets[getField("preset").value] || presets.default;
        Object.entries(selected).forEach(([id, value]) => {
            if (getField(id)) getField(id).value = value;
        });
        reset();
    });

    document.querySelectorAll("#setup-panel input, #setup-panel select, #visual-panel input, #visual-panel select").forEach((field) => {
        if (["speed-scale", "color-scheme", "show-links", "preset"].includes(field.id)) return;
        field.addEventListener("change", () => {
            if (field.id === "users-per-bs") {
                getField("n-users").value = Math.max(10, Math.min(3000, Math.trunc(
                    numberValue(getField, "n-bs", 19) * numberValue(getField, "users-per-bs", 20),
                )));
            }
            reset();
        });
    });

    // Speed-scale shows current value in its label
    const speedInput = getField("speed-scale");
    const speedDisplay = document.getElementById("speed-scale-display");
    if (speedInput && speedDisplay) {
        const updateSpeed = () => { speedDisplay.textContent = `${speedInput.value}×`; };
        speedInput.addEventListener("input", updateSpeed);
        updateSpeed();
    }

    getField("color-scheme").addEventListener("change", () => {
        updateLegend(getField);
        refresh();
    });
    getField("show-links").addEventListener("change", refresh);
    window.addEventListener("resize", () => {
        renderer.resize();
        refresh();
    });

    reset();
}
