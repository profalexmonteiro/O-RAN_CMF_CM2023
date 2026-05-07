import { chooseGridStep, colorToCss, shapeColorForUser, worldToCanvas } from "./coordinates.js";

export class CanvasRenderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext("2d");
        this.ready = !!this.ctx;
        this.summary = this.ready ? "CPU Canvas 2D ativo" : "Renderização indisponível";
    }

    resize() {
        this.ctx = this.canvas.getContext("2d");
    }

    render(state, params) {
        if (!this.ready) return;
        const ctx = this.ctx;
        const bounds = state.bounds;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        ctx.fillStyle = "#f8fbff";
        ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        const span = Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY);
        const step = chooseGridStep(span);
        ctx.lineWidth = Math.max(1, this.canvas.width / 1280);
        ctx.strokeStyle = "rgba(209, 219, 233, 1)";
        ctx.beginPath();
        for (let x = Math.ceil(bounds.minX / step) * step; x <= bounds.maxX; x += step) {
            const a = worldToCanvas(this.canvas, bounds, x, bounds.minY);
            const b = worldToCanvas(this.canvas, bounds, x, bounds.maxY);
            ctx.moveTo(a[0], a[1]);
            ctx.lineTo(b[0], b[1]);
        }
        for (let y = Math.ceil(bounds.minY / step) * step; y <= bounds.maxY; y += step) {
            const a = worldToCanvas(this.canvas, bounds, bounds.minX, y);
            const b = worldToCanvas(this.canvas, bounds, bounds.maxX, y);
            ctx.moveTo(a[0], a[1]);
            ctx.lineTo(b[0], b[1]);
        }
        ctx.stroke();

        ctx.strokeStyle = "rgba(89, 125, 166, 1)";
        ctx.strokeRect(0.5, 0.5, this.canvas.width - 1, this.canvas.height - 1);

        if (params.showLinks) {
            ctx.strokeStyle = "rgba(59, 107, 158, 0.18)";
            ctx.beginPath();
            for (const user of state.users) {
                if (!user.connected || user.serving < 0) continue;
                const bs = state.bs[user.serving];
                const a = worldToCanvas(this.canvas, bounds, user.x, user.y);
                const b = worldToCanvas(this.canvas, bounds, bs.x, bs.y);
                ctx.moveTo(a[0], a[1]);
                ctx.lineTo(b[0], b[1]);
            }
            ctx.stroke();
        }

        for (const user of state.users) {
            const [x, y] = worldToCanvas(this.canvas, bounds, user.x, user.y);
            const radius = (user.connected ? 4.2 : 3.0) * Math.max(1, this.canvas.width / 1280);
            const color = user.connected ? shapeColorForUser(user, params) : [0.58, 0.64, 0.72, 0.6];
            ctx.fillStyle = colorToCss(color);
            ctx.beginPath();
            ctx.arc(x, y, radius, 0, Math.PI * 2);
            ctx.fill();
        }
    }
}
