import json
import os
import sys
import tempfile
import time

import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import scripts.simulation as simulation

STATE_PATH = os.path.join(tempfile.gettempdir(), "oran_vercel_state.json")
STOP_PATH = os.path.join(tempfile.gettempdir(), "oran_vercel_stop")

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

DEFAULT_STATE = {
    "running": False,
    "last_snapshot": None,
    "message": "Idle",
    "params": {},
    "last_update": 0,
    "done": False,
}


def json_default(obj):
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
    data = json.dumps(payload, default=json_default).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    handler.end_headers()
    handler.wfile.write(data)


def read_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as state_file:
            state = json.load(state_file)
    except (FileNotFoundError, json.JSONDecodeError):
        state = dict(DEFAULT_STATE)
    return state


def write_state(**changes):
    state = read_state()
    state.update(changes)
    state["last_update"] = time.time()
    with open(STATE_PATH, "w", encoding="utf-8") as state_file:
        json.dump(state, state_file, default=json_default)
    return state


def parse_payload(handler):
    content_length = int(handler.headers.get("Content-Length", 0))
    body = handler.rfile.read(content_length).decode("utf-8")
    return json.loads(body) if body else {}


def coerce_params(data):
    params = {}
    for key, caster in PARAM_TYPES.items():
        value = data.get(key, data.get(key.lower()))
        if value is None:
            params[key] = getattr(simulation, key)
            continue
        try:
            params[key] = caster(value)
        except (TypeError, ValueError):
            params[key] = caster(getattr(simulation, key))

    if isinstance(data.get("USER_PROFILES"), dict):
        params["USER_PROFILES"] = data["USER_PROFILES"]

    cmf_mode = data.get("cmf_mode") or data.get("CMF_MODE") or "no_CM"
    if cmf_mode not in {"no_CM", "prio_MRO", "prio_MLB"}:
        cmf_mode = "no_CM"

    params["cmf_mode"] = cmf_mode
    params["export_bs_results"] = False
    return params


def apply_simulation_parameters(params):
    for key, value in params.items():
        if key in {"USER_PROFILES", "cmf_mode", "export_bs_results"}:
            continue
        if hasattr(simulation, key):
            setattr(simulation, key, value)

    profile_updates = params.get("USER_PROFILES")
    if isinstance(profile_updates, dict):
        for name, values in profile_updates.items():
            if name in simulation.USER_PROFILES and isinstance(values, dict):
                simulation.USER_PROFILES[name].update(values)

    simulation.N_USERS = int(simulation.N_USERS)
    simulation.STEPS = int(simulation.SIM_TIME / simulation.DT)
    simulation.TOTAL_PRBS_PER_BS = int(simulation.BANDWIDTH_HZ / simulation.PRB_BANDWIDTH_HZ)


class FileStopEvent:
    def is_set(self):
        return os.path.exists(STOP_PATH)


def clear_stop_request():
    try:
        os.remove(STOP_PATH)
    except FileNotFoundError:
        pass
