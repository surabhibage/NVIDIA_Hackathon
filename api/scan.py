import json
import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from http.server import BaseHTTPRequestHandler
from urllib.parse import urljoin

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        url = json.loads(post_data).get("url")

        if not url:
            self.send_response(400)
            self.end_headers()
            return

        try:
            # 1. Fetch the page (with a user-agent to avoid blocks)
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
            
            # 2. Parse with BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 3. Extract Images & Metadata (Since we can't do a full screenshot)
            images = []
            for img in soup.find_all('img'):
                src = img.get('src')
                alt = img.get('alt', 'MISSING')
                if src:
                    images.append({
                        "url": urljoin(url, src),
                        "alt": alt,
                        "accessible": alt != 'MISSING'
                    })

            # 4. Convert HTML to Markdown for your AI persona engine
            # We strip scripts and styles to keep it clean
            for script in soup(["script", "style"]):
                script.decompose()
            
            clean_markdown = md(str(soup), heading_style="ATX")

            # 5. Return the payload
            payload = {
                "url": url,
                "markdown": clean_markdown[:10000], # Truncate to save bandwidth
                "images": images,
                "status": "success"
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())