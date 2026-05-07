import { chooseGridStep, shapeColorForUser, worldToClip } from "./coordinates.js";

function pushShape(out, x, y, radiusX, radiusY, color, shape) {
    out.push(x, y, radiusX, radiusY, color[0], color[1], color[2], color[3], shape, 0);
}

function pushLine(out, x1, y1, c1, x2, y2, c2 = c1) {
    out.push(x1, y1, c1[0], c1[1], c1[2], c1[3], x2, y2, c2[0], c2[1], c2[2], c2[3]);
}

export function buildRenderData(canvas, state, params, limits) {
    const shapes = [];
    const lines = [];
    const sx = 2 / Math.max(canvas.width, 1);
    const sy = 2 / Math.max(canvas.height, 1);
    const bounds = state.bounds;

    const gridColor = [0.82, 0.87, 0.93, 1];
    const areaColor = [0.35, 0.49, 0.65, 1];
    const step = chooseGridStep(Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY));
    for (let x = Math.ceil(bounds.minX / step) * step; x <= bounds.maxX; x += step) {
        const a = worldToClip(bounds, x, bounds.minY);
        const b = worldToClip(bounds, x, bounds.maxY);
        pushLine(lines, a[0], a[1], gridColor, b[0], b[1]);
    }
    for (let y = Math.ceil(bounds.minY / step) * step; y <= bounds.maxY; y += step) {
        const a = worldToClip(bounds, bounds.minX, y);
        const b = worldToClip(bounds, bounds.maxX, y);
        pushLine(lines, a[0], a[1], gridColor, b[0], b[1]);
    }

    const corners = [
        worldToClip(bounds, bounds.minX, bounds.minY),
        worldToClip(bounds, bounds.maxX, bounds.minY),
        worldToClip(bounds, bounds.maxX, bounds.maxY),
        worldToClip(bounds, bounds.minX, bounds.maxY),
    ];
    for (let i = 0; i < corners.length; i += 1) {
        const a = corners[i];
        const b = corners[(i + 1) % corners.length];
        pushLine(lines, a[0], a[1], areaColor, b[0], b[1]);
    }

    if (params.showLinks) {
        for (const user of state.users) {
            if (!user.connected || user.serving < 0) continue;
            const bs = state.bs[user.serving];
            const a = worldToClip(bounds, user.x, user.y);
            const b = worldToClip(bounds, bs.x, bs.y);
            pushLine(lines, a[0], a[1], [0.23, 0.42, 0.62, 0.18], b[0], b[1]);
        }
    }

    for (const user of state.users) {
        const [x, y] = worldToClip(bounds, user.x, user.y);
        const radius = user.connected ? 4.2 : 3.0;
        const color = user.connected ? shapeColorForUser(user, params) : [0.58, 0.64, 0.72, 0.6];
        pushShape(shapes, x, y, radius * sx, radius * sy, color, 0);
    }

    return {
        shapes: new Float32Array(shapes.slice(0, limits.maxShapes * 10)),
        shapeCount: Math.min(shapes.length / 10, limits.maxShapes),
        lines: new Float32Array(lines.slice(0, limits.maxLineVertices * 6)),
        lineVertexCount: Math.min(lines.length / 6, limits.maxLineVertices),
    };
}
