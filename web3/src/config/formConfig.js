import { defaultProfiles } from "./presets.js";

export function numberValue(getField, id, fallback) {
    const field = getField(id);
    if (!field) return fallback;
    const value = Number(field.value);
    return Number.isFinite(value) ? value : fallback;
}

export function configuredProfiles(getField) {
    const profiles = defaultProfiles.map((profile) => ({
        ...profile,
        bitrateKbps: Math.max(1, numberValue(getField, `${profile.name}-bitrate`, profile.bitrateKbps)),
        probability: Math.max(0, numberValue(getField, `${profile.name}-prob`, profile.probability * 100)),
    }));
    const total = profiles.reduce((sum, profile) => sum + profile.probability, 0);
    if (total <= 0) return defaultProfiles;
    return profiles.map((profile) => ({ ...profile, probability: profile.probability / total }));
}

export function readParams(getField) {
    const nBs = Math.max(1, Math.min(61, Math.trunc(numberValue(getField, "n-bs", 19))));
    const usersPerBs = Math.max(1, Math.trunc(numberValue(getField, "users-per-bs", 20)));
    return {
        nBs,
        usersPerBs,
        nUsers: Math.max(10, Math.min(3000, Math.trunc(numberValue(getField, "n-users", nBs * usersPerBs)))),
        isd: Math.max(100, numberValue(getField, "isd", 600)),
        areaMarginFactor: Math.max(0.1, numberValue(getField, "area-margin-factor", 1.5)),
        simTime: Math.max(1, numberValue(getField, "sim-time", 1000)),
        dt: Math.max(0.01, numberValue(getField, "dt", 0.05)),
        speedScale: numberValue(getField, "speed-scale", 1),
        pedestrianProb: Math.max(0, Math.min(1, numberValue(getField, "pedestrian-prob", 80) / 100)),
        pedestrianSpeed: Math.max(0, numberValue(getField, "pedestrian-speed", 5)),
        vehicleSpeed: Math.max(0, numberValue(getField, "vehicle-speed", 25)),
        turnProb: Math.max(0, numberValue(getField, "turn-prob", 1.2) / 100),
        txPower: numberValue(getField, "tx-power", 28),
        bsAntennaGain: numberValue(getField, "bs-antenna-gain", 2),
        bsHeight: Math.max(1, numberValue(getField, "bs-height", 10)),
        bsCableLoss: Math.max(0, numberValue(getField, "bs-cable-loss", 2)),
        frequency: Math.max(600, numberValue(getField, "frequency", 2100)),
        bandwidthMhz: Math.max(1, numberValue(getField, "bandwidth-mhz", 20)),
        subcarrierCount: Math.max(1, Math.trunc(numberValue(getField, "subcarrier-count", 12))),
        subcarrierSpacingKhz: Math.max(1, numberValue(getField, "subcarrier-spacing-khz", 15)),
        defaultCio: numberValue(getField, "default-cio", 0),
        rxSensitivity: numberValue(getField, "rx-sensitivity", -110),
        rxSensitivityMargin: numberValue(getField, "rx-sensitivity-margin", 0),
        hysteresis: Math.max(0, numberValue(getField, "hysteresis", 0)),
        ttt: Math.max(0, numberValue(getField, "ttt", 0.064)),
        ueAntennaGain: numberValue(getField, "ue-antenna-gain", 0),
        ueHeight: Math.max(0.1, numberValue(getField, "ue-height", 1.6)),
        ueCableLoss: Math.max(0, numberValue(getField, "ue-cable-loss", 0)),
        ueMimoLayers: Math.max(1, Math.trunc(numberValue(getField, "ue-mimo-layers", 2))),
        connectionAttemptMean: Math.max(0.1, numberValue(getField, "connection-attempt-mean", 20)),
        connectionAttemptStd: Math.max(0, numberValue(getField, "connection-attempt-std", 3)),
        connectionDurationMean: Math.max(0.1, numberValue(getField, "connection-duration-mean", 60)),
        connectionDurationStd: Math.max(0, numberValue(getField, "connection-duration-std", 15)),
        bodyLoss: numberValue(getField, "body-loss", 1),
        slowFadingMargin: numberValue(getField, "slow-fading-margin", 4),
        foliageLoss: numberValue(getField, "foliage-loss", 4),
        interferenceMargin: numberValue(getField, "interference-margin", 2),
        rainMargin: numberValue(getField, "rain-margin", 0),
        noiseFigure: numberValue(getField, "noise-figure", 7),
        thermalNoise: numberValue(getField, "thermal-noise", -174),
        prbBandwidthKhz: Math.max(1, numberValue(getField, "prb-bandwidth-khz", 180)),
        ricControlPeriod: Math.max(0.1, numberValue(getField, "ric-control-period", 10)),
        mroWindow: Math.max(1, numberValue(getField, "mro-window", 240)),
        pingpongPeriod: Math.max(0.1, numberValue(getField, "pingpong-period", 10)),
        statisticsIgnoreInitial: Math.max(0, numberValue(getField, "statistics-ignore-initial", 150)),
        rlfSinrThreshold: numberValue(getField, "rlf-sinr-threshold", -6),
        rlfRsrpThreshold: numberValue(getField, "rlf-rsrp-threshold", -110),
        cmfMode: getField("cmf-mode")?.value || "no_CM",
        profiles: configuredProfiles(getField),
        colorScheme: getField("color-scheme")?.value || "bitrate",
        showLinks: getField("show-links")?.checked ?? true,
    };
}
