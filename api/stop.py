from http.server import BaseHTTPRequestHandler

from api._common import STOP_PATH, send_json, write_state


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        with open(STOP_PATH, "w", encoding="utf-8") as stop_file:
            stop_file.write("stop")
        write_state(running=True, message="Stopping", done=False)
        send_json(self, {"status": "stopping"})

