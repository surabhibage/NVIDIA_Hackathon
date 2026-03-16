import json
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):

    def do_POST(self):

        length = int(self.headers.get("content-length"))
        body = self.rfile.read(length)
        data = json.loads(body)

        url = data["url"]

        response = {
            "status": "success",
            "received_url": url
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        self.wfile.write(json.dumps(response).encode())