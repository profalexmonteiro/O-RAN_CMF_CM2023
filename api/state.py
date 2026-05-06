from http.server import BaseHTTPRequestHandler

from api._common import read_state, send_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        send_json(self, read_state())

