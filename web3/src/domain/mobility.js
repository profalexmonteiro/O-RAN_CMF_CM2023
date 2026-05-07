export function randomBetween(min, max) {
    return min + Math.random() * (max - min);
}

export function bounceUser(user, bounds) {
    if (user.x < bounds.minX || user.x > bounds.maxX) {
        user.x = Math.max(bounds.minX, Math.min(bounds.maxX, user.x));
        user.vx *= -1;
    }
    if (user.y < bounds.minY || user.y > bounds.maxY) {
        user.y = Math.max(bounds.minY, Math.min(bounds.maxY, user.y));
        user.vy *= -1;
    }
}

export function maybeTurn(user, params, dt) {
    if (Math.random() > params.turnProb * dt) return;
    const angle = Math.atan2(user.vy, user.vx) + randomBetween(-0.9, 0.9);
    user.vx = Math.cos(angle) * user.speed;
    user.vy = Math.sin(angle) * user.speed;
}
