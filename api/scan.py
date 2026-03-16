import json
import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from http.server import BaseHTTPRequestHandler

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
            # 1. INGESTION (Carolyna): Fetch raw HTML
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            res = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
            soup = BeautifulSoup(res.text, 'html.parser')

            # 2. CHECKER (Julia): Extract Visual Metadata & Issues
            image_data = []
            issues = []
            
            # Image Check
            imgs = soup.find_all('img')
            for img in imgs:
                alt = img.get('alt')
                image_data.append({
                    "src": img.get('src'),
                    "alt": alt if alt else "MISSING"
                })
            
            missing_alt_count = len([i for i in image_data if i['alt'] == "MISSING"])
            if missing_alt_count > 0:
                issues.append(f"{missing_alt_count} images are missing alt text descriptions.")

            # Structure Check
            headings = [h.name for h in soup.find_all(['h1', 'h2', 'h3', 'h4'])]
            if 'h1' not in headings:
                issues.append("Page is missing an H1 main heading.")

            # 3. REASONING PREP: Convert to Markdown
            # Strip scripts/styles for a cleaner LLM context
            for script in soup(["script", "style"]):
                script.decompose()
            clean_markdown = md(str(soup), heading_style="ATX")

            # EXPLICIT RETURN OBJECT
            payload = {
                "status": "success",
                "url": url,
                "markdown": clean_markdown[:8000],  # Structured text for Asmita
                "issues": issues,                   # The Julia Agent's "Problem List"
                "visual_manifest": {                # The "Synthetic Screenshot"
                    "image_count": len(imgs),
                    "image_details": image_data,
                    "headings": headings,
                    "vibe_check": "Analyzed via structural metadata"
                }
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())