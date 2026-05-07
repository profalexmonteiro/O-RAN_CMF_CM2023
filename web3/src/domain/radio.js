export function pathlossDb(distanceM, frequencyMhz) {
    const dKm = Math.max(distanceM / 1000, 0.001);
    return 32.4 + 20 * Math.log10(frequencyMhz) + 30 * Math.log10(dKm);
}

export function signalDbm(user, bs, params) {
    const horizontalDistance = Math.hypot(user.x - bs.x, user.y - bs.y);
    const bsHeight = bs.antenna?.heightM ?? params.bsHeight;
    const bsGain = bs.antenna?.gainDb ?? params.bsAntennaGain;
    const bsCableLoss = bs.antenna?.cableLossDb ?? params.bsCableLoss;
    const txPower = bs.antenna?.txPowerDbm ?? params.txPower;
    const frequency = bs.antenna?.frequencyMhz ?? params.frequency;
    const distance = Math.hypot(horizontalDistance, bsHeight - params.ueHeight);
    const loadPenalty = bs.load * 8;
    const gains = bsGain + params.ueAntennaGain;
    const losses = bsCableLoss + params.ueCableLoss + params.bodyLoss + params.slowFadingMargin + params.foliageLoss + params.interferenceMargin + params.rainMargin;
    return txPower + gains - losses - pathlossDb(distance, frequency) - loadPenalty;
}

// CIO (Cell Individual Offset) is added to each BS's measured signal before comparison.
// MLB adjusts per-BS CIO to steer users toward under-loaded cells (load balancing).
// The global defaultCio applies uniformly to all cells as a baseline offset.
export function bestServer(user, baseStations, params) {
    const globalCio = params.defaultCio ?? 0;
    let best = -1;
    let bestSignal = -Infinity;
    let currentSignal = -Infinity;
    for (let i = 0; i < baseStations.length; i += 1) {
        const raw = signalDbm(user, baseStations[i], params);
        const adjusted = raw + (baseStations[i].cio ?? 0) + globalCio;
        if (i === user.serving) currentSignal = adjusted;
        if (adjusted > bestSignal) {
            best = i;
            bestSignal = adjusted;
        }
    }
    return { best, bestSignal, currentSignal };
}
