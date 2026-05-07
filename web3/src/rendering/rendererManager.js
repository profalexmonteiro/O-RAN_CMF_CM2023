import { CanvasRenderer } from "./canvasRenderer.js";
import { TowerLayer } from "./towerLayer.js";
import { WebGpuRenderer } from "./webgpuRenderer.js";

export class RendererManager {
    constructor(sceneCanvas, towerCanvas) {
        this.sceneCanvas = sceneCanvas;
        this.towerLayer = new TowerLayer(towerCanvas, sceneCanvas, "assets/cell-tower.svg");
        this.activeRenderer = null;
    }

    async init() {
        const webgpu = new WebGpuRenderer(this.sceneCanvas);
        if (await webgpu.init()) {
            this.activeRenderer = webgpu;
        } else {
            this.activeRenderer = new CanvasRenderer(this.sceneCanvas);
        }
        return this.summary;
    }

    get summary() {
        return this.activeRenderer?.summary || "Inicializando renderização";
    }

    resize() {
        const rect = this.sceneCanvas.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return false;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const width = Math.max(1, Math.floor(rect.width * dpr));
        const height = Math.max(1, Math.floor(rect.height * dpr));
        if (this.sceneCanvas.width === width && this.sceneCanvas.height === height) return false;
        this.sceneCanvas.width = width;
        this.sceneCanvas.height = height;
        this.towerLayer.resize();
        this.activeRenderer?.resize();
        return true;
    }

    render(state, params) {
        if (!this.activeRenderer) return;
        this.activeRenderer.render(state, params);
        this.towerLayer.render(state);
    }
}
