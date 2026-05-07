export class UserEquipment {
    constructor({ id, x, y, vx, vy, speed, mobility, profile }) {
        this.id = id;
        this.x = x;
        this.y = y;
        this.vx = vx;
        this.vy = vy;
        this.speed = speed;
        this.mobility = mobility;
        this.profile = profile;
        this.connected = false;
        this.serving = -1;
        this.previousServing = -1;
        this.candidate = -1;
        this.ttt = 0;
        this.lastHandoverTime = -999;
        this.satisfaction = 0;
        this.wasBlocked = false;
    }

    move(dt) {
        this.x += this.vx * dt;
        this.y += this.vy * dt;
    }

    disconnect() {
        this.connected = false;
        this.serving = -1;
        this.satisfaction = 0;
        this.wasBlocked = false;
    }

    connectTo(baseStationIndex) {
        this.connected = true;
        this.serving = baseStationIndex;
        this.candidate = -1;
        this.ttt = 0;
        this.wasBlocked = false;
    }
}

export class AntennaModel {
    constructor({ id, gainDb, heightM, cableLossDb, txPowerDbm, frequencyMhz, bandwidthMhz }) {
        this.id = id;
        this.gainDb = gainDb;
        this.heightM = heightM;
        this.cableLossDb = cableLossDb;
        this.txPowerDbm = txPowerDbm;
        this.frequencyMhz = frequencyMhz;
        this.bandwidthMhz = bandwidthMhz;
    }
}

export class RruModel {
    constructor({ id, antenna, maxPrbs, prbBandwidthKhz }) {
        this.id = id;
        this.antenna = antenna;
        this.maxPrbs = maxPrbs;
        this.prbBandwidthKhz = prbBandwidthKhz;
        this.usedPrbs = 0;
    }

    resetResources() {
        this.usedPrbs = 0;
    }

    allocatePrbs(demandPrbs) {
        const availablePrbs = Math.max(0, this.maxPrbs - this.usedPrbs);
        const allocatedPrbs = Math.min(availablePrbs, demandPrbs);
        this.usedPrbs += allocatedPrbs;
        return { allocatedPrbs, availablePrbs };
    }

    get load() {
        return this.maxPrbs > 0 ? Math.min(this.usedPrbs / this.maxPrbs, 1) : 0;
    }
}

export class DistributedUnit {
    constructor({ id, rrus = [] }) {
        this.id = id;
        this.rrus = rrus;
    }
}

export class CentralUnit {
    constructor({ id, distributedUnits = [] }) {
        this.id = id;
        this.distributedUnits = distributedUnits;
    }
}

export class BaseStation {
    constructor({ id, x, y, antenna, rru, du, cu }) {
        this.id = id;
        this.x = x;
        this.y = y;
        this.antenna = antenna;
        this.rru = rru;
        this.du = du;
        this.cu = cu;
        this.load = 0;
        this.usedPrbs = 0;
        // CMF-managed per-BS parameters (null = fall back to global params)
        this.cio = 0;           // Cell Individual Offset (dB), adjusted by MLB
        this.ttt = null;        // Time-To-Trigger (s), adjusted by MRO
        this.hysteresis = null; // Handover hysteresis (dB), adjusted by MRO
        // Per-BS statistics accumulated for MRO observation
        this.stats = { rlf: 0, pingpong: 0, handovers: 0 };
    }

    resetResources() {
        this.rru.resetResources();
        this.usedPrbs = 0;
        this.load = 0;
    }

    allocatePrbs(demandPrbs) {
        const result = this.rru.allocatePrbs(demandPrbs);
        this.usedPrbs = this.rru.usedPrbs;
        this.load = this.rru.load;
        return result;
    }

    syncLoad() {
        this.usedPrbs = this.rru.usedPrbs;
        this.load = this.rru.load;
    }
}

// Base xApp: no-op decisions
export class XApp {
    constructor({ id, name, type, priority = 0, enabled = true }) {
        this.id = id;
        this.name = name;
        this.type = type;
        this.priority = priority;
        this.enabled = enabled;
    }

    observe(state) {
        return {
            time: state.time,
            connectedUsers: state.metrics.connected,
            avgLoad: state.metrics.avgLoad,
            handovers: state.metrics.handovers,
            pingpong: state.metrics.pingpong,
            rlf: state.metrics.rlf,
        };
    }

    computeDecisions(_state, _params) {
        return [];
    }
}

// MRO xApp: adjusts per-BS TTT and hysteresis to minimize RLFs and ping-pong handovers.
// High RLF rate (too-late HO) → decrease TTT/Hys to trigger HO earlier.
// High ping-pong rate (too-early HO) → increase TTT/Hys to stabilize HO.
export class MROXApp extends XApp {
    constructor(props) {
        super({ ...props, type: "MRO" });
    }

    computeDecisions(state, params) {
        const decisions = [];
        for (const bs of state.bs) {
            const { rlf, pingpong, handovers } = bs.stats;
            const totalEvents = handovers + rlf;
            if (totalEvents < 1) continue; // insufficient data for this period

            const rlfRate = rlf / totalEvents;
            const ppRate = handovers > 0 ? pingpong / handovers : 0;

            const curTtt = bs.ttt ?? params.ttt;
            const curHys = bs.hysteresis ?? params.hysteresis;
            let newTtt = curTtt;
            let newHys = curHys;

            if (rlfRate > 0.1 && ppRate <= 0.3) {
                // Too-late HO: reduce TTT and hysteresis so HO triggers sooner
                newTtt = Math.max(0.04, curTtt * 0.85);
                newHys = Math.max(0, curHys - 0.5);
            } else if (ppRate > 0.3 && rlfRate <= 0.1) {
                // Too-early HO: increase TTT and hysteresis to stabilize
                newTtt = Math.min(0.512, curTtt * 1.2);
                newHys = Math.min(10, curHys + 0.5);
            }

            if (Math.abs(newTtt - curTtt) > 1e-6 || Math.abs(newHys - curHys) > 1e-6) {
                decisions.push({
                    bsId: bs.id,
                    params: { ttt: newTtt, hysteresis: newHys },
                    xAppId: this.id,
                    paramGroup: "AffectHandover",
                });
            }
        }
        return decisions;
    }
}

// MLB xApp: adjusts per-BS CIO to balance load across base stations.
// Overloaded BS → decrease CIO to offload users to neighbors.
// Underloaded BS → increase CIO to attract users.
export class MLBXApp extends XApp {
    constructor(props) {
        super({ ...props, type: "MLB" });
    }

    computeDecisions(state, params) {
        const decisions = [];
        const avgLoad = state.metrics.avgLoad;
        for (const bs of state.bs) {
            const loadDiff = bs.load - avgLoad;
            const curCio = bs.cio;
            let newCio = curCio;

            if (loadDiff > 0.1) {
                newCio = Math.max(-6, curCio - 1);
            } else if (loadDiff < -0.1) {
                newCio = Math.min(6, curCio + 1);
            } else if (Math.abs(loadDiff) < 0.05 && Math.abs(curCio) > 0) {
                // Near-balanced: converge CIO back toward 0
                newCio = curCio > 0 ? Math.max(0, curCio - 0.5) : Math.min(0, curCio + 0.5);
            }

            if (Math.abs(newCio - curCio) > 1e-6) {
                decisions.push({
                    bsId: bs.id,
                    params: { cio: newCio },
                    xAppId: this.id,
                    paramGroup: "AffectHandover",
                });
            }
        }
        return decisions;
    }
}

// Near-RT RIC with embedded CMF (CD Agent + CR Agent).
// CD Agent detects ICD conflicts: decisions from different xApps in the same
// Parameter Group (AffectHandover) for the same BS.
// CR Agent resolves conflicts by blocking the lower-priority xApp's decision.
// In no_CM mode, conflict detection is disabled and all decisions are applied.
export class NearRtRic {
    constructor({ id, controlPeriodS, xApps = [], cmfMode = "no_CM" }) {
        this.id = id;
        this.controlPeriodS = controlPeriodS;
        this.cmfMode = cmfMode;
        this.xApps = xApps;
        this.lastControlTime = 0;
        this.lastObservations = [];
        // CMF Database: bsId → paramGroup → xAppId → { priority }
        this.recentDecisions = new Map();
        // Exposed for UI: stats from the most recent control cycle
        this.lastActivity = { conflictsDetected: 0, decisionsBlocked: 0, avgTtt: null, avgHys: null, avgCio: 0, cycleTime: -1 };
    }

    shouldRun(time) {
        return time - this.lastControlTime >= this.controlPeriodS;
    }

    runControlLoop(state, params) {
        if (!this.shouldRun(state.time)) return [];
        this.lastControlTime = state.time;

        // Previous control period's decisions have expired
        this.recentDecisions.clear();

        const bsMap = new Map(state.bs.map((bs) => [bs.id, bs]));

        // Collect decisions from each xApp, highest priority first
        const allDecisions = [];
        const sorted = [...this.xApps]
            .filter((x) => x.enabled)
            .sort((a, b) => b.priority - a.priority);
        for (const xApp of sorted) {
            for (const d of xApp.computeDecisions(state, params)) {
                allDecisions.push({ ...d, priority: xApp.priority });
            }
        }

        // CD Agent + CR Agent: evaluate and apply each decision
        let conflictsDetected = 0;
        let decisionsBlocked = 0;
        for (const decision of allDecisions) {
            const bs = bsMap.get(decision.bsId);
            if (!bs) continue;
            const hasConflict = this._detectConflict(decision);
            if (hasConflict) conflictsDetected++;
            if (this.cmfMode !== "no_CM" && hasConflict && this._priorityBlocks(decision)) {
                decisionsBlocked++;
                continue;
            }
            this._applyDecision(bs, decision);
        }

        // Update lastActivity for UI display
        const activeTtts = state.bs.map((bs) => bs.ttt).filter((v) => v !== null);
        const activeHyss = state.bs.map((bs) => bs.hysteresis).filter((v) => v !== null);
        this.lastActivity = {
            conflictsDetected,
            decisionsBlocked,
            avgTtt: activeTtts.length > 0 ? activeTtts.reduce((a, b) => a + b, 0) / activeTtts.length : null,
            avgHys: activeHyss.length > 0 ? activeHyss.reduce((a, b) => a + b, 0) / activeHyss.length : null,
            avgCio: state.bs.length > 0 ? state.bs.reduce((sum, bs) => sum + bs.cio, 0) / state.bs.length : 0,
            cycleTime: state.time,
        };

        // Reset per-BS stats after MRO has observed them
        for (const bs of state.bs) {
            bs.stats.rlf = 0;
            bs.stats.pingpong = 0;
            bs.stats.handovers = 0;
        }

        this.lastObservations = allDecisions;
        return allDecisions;
    }

    // ICD: conflict exists if another xApp has a decision in the same PG for this BS
    _detectConflict(decision) {
        const pgMap = this.recentDecisions.get(decision.bsId)?.get(decision.paramGroup);
        if (!pgMap) return false;
        for (const xAppId of pgMap.keys()) {
            if (xAppId !== decision.xAppId) return true;
        }
        return false;
    }

    // CR Agent: block if the conflicting xApp has equal or higher priority
    _priorityBlocks(decision) {
        const pgMap = this.recentDecisions.get(decision.bsId)?.get(decision.paramGroup);
        if (!pgMap) return false;
        for (const [xAppId, entry] of pgMap) {
            if (xAppId !== decision.xAppId && entry.priority >= decision.priority) return true;
        }
        return false;
    }

    _applyDecision(bs, decision) {
        if (decision.params.ttt !== undefined) bs.ttt = decision.params.ttt;
        if (decision.params.hysteresis !== undefined) bs.hysteresis = decision.params.hysteresis;
        if (decision.params.cio !== undefined) bs.cio = decision.params.cio;

        if (!this.recentDecisions.has(bs.id)) this.recentDecisions.set(bs.id, new Map());
        const bsLevel = this.recentDecisions.get(bs.id);
        if (!bsLevel.has(decision.paramGroup)) bsLevel.set(decision.paramGroup, new Map());
        bsLevel.get(decision.paramGroup).set(decision.xAppId, { priority: decision.priority });
    }
}
