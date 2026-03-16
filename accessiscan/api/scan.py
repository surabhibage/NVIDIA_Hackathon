import json
from http.server import BaseHTTPRequestHandler
from crawler import crawl_sync


class handler(BaseHTTPRequestHandler):

    def do_POST(self):

        length = int(self.headers.get("content-length"))
        body = self.rfile.read(length)
        data = json.loads(body)

        url = data["url"]

        result = crawl_sync(url)

        response = {
            "status": "success",
            "text_length": len(result["markdown"]),
            "screenshot": result["screenshot"] is not None
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        self.wfile.write(json.dumps(response).encode())