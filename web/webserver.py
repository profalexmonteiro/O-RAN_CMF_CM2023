import json
import os
import sys
import threading
import time
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

import scripts.simulation as simulation

WEB_DIR = os.path.abspath(os.path.dirname(__file__))
PORT = 8000

PARAM_TYPES = {
    "N_BS": int,
    "USERS_PER_BS": int,
    "N_USERS": int,
    "INTER_SITE_DISTANCE": float,
    "SIMULATION_AREA_MARGIN_FACTOR": float,
    "SIM_TIME": float,
    "DT": float,
    "BS_TX_POWER_DBM": float,
    "BS_ANTENNA_GAIN_DB": float,
    "BS_HEIGHT_M": float,
    "BS_CABLE_LOSS_DB": float,
    "CENTER_FREQ_GHZ": float,
    "BANDWIDTH_HZ": float,
    "SUBCARRIER_COUNT": int,
    "SUBCARRIER_SPACING_HZ": float,
    "DEFAULT_CIO_DB": float,
    "DEFAULT_TTT_S": float,
    "DEFAULT_HYSTERESIS_DB": float,
    "UE_ANTENNA_GAIN_DB": float,
    "UE_HEIGHT_M": float,
    "UE_CABLE_LOSS_DB": float,
    "UE_RX_SENSITIVITY_DBM": float,
    "UE_RX_SENSITIVITY_MARGIN_DB": float,
    "UE_MIMO_LAYERS": int,
    "PEDESTRIAN_PROB": float,
    "PEDESTRIAN_SPEED": float,
    "VEHICLE_SPEED": float,
    "DIRECTION_CHANGE_PROB": float,
    "CONNECTION_ATTEMPT_MEAN": float,
    "CONNECTION_ATTEMPT_STD": float,
    "CONNECTION_DURATION_MEAN": float,
    "CONNECTION_DURATION_STD": float,
    "BODY_LOSS_DB": float,
    "SLOW_FADING_MARGIN_DB": float,
    "FOLIAGE_LOSS_DB": float,
    "INTERFERENCE_MARGIN_DB": float,
    "RAIN_MARGIN_DB": float,
    "NOISE_FIGURE_DB": float,
    "THERMAL_NOISE_DBM_HZ": float,
    "PRB_BANDWIDTH_HZ": float,
    "RIC_CONTROL_PERIOD": float,
    "MRO_WINDOW": float,
    "PINGPONG_PERIOD": float,
    "RLF_SINR_THRESHOLD_DB": float,
    "RLF_RSRP_THRESHOLD_DBM": float,
}

SIM_STATE = {
    "running": False,
    "last_snapshot": None,
    "message": "Idle",
    "params": {},
    "last_update": 0,
}
SIM_LOCK = threading.Lock()
SIM_THREAD = None
STOP_EVENT = threading.Event()


def _json_default(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", "ignore")
    raise TypeError(f"Type {type(obj).__name__} not serializable")


def send_json(handler, payload, status=200):
    data = json.dumps(payload, default=_json_default).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def update_simulation_state(snapshot=None, message=None, running=None, done=None):
    with SIM_LOCK:
        if snapshot is not None:
            SIM_STATE["last_snapshot"] = snapshot
        if message is not None:
            SIM_STATE["message"] = message
        if running is not None:
            SIM_STATE["running"] = running
        if done is not None:
            SIM_STATE["done"] = done
        SIM_STATE["last_update"] = time.time()


def simulation_step_callback(snapshot):
    update_simulation_state(snapshot=snapshot, message="Running", running=True, done=False)


def apply_simulation_parameters(params):
    """Apply parameters directly to the simulation module globals."""
    for key, value in params.items():
        if key == "USER_PROFILES":
            continue
        if hasattr(simulation, key):
            setattr(simulation, key, value)

    profile_updates = params.get("USER_PROFILES")
    if isinstance(profile_updates, dict):
        for name, values in profile_updates.items():
            if name in simulation.USER_PROFILES and isinstance(values, dict):
                simulation.USER_PROFILES[name].update(values)

    if hasattr(simulation, "SIM_TIME") and hasattr(simulation, "DT"):
        simulation.STEPS = int(simulation.SIM_TIME / simulation.DT)
    if hasattr(simulation, "BANDWIDTH_HZ") and hasattr(simulation, "PRB_BANDWIDTH_HZ"):
        simulation.TOTAL_PRBS_PER_BS = int(simulation.BANDWIDTH_HZ / simulation.PRB_BANDWIDTH_HZ)


def run_simulation_task(params, cmf_mode="no_CM", export_bs_results=True):
    try:
        STOP_EVENT.clear()
        apply_simulation_parameters(params)
        update_simulation_state(message="Starting", running=True, done=False)
        simulation.run_simulation(
            show_progress=False,
            step_callback=simulation_step_callback,
            stop_event=STOP_EVENT,
            cmf_mode=cmf_mode,
            export_bs_results=export_bs_results,
        )
        update_simulation_state(message="Finished", running=False, done=True)
    except Exception as exc:
        print("[webserver] Simulation task exception:")
        traceback.print_exc()
        update_simulation_state(message=f"Error: {exc}", running=False, done=True)


class SimulationHTTPRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        print("[web] " + format % args)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            with SIM_LOCK:
                state = {
                    "running": SIM_STATE["running"],
                    "message": SIM_STATE["message"],
                    "params": SIM_STATE["params"],
                    "last_update": SIM_STATE["last_update"],
                    "snapshot": SIM_STATE["last_snapshot"],
                    "done": SIM_STATE.get("done", False),
                }
            send_json(self, state)
            return
        if parsed.path == "/api/info":
            info = {key: getattr(simulation, key) for key in PARAM_TYPES}
            info["steps"] = simulation.STEPS
            info["status"] = "ready"
            send_json(self, info)
            return
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/start":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                send_json(self, {"error": "JSON inválido"}, status=400)
                return

            with SIM_LOCK:
                if SIM_STATE["running"]:
                    send_json(self, {"error": "Simulação já em execução"}, status=409)
                    return

            params = {}
            for key, caster in PARAM_TYPES.items():
                value = None
                if key in data:
                    value = data[key]
                elif key.lower() in data:
                    value = data[key.lower()]

                if value is not None:
                    try:
                        params[key] = caster(value)
                    except (TypeError, ValueError):
                        params[key] = caster(getattr(simulation, key))
                else:
                    params[key] = getattr(simulation, key)

            if isinstance(data.get("USER_PROFILES"), dict):
                params["USER_PROFILES"] = data["USER_PROFILES"]

            cmf_mode = data.get("cmf_mode") or data.get("CMF_MODE") or "no_CM"
            if cmf_mode not in {"no_CM", "prio_MRO", "prio_MLB"}:
                cmf_mode = "no_CM"
            params["cmf_mode"] = cmf_mode

            export_bs_results = bool(data.get("export_bs_results", True))
            params["export_bs_results"] = export_bs_results

            SIM_STATE["params"] = params
            update_simulation_state(message="Queued", running=False, done=False)

            global SIM_THREAD
            SIM_THREAD = threading.Thread(
                target=run_simulation_task,
                args=(params, cmf_mode, export_bs_results),
                daemon=True,
            )
            SIM_THREAD.start()

            send_json(self, {"status": "starting"})
            return

        if parsed.path == "/api/stop":
            STOP_EVENT.set()
            update_simulation_state(message="Stopping", running=True, done=False)
            send_json(self, {"status": "stopping"})
            return

        send_json(self, {"error": "Endpoint desconhecido"}, status=404)


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), SimulationHTTPRequestHandler)
    print(f"Servidor web rodando em http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
