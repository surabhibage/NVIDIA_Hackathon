import json
import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data)
            url = data.get("url")
        except:
            self.send_response(400)
            self.end_headers()
            return

        try:
            # 1. CAROLYNA (Ingestion): Fetching with a browser-like header
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            # Use a 10s timeout to prevent Vercel from killing the process
            with httpx.Client(headers=headers, follow_redirects=True, timeout=10.0) as client:
                response = client.get(url)
                response.raise_for_status() # Check if site exists
            
            soup = BeautifulSoup(response.text, 'html.parser')

            # 2. JULIA (Checker): Extracting the "Visual Manifest"
            image_details = []
            for img in soup.find_all('img'):
                alt = img.get('alt')
                image_details.append({
                    "src": img.get('src'),
                    "alt": alt if alt and alt.strip() else "MISSING"
                })

            headings = [h.name for h in soup.find_all(['h1', 'h2', 'h3'])]
            
            # 3. ASMITA (Reasoning Prep): Convert to Markdown
            # We remove script and style tags so the AI doesn't get confused
            for element in soup(["script", "style", "nav", "footer"]):
                element.decompose()
            
            markdown_content = md(str(soup), heading_style="ATX")

            # EXPLICIT RETURN FOR THE HACKATHON PIPELINE
            payload = {
                "status": "success",
                "markdown": markdown_content[:7000], # Clean text for LLM
                "visual_manifest": {                 # Substitution for screenshot
                    "image_count": len(image_details),
                    "image_details": image_details,
                    "headings": headings
                },
                "raw_html_snippet": str(soup)[:500] 
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        except Exception as e:
            # If it fails, return the error so the frontend can show it
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())