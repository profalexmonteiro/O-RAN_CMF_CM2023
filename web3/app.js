const $ = (id) => document.getElementById(id);

const presets = {
    default: { "n-bs": 19, "users-per-bs": 20, "n-users": 380, isd: 600, "pedestrian-prob": 80, "pedestrian-speed": 5, "vehicle-speed": 25, "turn-prob": 1.2, hysteresis: 0, ttt: 0.064 },
    handover: { "n-bs": 19, "users-per-bs": 22, "n-users": 420, isd: 450, "pedestrian-prob": 35, "pedestrian-speed": 4, "vehicle-speed": 36, hysteresis: 0.5, ttt: 0.05, "pingpong-period": 8 },
    density: { "n-bs": 19, "users-per-bs": 47, "n-users": 900, isd: 500, "pedestrian-prob": 75, "pedestrian-speed": 5, "vehicle-speed": 22, hysteresis: 1.5, ttt: 0.15 },
    wide: { "n-bs": 19, "users-per-bs": 16, "n-users": 300, isd: 900, "pedestrian-prob": 90, "pedestrian-speed": 4, "vehicle-speed": 18, hysteresis: 3, ttt: 0.35 },
};

const defaultProfiles = [
    { name: "low", bitrateKbps: 96, probability: 0.60, color: [0.086, 0.639, 0.290, 1] },
    { name: "medium", bitrateKbps: 5000, probability: 0.30, color: [0.918, 0.702, 0.031, 1] },
    { name: "high", bitrateKbps: 24000, probability: 0.10, color: [0.863, 0.149, 0.149, 1] },
];

const gpu = {
    ready: false,
    device: null,
    context: null,
    format: null,
    shapePipeline: null,
    linePipeline: null,
    shapeBuffer: null,
    lineBuffer: null,
    maxShapes: 4096,
    maxLineVertices: 24000,
};

const cpu = {
    ready: false,
    ctx: null,
};

const towerImage = new Image();
towerImage.src = "assets/cell-tower.svg";

const sim = {
    running: false,
    time: 0,
    lastFrameTime: 0,
    bounds: { minX: -1000, maxX: 1000, minY: -1000, maxY: 1000 },
    bs: [],
    users: [],
    metrics: {
        connected: 0,
        satisfaction: 0,
        handovers: 0,
        pingpong: 0,
        rlf: 0,
        blocked: 0,
        avgLoad: 0,
    },
};

function numberValue(id, fallback) {
    const field = $(id);
    if (!field) return fallback;
    const value = Number(field.value);
    return Number.isFinite(value) ? value : fallback;
}

function configuredProfiles() {
    const profiles = defaultProfiles.map((profile) => ({
        ...profile,
        bitrateKbps: Math.max(1, numberValue(`${profile.name}-bitrate`, profile.bitrateKbps)),
        probability: Math.max(0, numberValue(`${profile.name}-prob`, profile.probability * 100)),
    }));
    const total = profiles.reduce((sum, profile) => sum + profile.probability, 0);
    if (total <= 0) return defaultProfiles;
    return profiles.map((profile) => ({ ...profile, probability: profile.probability / total }));
}

function params() {
    const nBs = Math.max(1, Math.min(61, Math.trunc(numberValue("n-bs", 19))));
    const usersPerBs = Math.max(1, Math.trunc(numberValue("users-per-bs", 20)));
    return {
        nBs,
        usersPerBs,
        nUsers: Math.max(10, Math.min(3000, Math.trunc(numberValue("n-users", nBs * usersPerBs)))),
        isd: Math.max(100, numberValue("isd", 600)),
        areaMarginFactor: Math.max(0.1, numberValue("area-margin-factor", 1.5)),
        simTime: Math.max(1, numberValue("sim-time", 1000)),
        dt: Math.max(0.01, numberValue("dt", 0.05)),
        speedScale: numberValue("speed-scale", 1),
        pedestrianProb: Math.max(0, Math.min(1, numberValue("pedestrian-prob", 80) / 100)),
        pedestrianSpeed: Math.max(0, numberValue("pedestrian-speed", 5)),
        vehicleSpeed: Math.max(0, numberValue("vehicle-speed", 25)),
        turnProb: Math.max(0, numberValue("turn-prob", 1.2) / 100),
        txPower: numberValue("tx-power", 28),
        bsAntennaGain: numberValue("bs-antenna-gain", 2),
        bsHeight: Math.max(1, numberValue("bs-height", 10)),
        bsCableLoss: Math.max(0, numberValue("bs-cable-loss", 2)),
        frequency: Math.max(600, numberValue("frequency", 2100)),
        bandwidthMhz: Math.max(1, numberValue("bandwidth-mhz", 20)),
        subcarrierCount: Math.max(1, Math.trunc(numberValue("subcarrier-count", 12))),
        subcarrierSpacingKhz: Math.max(1, numberValue("subcarrier-spacing-khz", 15)),
        defaultCio: numberValue("default-cio", 0),
        rxSensitivity: numberValue("rx-sensitivity", -110),
        rxSensitivityMargin: numberValue("rx-sensitivity-margin", 0),
        hysteresis: Math.max(0, numberValue("hysteresis", 0)),
        ttt: Math.max(0, numberValue("ttt", 0.064)),
        ueAntennaGain: numberValue("ue-antenna-gain", 0),
        ueHeight: Math.max(0.1, numberValue("ue-height", 1.6)),
        ueCableLoss: Math.max(0, numberValue("ue-cable-loss", 0)),
        ueMimoLayers: Math.max(1, Math.trunc(numberValue("ue-mimo-layers", 2))),
        connectionAttemptMean: Math.max(0.1, numberValue("connection-attempt-mean", 20)),
        connectionAttemptStd: Math.max(0, numberValue("connection-attempt-std", 3)),
        connectionDurationMean: Math.max(0.1, numberValue("connection-duration-mean", 60)),
        connectionDurationStd: Math.max(0, numberValue("connection-duration-std", 15)),
        bodyLoss: numberValue("body-loss", 1),
        slowFadingMargin: numberValue("slow-fading-margin", 4),
        foliageLoss: numberValue("foliage-loss", 4),
        interferenceMargin: numberValue("interference-margin", 2),
        rainMargin: numberValue("rain-margin", 0),
        noiseFigure: numberValue("noise-figure", 7),
        thermalNoise: numberValue("thermal-noise", -174),
        prbBandwidthKhz: Math.max(1, numberValue("prb-bandwidth-khz", 180)),
        ricControlPeriod: Math.max(0.1, numberValue("ric-control-period", 10)),
        mroWindow: Math.max(1, numberValue("mro-window", 240)),
        pingpongPeriod: Math.max(0.1, numberValue("pingpong-period", 10)),
        statisticsIgnoreInitial: Math.max(0, numberValue("statistics-ignore-initial", 150)),
        rlfSinrThreshold: numberValue("rlf-sinr-threshold", -6),
        rlfRsrpThreshold: numberValue("rlf-rsrp-threshold", -110),
        cmfMode: $("cmf-mode")?.value || "no_CM",
        profiles: configuredProfiles(),
        colorScheme: $("color-scheme")?.value || "bitrate",
        showLinks: $("show-links")?.checked ?? true,
    };
}

function randomBetween(min, max) {
    return min + Math.random() * (max - min);
}

function sampleProfile(profiles) {
    const value = Math.random();
    let acc = 0;
    for (const profile of profiles) {
        acc += profile.probability;
        if (value <= acc) return profile;
    }
    return profiles[profiles.length - 1];
}

function generateBaseStations(count, isd) {
    const coords = [];
    let rings = 0;
    while (1 + 3 * rings * (rings + 1) < count) rings += 1;

    for (let q = -rings; q <= rings; q += 1) {
        for (let r = -rings; r <= rings; r += 1) {
            const s = -q - r;
            if (Math.max(Math.abs(q), Math.abs(r), Math.abs(s)) <= rings) {
                coords.push({
                    x: isd * Math.sqrt(3) * (q + r / 2),
                    y: isd * 1.5 * r,
                });
            }
        }
    }

    return coords
        .sort((a, b) => (a.x * a.x + a.y * a.y) - (b.x * b.x + b.y * b.y) || a.y - b.y || a.x - b.x)
        .slice(0, count)
        .sort((a, b) => a.y - b.y || a.x - b.x)
        .map((point, index) => ({ id: index + 1, x: point.x, y: point.y, load: 0, usedPrbs: 0 }));
}

function computeBounds(bs, isd, marginFactor) {
    const xs = bs.map((b) => b.x);
    const ys = bs.map((b) => b.y);
    const margin = Math.max(isd * marginFactor, 500);
    return {
        minX: Math.min(...xs) - margin,
        maxX: Math.max(...xs) + margin,
        minY: Math.min(...ys) - margin,
        maxY: Math.max(...ys) + margin,
    };
}

function resetSimulation() {
    const p = params();
    sim.running = false;
    sim.time = 0;
    sim.lastFrameTime = performance.now();
    sim.metrics = { connected: 0, satisfaction: 0, handovers: 0, pingpong: 0, rlf: 0, blocked: 0, avgLoad: 0 };
    sim.bs = generateBaseStations(p.nBs, p.isd);
    sim.bounds = computeBounds(sim.bs, p.isd, p.areaMarginFactor);
    sim.users = Array.from({ length: p.nUsers }, (_, id) => {
        const isPedestrian = Math.random() < p.pedestrianProb;
        const speed = isPedestrian ? p.pedestrianSpeed : p.vehicleSpeed;
        const angle = Math.random() * Math.PI * 2;
        const profile = sampleProfile(p.profiles);
        return {
            id,
            x: randomBetween(sim.bounds.minX, sim.bounds.maxX),
            y: randomBetween(sim.bounds.minY, sim.bounds.maxY),
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            speed,
            mobility: isPedestrian ? "pedestrian" : "vehicle",
            profile,
            connected: false,
            serving: -1,
            previousServing: -1,
            candidate: -1,
            ttt: 0,
            lastHandoverTime: -999,
            satisfaction: 0,
        };
    });
    setRunning(false);
    updateLegend();
    updateMetrics();
}

function setRunning(running) {
    sim.running = running;
    $("start-button").textContent = sim.running ? "Parar Simulação" : "Iniciar Simulação";
    $("setup-start-button").textContent = sim.running ? "Parar Simulação" : "Iniciar Simulação";
    $("start-button").classList.toggle("running", sim.running);
    $("setup-start-button").classList.toggle("running", sim.running);
    sim.lastFrameTime = performance.now();
}

function pathlossDb(distanceM, frequencyMhz) {
    const dKm = Math.max(distanceM / 1000, 0.001);
    return 32.4 + 20 * Math.log10(frequencyMhz) + 30 * Math.log10(dKm);
}

function signalDbm(user, bs, p) {
    const horizontalDistance = Math.hypot(user.x - bs.x, user.y - bs.y);
    const distance = Math.hypot(horizontalDistance, p.bsHeight - p.ueHeight);
    const loadPenalty = bs.load * 8;
    const gains = p.bsAntennaGain + p.ueAntennaGain;
    const losses = p.bsCableLoss + p.ueCableLoss + p.bodyLoss + p.slowFadingMargin + p.foliageLoss + p.interferenceMargin + p.rainMargin;
    return p.txPower + gains - losses - pathlossDb(distance, p.frequency) - loadPenalty;
}

function bestServer(user, p) {
    let best = -1;
    let bestSignal = -Infinity;
    let currentSignal = -Infinity;
    for (let i = 0; i < sim.bs.length; i += 1) {
        const signal = signalDbm(user, sim.bs[i], p);
        if (i === user.serving) currentSignal = signal;
        if (signal > bestSignal) {
            best = i;
            bestSignal = signal;
        }
    }
    return { best, bestSignal, currentSignal };
}

function bounceUser(user) {
    if (user.x < sim.bounds.minX || user.x > sim.bounds.maxX) {
        user.x = Math.max(sim.bounds.minX, Math.min(sim.bounds.maxX, user.x));
        user.vx *= -1;
    }
    if (user.y < sim.bounds.minY || user.y > sim.bounds.maxY) {
        user.y = Math.max(sim.bounds.minY, Math.min(sim.bounds.maxY, user.y));
        user.vy *= -1;
    }
}

function maybeTurn(user, p, dt) {
    if (Math.random() > p.turnProb * dt) return;
    const angle = Math.atan2(user.vy, user.vx) + randomBetween(-0.9, 0.9);
    user.vx = Math.cos(angle) * user.speed;
    user.vy = Math.sin(angle) * user.speed;
}

function stepSimulation(dt) {
    const p = params();
    const scaledDt = Math.min(dt * p.speedScale, p.dt);
    const totalPrbs = Math.max(1, Math.floor((p.bandwidthMhz * 1000) / p.prbBandwidthKhz));
    const prbThroughputKbps = Math.max(1, 450 * p.ueMimoLayers);
    const rlfRsrpThreshold = Math.max(p.rxSensitivity - p.rxSensitivityMargin, p.rlfRsrpThreshold);
    const noiseFloorDbm = p.thermalNoise + 10 * Math.log10(p.bandwidthMhz * 1_000_000) + p.noiseFigure;
    sim.time += scaledDt;
    sim.bs.forEach((bs) => {
        bs.usedPrbs = 0;
    });

    for (const user of sim.users) {
        user.x += user.vx * scaledDt;
        user.y += user.vy * scaledDt;
        bounceUser(user);
        maybeTurn(user, p, scaledDt);

        const { best, bestSignal, currentSignal } = bestServer(user, p);
        const sinrDb = bestSignal - noiseFloorDbm - p.interferenceMargin;
        if (bestSignal < rlfRsrpThreshold || sinrDb < p.rlfSinrThreshold) {
            if (user.connected) sim.metrics.rlf += 1;
            user.connected = false;
            user.serving = -1;
            user.satisfaction = 0;
            continue;
        }

        if (!user.connected) {
            user.connected = true;
            user.serving = best;
            user.candidate = -1;
            user.ttt = 0;
        } else if (best !== user.serving && bestSignal > currentSignal + p.hysteresis) {
            if (user.candidate !== best) {
                user.candidate = best;
                user.ttt = 0;
            }
            user.ttt += scaledDt;
            if (user.ttt >= p.ttt) {
                if (user.previousServing === best && sim.time - user.lastHandoverTime <= p.pingpongPeriod) sim.metrics.pingpong += 1;
                user.previousServing = user.serving;
                user.serving = best;
                user.lastHandoverTime = sim.time;
                user.candidate = -1;
                user.ttt = 0;
                sim.metrics.handovers += 1;
            }
        } else {
            user.candidate = -1;
            user.ttt = 0;
        }

        const serving = sim.bs[user.serving];
        const demandPrbs = Math.max(1, Math.ceil(user.profile.bitrateKbps / prbThroughputKbps));
        const availablePrbs = Math.max(0, totalPrbs - serving.usedPrbs);
        if (availablePrbs >= demandPrbs) {
            serving.usedPrbs += demandPrbs;
            user.satisfaction = 1;
        } else {
            serving.usedPrbs += availablePrbs;
            user.satisfaction = availablePrbs / demandPrbs;
            sim.metrics.blocked += scaledDt * 0.4;
        }
    }

    sim.bs.forEach((bs) => {
        bs.load = Math.min(bs.usedPrbs / totalPrbs, 1);
    });

    const connectedUsers = sim.users.filter((u) => u.connected);
    sim.metrics.connected = connectedUsers.length;
    sim.metrics.satisfaction = connectedUsers.length
        ? connectedUsers.reduce((sum, u) => sum + u.satisfaction, 0) / connectedUsers.length
        : 0;
    sim.metrics.avgLoad = sim.bs.length
        ? sim.bs.reduce((sum, bs) => sum + bs.load, 0) / sim.bs.length
        : 0;

    if (sim.time >= p.simTime) {
        setRunning(false);
        sim.time = p.simTime;
    }
}

function worldToClip(x, y) {
    const width = sim.bounds.maxX - sim.bounds.minX;
    const height = sim.bounds.maxY - sim.bounds.minY;
    return [
        ((x - sim.bounds.minX) / width) * 1.82 - 0.91,
        ((y - sim.bounds.minY) / height) * 1.82 - 0.91,
    ];
}

function worldToCanvas(x, y) {
    const canvas = $("scene");
    const width = sim.bounds.maxX - sim.bounds.minX;
    const height = sim.bounds.maxY - sim.bounds.minY;
    return [
        ((x - sim.bounds.minX) / width) * canvas.width,
        canvas.height - ((y - sim.bounds.minY) / height) * canvas.height,
    ];
}

function colorToCss(color) {
    const r = Math.round(color[0] * 255);
    const g = Math.round(color[1] * 255);
    const b = Math.round(color[2] * 255);
    const a = color[3] ?? 1;
    return `rgba(${r}, ${g}, ${b}, ${a})`;
}

function shapeColorForUser(user, p) {
    if (p.colorScheme === "mobility") {
        return user.mobility === "vehicle"
            ? [0.145, 0.388, 0.922, 1]
            : [0.863, 0.149, 0.149, 1];
    }
    return user.profile.color;
}

function pushShape(out, x, y, radiusX, radiusY, color, shape) {
    out.push(x, y, radiusX, radiusY, color[0], color[1], color[2], color[3], shape, 0);
}

function pushLine(out, x1, y1, c1, x2, y2, c2 = c1) {
    out.push(x1, y1, c1[0], c1[1], c1[2], c1[3], x2, y2, c2[0], c2[1], c2[2], c2[3]);
}

function buildRenderData() {
    const p = params();
    const shapes = [];
    const lines = [];
    const canvas = $("scene");
    const sx = 2 / Math.max(canvas.width, 1);
    const sy = 2 / Math.max(canvas.height, 1);

    const gridColor = [0.82, 0.87, 0.93, 1];
    const areaColor = [0.35, 0.49, 0.65, 1];
    const step = chooseGridStep(Math.max(sim.bounds.maxX - sim.bounds.minX, sim.bounds.maxY - sim.bounds.minY));
    for (let x = Math.ceil(sim.bounds.minX / step) * step; x <= sim.bounds.maxX; x += step) {
        const a = worldToClip(x, sim.bounds.minY);
        const b = worldToClip(x, sim.bounds.maxY);
        pushLine(lines, a[0], a[1], gridColor, b[0], b[1]);
    }
    for (let y = Math.ceil(sim.bounds.minY / step) * step; y <= sim.bounds.maxY; y += step) {
        const a = worldToClip(sim.bounds.minX, y);
        const b = worldToClip(sim.bounds.maxX, y);
        pushLine(lines, a[0], a[1], gridColor, b[0], b[1]);
    }

    const corners = [
        worldToClip(sim.bounds.minX, sim.bounds.minY),
        worldToClip(sim.bounds.maxX, sim.bounds.minY),
        worldToClip(sim.bounds.maxX, sim.bounds.maxY),
        worldToClip(sim.bounds.minX, sim.bounds.maxY),
    ];
    for (let i = 0; i < corners.length; i += 1) {
        const a = corners[i];
        const b = corners[(i + 1) % corners.length];
        pushLine(lines, a[0], a[1], areaColor, b[0], b[1]);
    }

    if (p.showLinks) {
        for (const user of sim.users) {
            if (!user.connected || user.serving < 0) continue;
            const bs = sim.bs[user.serving];
            const a = worldToClip(user.x, user.y);
            const b = worldToClip(bs.x, bs.y);
            pushLine(lines, a[0], a[1], [0.23, 0.42, 0.62, 0.18], b[0], b[1]);
        }
    }

    for (const user of sim.users) {
        const [x, y] = worldToClip(user.x, user.y);
        const radius = user.connected ? 4.2 : 3.0;
        const color = user.connected ? shapeColorForUser(user, p) : [0.58, 0.64, 0.72, 0.6];
        pushShape(shapes, x, y, radius * sx, radius * sy, color, 0);
    }

    return {
        shapes: new Float32Array(shapes.slice(0, gpu.maxShapes * 10)),
        shapeCount: Math.min(shapes.length / 10, gpu.maxShapes),
        lines: new Float32Array(lines.slice(0, gpu.maxLineVertices * 6)),
        lineVertexCount: Math.min(lines.length / 6, gpu.maxLineVertices),
    };
}

function chooseGridStep(span) {
    if (span <= 1200) return 100;
    if (span <= 3000) return 250;
    if (span <= 6000) return 500;
    return 1000;
}

function useCpuRenderer(message = "CPU Canvas 2D ativo") {
    const canvas = $("scene");
    const fallback = $("fallback-message");
    cpu.ctx = canvas.getContext("2d");
    cpu.ready = !!cpu.ctx;
    gpu.ready = false;
    $("gpu-status").textContent = cpu.ready ? message : "Renderização indisponível";
    $("render-summary").textContent = $("gpu-status").textContent;
    fallback.textContent = "";
    fallback.hidden = true;
}

async function initWebGPU() {
    const canvas = $("scene");
    if (!navigator.gpu) {
        useCpuRenderer();
        return;
    }

    let adapter;
    try {
        adapter = await navigator.gpu.requestAdapter();
    } catch (error) {
        console.warn(error);
        useCpuRenderer();
        return;
    }
    if (!adapter) {
        useCpuRenderer();
        return;
    }

    try {
        gpu.device = await adapter.requestDevice();
        gpu.context = canvas.getContext("webgpu");
    } catch (error) {
        console.warn(error);
        useCpuRenderer();
        return;
    }
    gpu.format = navigator.gpu.getPreferredCanvasFormat();
    gpu.context.configure({ device: gpu.device, format: gpu.format, alphaMode: "opaque" });

    const quad = gpu.device.createBuffer({
        size: 8 * 4,
        usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
    });
    gpu.device.queue.writeBuffer(quad, 0, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]));
    gpu.quadBuffer = quad;

    gpu.shapeBuffer = gpu.device.createBuffer({
        size: gpu.maxShapes * 10 * 4,
        usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
    });
    gpu.lineBuffer = gpu.device.createBuffer({
        size: gpu.maxLineVertices * 6 * 4,
        usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
    });

    const shapeShader = gpu.device.createShaderModule({ code: `
        struct VertexOut {
            @builtin(position) position: vec4f,
            @location(0) local: vec2f,
            @location(1) color: vec4f,
            @location(2) shape: f32,
        };
        @vertex
        fn vs(
            @location(0) local: vec2f,
            @location(1) center: vec2f,
            @location(2) halfSize: vec2f,
            @location(3) color: vec4f,
            @location(4) shape: f32
        ) -> VertexOut {
            var out: VertexOut;
            out.position = vec4f(center + local * halfSize, 0.0, 1.0);
            out.local = local;
            out.color = color;
            out.shape = shape;
            return out;
        }
        @fragment
        fn fs(in: VertexOut) -> @location(0) vec4f {
            if (in.shape < 0.5 && length(in.local) > 1.0) {
                discard;
            }
            return in.color;
        }
    ` });

    gpu.shapePipeline = gpu.device.createRenderPipeline({
        layout: "auto",
        vertex: {
            module: shapeShader,
            entryPoint: "vs",
            buffers: [
                { arrayStride: 8, attributes: [{ shaderLocation: 0, offset: 0, format: "float32x2" }] },
                {
                    arrayStride: 40,
                    stepMode: "instance",
                    attributes: [
                        { shaderLocation: 1, offset: 0, format: "float32x2" },
                        { shaderLocation: 2, offset: 8, format: "float32x2" },
                        { shaderLocation: 3, offset: 16, format: "float32x4" },
                        { shaderLocation: 4, offset: 32, format: "float32" },
                    ],
                },
            ],
        },
        fragment: {
            module: shapeShader,
            entryPoint: "fs",
            targets: [{ format: gpu.format, blend: {
                color: { srcFactor: "src-alpha", dstFactor: "one-minus-src-alpha" },
                alpha: { srcFactor: "one", dstFactor: "one-minus-src-alpha" },
            } }],
        },
        primitive: { topology: "triangle-strip" },
    });

    const lineShader = gpu.device.createShaderModule({ code: `
        struct VertexOut {
            @builtin(position) position: vec4f,
            @location(0) color: vec4f,
        };
        @vertex
        fn vs(@location(0) position: vec2f, @location(1) color: vec4f) -> VertexOut {
            var out: VertexOut;
            out.position = vec4f(position, 0.0, 1.0);
            out.color = color;
            return out;
        }
        @fragment
        fn fs(in: VertexOut) -> @location(0) vec4f {
            return in.color;
        }
    ` });

    gpu.linePipeline = gpu.device.createRenderPipeline({
        layout: "auto",
        vertex: {
            module: lineShader,
            entryPoint: "vs",
            buffers: [{
                arrayStride: 24,
                attributes: [
                    { shaderLocation: 0, offset: 0, format: "float32x2" },
                    { shaderLocation: 1, offset: 8, format: "float32x4" },
                ],
            }],
        },
        fragment: {
            module: lineShader,
            entryPoint: "fs",
            targets: [{ format: gpu.format, blend: {
                color: { srcFactor: "src-alpha", dstFactor: "one-minus-src-alpha" },
                alpha: { srcFactor: "one", dstFactor: "one-minus-src-alpha" },
            } }],
        },
        primitive: { topology: "line-list" },
    });

    gpu.ready = true;
    $("gpu-status").textContent = "WebGPU ativo";
    $("render-summary").textContent = "WebGPU ativo";
}

function renderGpu() {
    if (!gpu.ready) return;
    const data = buildRenderData();
    if (data.shapeCount > 0) gpu.device.queue.writeBuffer(gpu.shapeBuffer, 0, data.shapes);
    if (data.lineVertexCount > 0) gpu.device.queue.writeBuffer(gpu.lineBuffer, 0, data.lines);

    const encoder = gpu.device.createCommandEncoder();
    const pass = encoder.beginRenderPass({
        colorAttachments: [{
            view: gpu.context.getCurrentTexture().createView(),
            clearValue: { r: 0.972, g: 0.984, b: 1, a: 1 },
            loadOp: "clear",
            storeOp: "store",
        }],
    });

    pass.setPipeline(gpu.linePipeline);
    pass.setVertexBuffer(0, gpu.lineBuffer);
    pass.draw(data.lineVertexCount);
    pass.setPipeline(gpu.shapePipeline);
    pass.setVertexBuffer(0, gpu.quadBuffer);
    pass.setVertexBuffer(1, gpu.shapeBuffer);
    pass.draw(4, data.shapeCount);
    pass.end();
    gpu.device.queue.submit([encoder.finish()]);
}

function renderCpu() {
    if (!cpu.ready) return;

    const canvas = $("scene");
    const ctx = cpu.ctx;
    const p = params();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#f8fbff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const span = Math.max(sim.bounds.maxX - sim.bounds.minX, sim.bounds.maxY - sim.bounds.minY);
    const step = chooseGridStep(span);
    ctx.lineWidth = Math.max(1, canvas.width / 1280);
    ctx.strokeStyle = "rgba(209, 219, 233, 1)";
    ctx.beginPath();
    for (let x = Math.ceil(sim.bounds.minX / step) * step; x <= sim.bounds.maxX; x += step) {
        const a = worldToCanvas(x, sim.bounds.minY);
        const b = worldToCanvas(x, sim.bounds.maxY);
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(b[0], b[1]);
    }
    for (let y = Math.ceil(sim.bounds.minY / step) * step; y <= sim.bounds.maxY; y += step) {
        const a = worldToCanvas(sim.bounds.minX, y);
        const b = worldToCanvas(sim.bounds.maxX, y);
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(b[0], b[1]);
    }
    ctx.stroke();

    ctx.strokeStyle = "rgba(89, 125, 166, 1)";
    ctx.strokeRect(0.5, 0.5, canvas.width - 1, canvas.height - 1);

    if (p.showLinks) {
        ctx.strokeStyle = "rgba(59, 107, 158, 0.18)";
        ctx.beginPath();
        for (const user of sim.users) {
            if (!user.connected || user.serving < 0) continue;
            const bs = sim.bs[user.serving];
            const a = worldToCanvas(user.x, user.y);
            const b = worldToCanvas(bs.x, bs.y);
            ctx.moveTo(a[0], a[1]);
            ctx.lineTo(b[0], b[1]);
        }
        ctx.stroke();
    }

    for (const user of sim.users) {
        const [x, y] = worldToCanvas(user.x, user.y);
        const radius = (user.connected ? 4.2 : 3.0) * Math.max(1, canvas.width / 1280);
        const color = user.connected ? shapeColorForUser(user, p) : [0.58, 0.64, 0.72, 0.6];
        ctx.fillStyle = colorToCss(color);
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
    }
}

function renderTowerLayer() {
    const canvas = $("tower-layer");
    const scene = $("scene");
    if (canvas.width !== scene.width || canvas.height !== scene.height) {
        canvas.width = scene.width;
        canvas.height = scene.height;
    }

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!towerImage.complete || towerImage.naturalWidth === 0) return;

    const scale = Math.max(0.75, canvas.width / 1280);
    const width = 36 * scale;
    const height = 48 * scale;

    for (const bs of sim.bs) {
        const [x, y] = worldToCanvas(bs.x, bs.y);
        const loadGlow = Math.min(bs.load, 1);
        ctx.save();
        ctx.shadowColor = `rgba(${Math.round(220 * loadGlow)}, 70, 40, ${0.12 + loadGlow * 0.28})`;
        ctx.shadowBlur = 14 * scale;
        ctx.drawImage(towerImage, x - width / 2, y - height + 9 * scale, width, height);
        ctx.restore();
    }
}

function render() {
    if (gpu.ready) {
        renderGpu();
    } else {
        renderCpu();
    }
    renderTowerLayer();
}

function updateMetrics() {
    const p = params();
    $("metric-time").textContent = `${sim.time.toFixed(1)} s`;
    $("metric-connected").textContent = sim.metrics.connected.toString();
    $("metric-satisfaction").textContent = `${(sim.metrics.satisfaction * 100).toFixed(1)}%`;
    $("metric-handovers").textContent = Math.trunc(sim.metrics.handovers).toString();
    $("metric-pingpong").textContent = Math.trunc(sim.metrics.pingpong).toString();
    $("metric-rlf").textContent = Math.trunc(sim.metrics.rlf).toString();
    $("metric-blocked").textContent = Math.trunc(sim.metrics.blocked).toString();
    $("metric-load").textContent = `${(sim.metrics.avgLoad * 100).toFixed(1)}%`;
    $("status-message").textContent = sim.running ? "Executando no navegador." : "Aguardando início.";
    $("scenario-summary").textContent = `${p.nBs} BS, ${p.nUsers} UEs, ${p.cmfMode}, ${p.bandwidthMhz} MHz`;
}

function updateLegend() {
    const legend = $("legend");
    if ($("color-scheme").value === "mobility") {
        legend.innerHTML = `
            <span><i class="dot vehicle"></i>Carros: azul</span>
            <span><i class="dot pedestrian"></i>Pedestres: vermelho</span>
            <span><i class="tower"></i>Antena (BS)</span>
        `;
    } else {
        const profiles = configuredProfiles();
        const label = (profile) => `${profile.bitrateKbps.toFixed(0)} kbps (${(profile.probability * 100).toFixed(0)}%)`;
        legend.innerHTML = `
            <span><i class="dot low"></i>Low bitrate: ${label(profiles[0])}</span>
            <span><i class="dot medium"></i>Medium bitrate: ${label(profiles[1])}</span>
            <span><i class="dot high"></i>High bitrate: ${label(profiles[2])}</span>
            <span><i class="tower"></i>Antena (BS)</span>
        `;
    }
}

function animationLoop(now) {
    const dt = Math.min((now - sim.lastFrameTime) / 1000, 0.1);
    sim.lastFrameTime = now;
    if (sim.running) stepSimulation(dt);
    updateMetrics();
    render();
    requestAnimationFrame(animationLoop);
}

function resizeCanvas() {
    const canvas = $("scene");
    const rect = canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(rect.width * dpr));
    const height = Math.max(1, Math.floor(rect.height * dpr));
    if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
        $("tower-layer").width = width;
        $("tower-layer").height = height;
        if (gpu.ready) {
            gpu.context.configure({ device: gpu.device, format: gpu.format, alphaMode: "opaque" });
        }
        if (cpu.ready) {
            cpu.ctx = canvas.getContext("2d");
        }
    }
}

function bindControls() {
    const toggleSimulation = () => {
        setRunning(!sim.running);
        if (sim.running) switchTab("visual");
    };
    $("start-button").addEventListener("click", toggleSimulation);
    $("setup-start-button").addEventListener("click", toggleSimulation);
    $("reset-button").addEventListener("click", resetSimulation);
    $("tab-setup").addEventListener("click", () => switchTab("setup"));
    $("tab-visual").addEventListener("click", () => switchTab("visual"));
    $("setup-visual-shortcut").addEventListener("click", () => switchTab("visual"));
    $("language-toggle").addEventListener("click", () => {});
    $("preset").addEventListener("change", () => {
        const selected = presets[$("preset").value] || presets.default;
        Object.entries(selected).forEach(([id, value]) => {
            if ($(id)) $(id).value = value;
        });
        resetSimulation();
    });
    document.querySelectorAll("#setup-panel input, #setup-panel select").forEach((field) => {
        if (["speed-scale", "color-scheme", "show-links", "preset"].includes(field.id)) return;
        field.addEventListener("change", () => {
            if (field.id === "users-per-bs") {
                $("n-users").value = Math.max(10, Math.min(3000, Math.trunc(numberValue("n-bs", 19) * numberValue("users-per-bs", 20))));
            }
            updateLegend();
            resetSimulation();
        });
    });
    $("color-scheme").addEventListener("change", updateLegend);
    window.addEventListener("resize", resizeCanvas);
}

function switchTab(name) {
    document.querySelectorAll(".tab-button").forEach((button) => {
        button.classList.toggle("active", button.id === `tab-${name}`);
    });
    document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === `${name}-panel`);
    });
    resizeCanvas();
}

async function main() {
    bindControls();
    resetSimulation();
    resizeCanvas();
    await initWebGPU();
    resizeCanvas();
    requestAnimationFrame(animationLoop);
}

main();
