import json
import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from http.server import BaseHTTPRequestHandler
from urllib.parse import urljoin

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        url = json.loads(post_data).get("url")

        if not url:
            self.send_response(400)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Missing 'url'"}).encode())
            return

        try:
            # Fetch page
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            page_title = soup.title.string.strip() if soup.title and soup.title.string else None
            viewport_meta = soup.find("meta", attrs={"name": "viewport"}) is not None

            # -------------------------
            # Images
            # -------------------------
            images = []
            for img in soup.find_all("img"):
                src = img.get("src")
                alt = img.get("alt", "MISSING")

                if src:
                    images.append({
                        "url": urljoin(url, src),
                        "alt": alt,
                        "accessible": alt != "MISSING"
                    })

            # -------------------------
            # Headings
            # -------------------------
            headings = []
            for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                for heading in soup.find_all(tag):
                    text = heading.get_text(" ", strip=True)
                    if text:
                        headings.append({
                            "level": tag,
                            "text": text
                        })

            # -------------------------
            # Form Labels
            # -------------------------
            label_map = {}

            for label in soup.find_all("label"):
                label_text = label.get_text(" ", strip=True)
                target = label.get("for")
                if target:
                    label_map[target] = label_text

            forms = []
            for field in soup.find_all(["input", "textarea", "select"]):
                field_id = field.get("id")
                label = None

                if field_id and field_id in label_map:
                    label = label_map[field_id]

                if label is None:
                    parent_label = field.find_parent("label")
                    if parent_label:
                        label = parent_label.get_text(" ", strip=True)

                forms.append({
                    "tag": field.name,
                    "type": field.get("type", field.name),
                    "name": field.get("name"),
                    "id": field_id,
                    "label": label,
                    "placeholder": field.get("placeholder"),
                    "aria_label": field.get("aria-label")
                })

            # -------------------------
            # Interactive Elements
            # -------------------------
            interactive_elements = []

            for el in soup.find_all(["a", "button", "input", "select", "textarea", "div", "span"]):
                onclick = el.get("onclick") is not None
                role = el.get("role")
                text = el.get_text(" ", strip=True)

                if el.name in ["a", "button", "input", "select", "textarea"] or onclick or role in ["button", "link"]:
                    interactive_elements.append({
                        "tag": el.name,
                        "text": text,
                        "href": el.get("href"),
                        "onclick": onclick,
                        "role": role,
                        "tabindex": el.get("tabindex"),
                        "aria_label": el.get("aria-label")
                    })

            # -------------------------
            # Links
            # -------------------------
            links = []

            for link in soup.find_all("a"):
                href = link.get("href")

                if href:
                    links.append({
                        "href": urljoin(url, href),
                        "text": link.get_text(" ", strip=True),
                        "title": link.get("title"),
                        "aria_label": link.get("aria-label")
                    })

            # -------------------------
            # Videos
            # -------------------------
            videos = []

            for video in soup.find_all("video"):
                tracks = video.find_all("track")

                has_captions = any(
                    track.get("kind") == "captions" for track in tracks
                )

                videos.append({
                    "src": video.get("src"),
                    "has_captions": has_captions,
                    "track_count": len(tracks)
                })

            # -------------------------
            # Paragraphs / Text
            # -------------------------
            paragraphs = []

            for paragraph in soup.find_all("p"):
                text = paragraph.get_text(" ", strip=True)
                if text:
                    paragraphs.append(text)

            page_text = soup.get_text("\n", strip=True)

            # -------------------------
            # Color signals (for Nemotron)
            # -------------------------
            color_signals = []

            for element in soup.find_all(True):
                style = element.get("style", "")
                text = element.get_text(" ", strip=True)

                if style and ("color:" in style or "background" in style):
                    color_signals.append({
                        "tag": element.name,
                        "text": text[:120],
                        "style": style
                    })

            # Remove scripts/styles before markdown conversion
            for script in soup(["script", "style"]):
                script.decompose()

            clean_markdown = md(str(soup), heading_style="ATX")

            payload = {
                "url": url,
                "page_title": page_title,
                "markdown": clean_markdown[:10000],
                "page_text": page_text[:15000],
                "paragraphs": paragraphs[:200],
                "images": images,
                "headings": headings,
                "forms": forms,
                "interactive_elements": interactive_elements,
                "links": links,
                "videos": videos,
                "viewport_meta": viewport_meta,
                "color_signals": color_signals[:100],
                "status": "success"
            }

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())