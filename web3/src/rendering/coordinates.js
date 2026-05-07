export function worldToClip(bounds, x, y) {
    const width = bounds.maxX - bounds.minX;
    const height = bounds.maxY - bounds.minY;
    return [
        ((x - bounds.minX) / width) * 1.82 - 0.91,
        ((y - bounds.minY) / height) * 1.82 - 0.91,
    ];
}

export function worldToCanvas(canvas, bounds, x, y) {
    const width = bounds.maxX - bounds.minX;
    const height = bounds.maxY - bounds.minY;
    return [
        ((x - bounds.minX) / width) * canvas.width,
        canvas.height - ((y - bounds.minY) / height) * canvas.height,
    ];
}

export function chooseGridStep(span) {
    if (span <= 1200) return 100;
    if (span <= 3000) return 250;
    if (span <= 6000) return 500;
    return 1000;
}

export function colorToCss(color) {
    const r = Math.round(color[0] * 255);
    const g = Math.round(color[1] * 255);
    const b = Math.round(color[2] * 255);
    const a = color[3] ?? 1;
    return `rgba(${r}, ${g}, ${b}, ${a})`;
}

export function shapeColorForUser(user, params) {
    if (params.colorScheme === "mobility") {
        return user.mobility === "vehicle"
            ? [0.145, 0.388, 0.922, 1]
            : [0.863, 0.149, 0.149, 1];
    }
    return user.profile.color;
}
