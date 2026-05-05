#!/usr/bin/env python3
import csv
import io
import json
import os
import sys
import threading
import time
import traceback
from dataclasses import fields
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, ROOT_DIR)

from scripts.simulationW import SimConfig, deploy_gnbs, init_ues, run_once

PORT = int(os.environ.get("SIM2_PORT", "8001"))
METHODS = ["NC", "SBD", "P-ES", "P-MRO", "QACM"]
METRICS = [
    "energy_efficiency_gb_per_j",
    "link_failures",
    "total_handovers",
    "pingpong_handovers",
]

STATE = {
    "running": False,
    "status": "Idle",
    "message": "Aguardando configuracao",
    "completed": 0,
    "total": 0,
    "started_at": None,
    "finished_at": None,
    "results": None,
    "topology": None,
    "error": None,
}
STATE_LOCK = threading.Lock()


def json_default(value):
    try:
        import numpy as np

        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return float(value)
        if isinstance(value, np.ndarray):
            return value.tolist()
    except Exception:
        pass
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def send_json(handler, payload, status=200):
    data = json.dumps(payload, default=json_default).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def update_state(**changes):
    with STATE_LOCK:
        STATE.update(changes)


def config_fields():
    cfg = SimConfig()
    rows = []
    for field in fields(SimConfig):
        value = getattr(cfg, field.name)
        if isinstance(value, tuple):
            continue
        rows.append({
            "name": field.name,
            "label": field.name.replace("_", " ").title(),
            "value": value,
            "type": "int" if isinstance(value, int) and not isinstance(value, bool) else "float",
        })
    return rows


def coerce_config(payload):
    defaults = SimConfig()
    values = {}
    incoming = payload.get("config") if isinstance(payload.get("config"), dict) else {}

    for field in fields(SimConfig):
        default = getattr(defaults, field.name)
        if isinstance(default, tuple):
            values[field.name] = default
            continue

        raw = incoming.get(field.name, default)
        try:
            values[field.name] = int(raw) if isinstance(default, int) and not isinstance(default, bool) else float(raw)
        except (TypeError, ValueError):
            values[field.name] = default

    return SimConfig(**values)


def make_topology(cfg, seed):
    import numpy as np

    rng = np.random.default_rng(seed)
    gnbs = deploy_gnbs(cfg)
    ue_pos, ue_vel, services = init_ues(cfg, rng)

    return {
        "area_size_m": cfg.area_size_m,
        "dt_s": cfg.dt_s,
        "gnbs": [
            {"id": index + 1, "x": float(position[0]), "y": float(position[1])}
            for index, position in enumerate(gnbs)
        ],
        "ues": [
            {
                "id": index + 1,
                "x": float(ue_pos[index][0]),
                "y": float(ue_pos[index][1]),
                "vx": float(ue_vel[index][0]),
                "vy": float(ue_vel[index][1]),
                "service": str(services[index]),
            }
            for index in range(len(ue_pos))
        ],
    }


def summarize(rows):
    summary = {}
    methods = sorted({row["method"] for row in rows}, key=METHODS.index)

    for method in methods:
        method_rows = [row for row in rows if row["method"] == method]
        summary[method] = {}
        for metric in METRICS:
            values = [float(row[metric]) for row in method_rows]
            mean = sum(values) / len(values)
            sorted_values = sorted(values)
            midpoint = len(values) // 2
            if len(values) % 2:
                median = sorted_values[midpoint]
            else:
                median = (sorted_values[midpoint - 1] + sorted_values[midpoint]) / 2
            variance = sum((value - mean) ** 2 for value in values) / len(values)
            summary[method][metric] = {
                "mean": mean,
                "median": median,
                "std": variance ** 0.5,
                "min": min(values),
                "max": max(values),
            }
    return summary


def rows_to_csv(rows):
    if not rows:
        return ""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def run_task(payload):
    try:
        cfg = coerce_config(payload)
        repetitions = max(1, min(int(payload.get("repetitions", 10)), 500))
        base_seed = int(payload.get("base_seed", 42))
        methods = payload.get("methods") or METHODS
        methods = [method for method in methods if method in METHODS] or METHODS
        total = repetitions * len(methods)

        update_state(
            running=True,
            status="Running",
            message="Simulacao em execucao",
            completed=0,
            total=total,
            started_at=time.time(),
            finished_at=None,
            results=None,
            topology=make_topology(cfg, base_seed),
            error=None,
        )

        rows = []
        completed = 0
        for rep in range(repetitions):
            for index, method in enumerate(methods):
                seed = base_seed + rep * 100 + index
                rows.append(run_once(method, seed, cfg))
                completed += 1
                update_state(
                    completed=completed,
                    message=f"{completed}/{total} simulacoes completas",
                )

        results = {
            "rows": rows,
            "summary": summarize(rows),
            "csv": rows_to_csv(rows),
        }
        update_state(
            running=False,
            status="Finished",
            message="Simulacao finalizada",
            finished_at=time.time(),
            results=results,
        )
    except Exception as exc:
        traceback.print_exc()
        update_state(
            running=False,
            status="Error",
            message=f"Erro: {exc}",
            finished_at=time.time(),
            error=str(exc),
        )


class SimHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        print("[sim2] " + format % args)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            send_json(self, {"fields": config_fields(), "methods": METHODS})
            return
        if parsed.path == "/api/state":
            with STATE_LOCK:
                state = dict(STATE)
            send_json(self, state)
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/start":
            send_json(self, {"error": "Endpoint desconhecido"}, status=404)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            send_json(self, {"error": "JSON invalido"}, status=400)
            return

        with STATE_LOCK:
            if STATE["running"]:
                send_json(self, {"error": "Simulacao ja em execucao"}, status=409)
                return

        thread = threading.Thread(target=run_task, args=(payload,), daemon=True)
        thread.start()
        send_json(self, {"status": "starting"})


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), SimHandler)
    print(f"Simulador web rodando em http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuario")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
