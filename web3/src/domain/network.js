import { randomBetween } from "./mobility.js";
import {
    AntennaModel,
    BaseStation,
    CentralUnit,
    DistributedUnit,
    MLBXApp,
    MROXApp,
    NearRtRic,
    RruModel,
    UserEquipment,
} from "./models.js";

function totalPrbs(params) {
    const bandwidthMhz = params.bandwidthMhz ?? 20;
    const prbBandwidthKhz = params.prbBandwidthKhz ?? 180;
    return Math.max(1, Math.floor((bandwidthMhz * 1000) / prbBandwidthKhz));
}

export function generateBaseStations(count, isd, params = {}) {
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
        .map((point, index) => {
            const id = index + 1;
            const antenna = new AntennaModel({
                id: `ANT-${id}`,
                gainDb: params.bsAntennaGain ?? 2,
                heightM: params.bsHeight ?? 10,
                cableLossDb: params.bsCableLoss ?? 2,
                txPowerDbm: params.txPower ?? 28,
                frequencyMhz: params.frequency ?? 2100,
                bandwidthMhz: params.bandwidthMhz ?? 20,
            });
            const rru = new RruModel({
                id: `RRU-${id}`,
                antenna,
                maxPrbs: totalPrbs(params),
                prbBandwidthKhz: params.prbBandwidthKhz ?? 180,
            });
            const du = new DistributedUnit({ id: `DU-${id}`, rrus: [rru] });
            const cu = new CentralUnit({ id: `CU-${id}`, distributedUnits: [du] });
            return new BaseStation({ id, x: point.x, y: point.y, antenna, rru, du, cu });
        });
}

export function computeBounds(baseStations, isd, marginFactor) {
    const xs = baseStations.map((bs) => bs.x);
    const ys = baseStations.map((bs) => bs.y);
    const margin = Math.max(isd * marginFactor, 500);
    return {
        minX: Math.min(...xs) - margin,
        maxX: Math.max(...xs) + margin,
        minY: Math.min(...ys) - margin,
        maxY: Math.max(...ys) + margin,
    };
}

export function sampleProfile(profiles) {
    const value = Math.random();
    let acc = 0;
    for (const profile of profiles) {
        acc += profile.probability;
        if (value <= acc) return profile;
    }
    return profiles[profiles.length - 1];
}

export function generateUsers(count, bounds, params) {
    return Array.from({ length: count }, (_, id) => {
        const isPedestrian = Math.random() < params.pedestrianProb;
        const speed = isPedestrian ? params.pedestrianSpeed : params.vehicleSpeed;
        const angle = Math.random() * Math.PI * 2;
        return new UserEquipment({
            id,
            x: randomBetween(bounds.minX, bounds.maxX),
            y: randomBetween(bounds.minY, bounds.maxY),
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            speed,
            mobility: isPedestrian ? "pedestrian" : "vehicle",
            profile: sampleProfile(params.profiles),
        });
    });
}

export function createNearRtRic(params) {
    const priorities = {
        no_CM: { mro: 1, mlb: 1 },
        prio_MRO: { mro: 2, mlb: 1 },
        prio_MLB: { mro: 1, mlb: 2 },
    }[params.cmfMode] || { mro: 1, mlb: 1 };

    return new NearRtRic({
        id: "near-RT-RIC-1",
        controlPeriodS: params.ricControlPeriod ?? 10,
        cmfMode: params.cmfMode ?? "no_CM",
        xApps: [
            new MROXApp({ id: "xapp-mro", name: "MRO xApp", priority: priorities.mro }),
            new MLBXApp({ id: "xapp-mlb", name: "MLB xApp", priority: priorities.mlb }),
        ],
    });
}
