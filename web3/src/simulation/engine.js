import { bounceUser, maybeTurn } from "../domain/mobility.js";
import { computeBounds, createNearRtRic, generateBaseStations, generateUsers } from "../domain/network.js";
import { bestServer } from "../domain/radio.js";
import { emptyMetrics, updateAggregateMetrics } from "./metrics.js";

export class SimulationEngine {
    constructor(readParams, clock = () => performance.now()) {
        this.readParams = readParams;
        this.clock = clock;
        this.state = {
            running: false,
            completed: false,
            time: 0,
            lastFrameTime: 0,
            bounds: { minX: -1000, maxX: 1000, minY: -1000, maxY: 1000 },
            bs: [],
            users: [],
            nearRtRic: null,
            metrics: emptyMetrics(),
        };
    }

    get params() {
        return this.readParams();
    }

    reset() {
        const params = this.params;
        this.state.running = false;
        this.state.completed = false;
        this.state.time = 0;
        this.state.lastFrameTime = this.clock();
        this.state.metrics = emptyMetrics();
        this.state.nearRtRic = createNearRtRic(params);
        this.state.bs = generateBaseStations(params.nBs, params.isd, params);
        this.state.bounds = computeBounds(this.state.bs, params.isd, params.areaMarginFactor);
        this.state.users = generateUsers(params.nUsers, this.state.bounds, params);
        updateAggregateMetrics(this.state);
    }

    setRunning(running) {
        this.state.running = running;
        this.state.lastFrameTime = this.clock();
    }

    toggleRunning() {
        this.setRunning(!this.state.running);
        return this.state.running;
    }

    frame(now) {
        const dt = Math.min((now - this.state.lastFrameTime) / 1000, 0.1);
        this.state.lastFrameTime = now;
        if (this.state.running) this.step(dt);
    }

    step(dt) {
        const params = this.params;
        const scaledDt = Math.min(dt * params.speedScale, params.dt);
        const totalPrbs = Math.max(1, Math.floor((params.bandwidthMhz * 1000) / params.prbBandwidthKhz));
        const prbThroughputKbps = Math.max(1, 450 * params.ueMimoLayers);
        const rlfRsrpThreshold = Math.max(params.rxSensitivity - params.rxSensitivityMargin, params.rlfRsrpThreshold);
        const noiseFloorDbm = params.thermalNoise + 10 * Math.log10(params.bandwidthMhz * 1_000_000) + params.noiseFigure;

        this.state.time += scaledDt;

        // Metrics are only counted after the warm-up period (paper: first 150 s ignored)
        const counting = this.state.time >= params.statisticsIgnoreInitial;

        this.state.bs.forEach((bs) => {
            bs.resetResources();
        });

        for (const user of this.state.users) {
            user.move(scaledDt);
            bounceUser(user, this.state.bounds);
            maybeTurn(user, params, scaledDt);

            const { best, bestSignal, currentSignal } = bestServer(user, this.state.bs, params);
            const sinrDb = bestSignal - noiseFloorDbm - params.interferenceMargin;

            if (bestSignal < rlfRsrpThreshold || sinrDb < params.rlfSinrThreshold) {
                const rlfBsIdx = user.serving;
                user.disconnect();
                if (counting) {
                    this.state.metrics.rlf += 1;
                    if (rlfBsIdx >= 0) this.state.bs[rlfBsIdx].stats.rlf += 1;
                }
                continue;
            }

            if (!user.connected) {
                user.connectTo(best);
            } else {
                // Use per-BS hysteresis if MRO has set one, otherwise fall back to global
                const bsHys = this.state.bs[user.serving]?.hysteresis ?? params.hysteresis;
                if (best !== user.serving && bestSignal > currentSignal + bsHys) {
                    this.handleHandoverCandidate(user, best, scaledDt, params, counting);
                } else {
                    user.candidate = -1;
                    user.ttt = 0;
                }
            }

            this.allocateRadioResources(user, totalPrbs, prbThroughputKbps, counting);
        }

        this.state.bs.forEach((bs) => {
            bs.syncLoad();
        });
        updateAggregateMetrics(this.state);

        // Pass params so xApps can access global TTT/Hys/CIO defaults
        this.state.nearRtRic?.runControlLoop(this.state, params);

        if (this.state.time >= params.simTime) {
            this.state.time = params.simTime;
            this.state.completed = true;
            this.setRunning(false);
        }
    }

    handleHandoverCandidate(user, best, dt, params, counting) {
        if (user.candidate !== best) {
            user.candidate = best;
            user.ttt = 0;
        }
        user.ttt += dt;

        // Use per-BS TTT if MRO has set one, otherwise fall back to global
        const bsTtt = this.state.bs[user.serving]?.ttt ?? params.ttt;
        if (user.ttt < bsTtt) return;

        const sourceBsIdx = user.serving;
        if (user.previousServing === best && this.state.time - user.lastHandoverTime <= params.pingpongPeriod) {
            if (counting) {
                this.state.metrics.pingpong += 1;
                if (sourceBsIdx >= 0) this.state.bs[sourceBsIdx].stats.pingpong += 1;
            }
        }
        if (counting) {
            this.state.metrics.handovers += 1;
            if (sourceBsIdx >= 0) this.state.bs[sourceBsIdx].stats.handovers += 1;
        }

        user.previousServing = user.serving;
        user.serving = best;
        user.lastHandoverTime = this.state.time;
        user.candidate = -1;
        user.ttt = 0;
    }

    allocateRadioResources(user, totalPrbs, prbThroughputKbps, counting) {
        const serving = this.state.bs[user.serving];
        const demandPrbs = Math.max(1, Math.ceil(user.profile.bitrateKbps / prbThroughputKbps));
        const { allocatedPrbs } = serving.allocatePrbs(demandPrbs);

        if (allocatedPrbs === 0) {
            // Fully blocked: count discrete call blockage event on transition
            if (!user.wasBlocked && counting) {
                this.state.metrics.blocked += 1;
            }
            user.wasBlocked = true;
            user.satisfaction = 0;
        } else {
            user.wasBlocked = false;
            user.satisfaction = allocatedPrbs / demandPrbs;
        }
    }
}
