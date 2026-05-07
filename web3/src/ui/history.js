// Stores time-series samples of simulation metrics for sparkline rendering.
// Samples are taken at most once per sampleInterval seconds to limit memory.
export class MetricsHistory {
    constructor(maxSamples = 250, sampleInterval = 2) {
        this.maxSamples = maxSamples;
        this.sampleInterval = sampleInterval;
        this.samples = [];
        this.lastSampleTime = -999;
    }

    maybeRecord(time, metrics) {
        if (time - this.lastSampleTime < this.sampleInterval) return;
        this.lastSampleTime = time;
        this.samples.push({ time, ...metrics });
        if (this.samples.length > this.maxSamples) this.samples.shift();
    }

    getSeries(key) {
        return this.samples.map((s) => s[key] ?? 0);
    }

    clear() {
        this.samples = [];
        this.lastSampleTime = -999;
    }
}

export function drawSparkline(canvas, data, color = "#457b9d") {
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    if (data.length < 2) return;

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    // Fill area under the line
    ctx.fillStyle = color + "22";
    ctx.beginPath();
    data.forEach((v, i) => {
        const x = (i / (data.length - 1)) * w;
        const y = h - ((v - min) / range) * (h - 4) - 2;
        if (i === 0) ctx.moveTo(x, h);
        ctx.lineTo(x, y);
    });
    ctx.lineTo(w, h);
    ctx.closePath();
    ctx.fill();

    // Draw the line
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = "round";
    ctx.beginPath();
    data.forEach((v, i) => {
        const x = (i / (data.length - 1)) * w;
        const y = h - ((v - min) / range) * (h - 4) - 2;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();
}
