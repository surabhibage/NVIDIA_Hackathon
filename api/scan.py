import json
import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from http.server import BaseHTTPRequestHandler
from urllib.parse import urljoin, quote

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        url = json.loads(post_data).get("url")

        # --- CONFIGURATION ---
        # Replace with your ScreenshotOne or AbstractAPI key
        SCREENSHOT_API_KEY = "e40f4d2f2b398e82d6ff" 
        screenshot_url = f"https://api.screenshotone.com/take?access_key={SCREENSHOT_API_KEY}&url={quote(url)}&full_page=false&format=jpg"

        try:
            # 1. Fetch Page Content
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 2. Automated Accessibility Checklist Logic
            issue_list = []
            image_audit = []
            
            # Image Analysis
            imgs = soup.find_all('img')
            for img in imgs:
                alt = img.get('alt')
                src = img.get('src')
                is_flagged = not alt or alt.strip() == ""
                image_audit.append({
                    "url": urljoin(url, src) if src else None,
                    "alt_text": alt if alt else "MISSING",
                    "status": "Warning" if is_flagged else "Pass"
                })
            
            missing_alt = len([i for i in image_audit if i['status'] == "Warning"])
            if missing_alt > 0:
                issue_list.append(f"Detected {missing_alt} images missing alternative text descriptions.")

            # Structure Analysis
            headings = [h.name for h in soup.find_all(['h1', 'h2', 'h3'])]
            if 'h1' not in headings:
                issue_list.append("Document lacks an H1 heading; hierarchy may be unclear.")

            # Content Density Analysis
            long_paragraphs = [p for p in soup.find_all('p') if len(p.get_text().split()) > 80]
            if long_paragraphs:
                issue_list.append(f"Found {len(long_paragraphs)} high-density text blocks exceeding 80 words.")

            # 3. Process Text for LLM Context
            for element in soup(["script", "style"]):
                element.decompose()
            clean_markdown = md(str(soup), heading_style="ATX")

            # --- #COMMENT THIS OUT: DOWNLOAD SCREENSHOT FOR LOCAL ARCHIVE ---
            # if SCREENSHOT_API_KEY != "YOUR_API_KEY":
            #     raw_img = httpx.get(screenshot_url).content
            #     with open("latest_ingestion.jpg", "wb") as f:
            #         f.write(raw_img)
            # ----------------------------------------------------------------

            # 4. EXPLICIT OUTPUT FOR NEMOTRON REASONING
            payload = {
                "status": "success",
                "metadata": {
                    "source_url": url,
                    "timestamp": "2026-03-16"
                },
                "visual_data": {
                    "screenshot_link": screenshot_url,
                    "image_inventory": image_audit
                },
                "text_data": {
                    "markdown_content": clean_markdown[:8000] # Token-efficient context
                },
                "checklist_results": {
                    "automated_issues": issue_list
                }
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())