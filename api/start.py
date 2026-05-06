import json
import time
import traceback
from http.server import BaseHTTPRequestHandler

from api._common import (
    FileStopEvent,
    apply_simulation_parameters,
    clear_stop_request,
    coerce_params,
    parse_payload,
    send_json,
    simulation,
    write_state,
)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            data = parse_payload(self)
        except json.JSONDecodeError:
            send_json(self, {"error": "JSON invalido"}, status=400)
            return

        params = coerce_params(data)
        clear_stop_request()
        apply_simulation_parameters(params)
        write_state(
            running=True,
            message="Running",
            done=False,
            params=params,
            last_snapshot=None,
        )

        last_flush = 0.0

        def step_callback(snapshot):
            nonlocal last_flush
            now = time.monotonic()
            if snapshot.get("progress") == 100 or now - last_flush >= 0.5:
                write_state(
                    running=True,
                    message="Running",
                    done=False,
                    last_snapshot=snapshot,
                )
                last_flush = now

        try:
            simulation.run_simulation(
                show_progress=False,
                step_callback=step_callback,
                stop_event=FileStopEvent(),
                cmf_mode=params["cmf_mode"],
                export_bs_results=False,
            )
            state = write_state(running=False, message="Finished", done=True)
            send_json(self, {"status": "finished", "state": state})
        except Exception as exc:
            traceback.print_exc()
            state = write_state(running=False, message=f"Error: {exc}", done=True)
            send_json(self, {"error": str(exc), "state": state}, status=500)

