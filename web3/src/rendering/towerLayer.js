import { worldToCanvas } from "./coordinates.js";

// Maps a BS load [0,1] to an RGB color: green (low) → yellow → red (high)
function loadColor(load) {
    const t = Math.min(Math.max(load, 0), 1);
    if (t < 0.5) {
        const r = Math.round(t * 2 * 220);
        return `rgb(${r}, 180, 40)`;
    }
    const r = 220;
    const g = Math.round(180 * (1 - (t - 0.5) * 2));
    return `rgb(${r}, ${g}, 40)`;
}

export class TowerLayer {
    constructor(canvas, sceneCanvas, imageSrc) {
        this.canvas = canvas;
        this.sceneCanvas = sceneCanvas;
        this.image = new Image();
        this.image.src = imageSrc;
    }

    resize() {
        if (this.canvas.width !== this.sceneCanvas.width || this.canvas.height !== this.sceneCanvas.height) {
            this.canvas.width = this.sceneCanvas.width;
            this.canvas.height = this.sceneCanvas.height;
        }
    }

    render(state) {
        this.resize();
        const ctx = this.canvas.getContext("2d");
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        const scale = Math.max(0.75, this.canvas.width / 1280);
        const iconW = 36 * scale;
        const iconH = 48 * scale;
        const ringR = 18 * scale;
        const fontSize = Math.round(11 * scale);

        for (const bs of state.bs) {
            const [x, y] = worldToCanvas(this.canvas, state.bounds, bs.x, bs.y);
            const color = loadColor(bs.load);

            // Load ring: colored filled circle behind the tower icon
            ctx.save();
            ctx.beginPath();
            ctx.arc(x, y - 10 * scale, ringR, 0, Math.PI * 2);
            ctx.fillStyle = color + "55";
            ctx.fill();
            ctx.strokeStyle = color;
            ctx.lineWidth = 2 * scale;
            ctx.stroke();
            ctx.restore();

            // Tower icon with subtle shadow
            if (this.image.complete && this.image.naturalWidth > 0) {
                ctx.save();
                ctx.shadowColor = `rgba(0,0,0,0.25)`;
                ctx.shadowBlur = 6 * scale;
                ctx.drawImage(this.image, x - iconW / 2, y - iconH + 9 * scale, iconW, iconH);
                ctx.restore();
            }

            // CIO label (shown when MLB has adjusted it away from 0)
            const cio = bs.cio ?? 0;
            if (Math.abs(cio) >= 0.5) {
                const sign = cio > 0 ? "+" : "";
                const label = `CIO ${sign}${cio.toFixed(1)}`;
                ctx.save();
                ctx.font = `bold ${fontSize}px Inter, Arial, sans-serif`;
                ctx.textAlign = "center";
                const textW = ctx.measureText(label).width + 6 * scale;
                const badgeH = fontSize + 6 * scale;
                const bx = x - textW / 2;
                const by = y + 6 * scale;
                ctx.fillStyle = cio > 0 ? "#1d6b3a" : "#9a1c1c";
                ctx.beginPath();
                if (ctx.roundRect) {
                    ctx.roundRect(bx, by, textW, badgeH, 3 * scale);
                } else {
                    ctx.rect(bx, by, textW, badgeH);
                }
                ctx.fill();
                ctx.fillStyle = "#fff";
                ctx.fillText(label, x, by + badgeH - 4 * scale);
                ctx.restore();
            }

            // Load percentage label
            ctx.save();
            ctx.font = `${Math.round(10 * scale)}px Inter, Arial, sans-serif`;
            ctx.textAlign = "center";
            ctx.fillStyle = "#334155";
            ctx.fillText(`${Math.round(bs.load * 100)}%`, x, y + (ringR + fontSize + 2) * scale);
            ctx.restore();
        }
    }
}
