# app.py - Nemotron Reasoning Agent (Multimodal color accessibility)
#
# Usage:
# 1. Ensure .env has NVIDIA_API_KEY and MODEL_NAME
# 2. Ensure sample_input.json contains screenshot_path, page_text, issues[]
# 3. python3 app.py
#
import os
import json
import base64
import io
import re
from collections import Counter
from dotenv import load_dotenv
import requests
from PIL import Image

load_dotenv()

API_KEY = os.getenv("NVIDIA_API_KEY")
MODEL = os.getenv("MODEL_NAME", "nvidia/nemotron-3-super-120b-a12b")

INPUT_FILE = "sample_input.json"
OUTPUT_FILE = "output.json"

# -----------------------
# Image & color helpers
# -----------------------
def image_to_data_uri(path, max_width=900, quality=70):
    """Resize/compress image to JPEG and return data URI (or None if error)."""
    try:
        img = Image.open(path).convert("RGB")
    except Exception as e:
        print("image_to_data_uri: cannot open image:", e)
        return None

    w, h = img.size
    if w > max_width:
        new_h = int(h * (max_width / w))
        img = img.resize((max_width, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    try:
        img.save(buf, format="JPEG", quality=quality, optimize=True)
    except Exception:
        img.save(buf, format="JPEG", quality=quality)

    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{b64}"
    return data_uri


def get_dominant_colors(path, n=4, sample_size=200):
    """Return up to n dominant RGB tuples (fast, heuristic)."""
    try:
        img = Image.open(path).convert("RGB")
    except Exception as e:
        print("get_dominant_colors: cannot open image:", e)
        return []

    img.thumbnail((sample_size, sample_size))
    # Pillow getdata deprecation warning is harmless — leaving as-is for compatibility
    pixels = list(img.getdata())
    counts = Counter(pixels)
    most_common = counts.most_common(n)
    return [c[0] for c in most_common]


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def relative_luminance(rgb):
    def chan(c):
        c = c / 255.0
        if c <= 0.03928:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast_ratio(rgb1, rgb2):
    L1 = relative_luminance(rgb1)
    L2 = relative_luminance(rgb2)
    lighter = max(L1, L2)
    darker = min(L1, L2)
    return (lighter + 0.05) / (darker + 0.05)


def prepare_screenshot_data(screenshot_path):
    """
    Prepare compact screenshot evidence:
    - image_data_uri: small jpeg data URI (or None)
    - dominant_colors: list of hex strings
    - contrast_examples: list of dicts {fg, bg, contrast}
    - screenshot_description: short text hint
    """
    metrics = {
        "image_data_uri": None,
        "dominant_colors": [],
        "contrast_examples": [],
        "screenshot_description": ""
    }

    # image data uri (resized JPEG). Note: might be large; we'll include only if reasonably small.
    try:
        data_uri = image_to_data_uri(screenshot_path, max_width=900, quality=70)
        if data_uri and len(data_uri) < 450000:  # ~450 KB threshold; tweak if needed
            metrics["image_data_uri"] = data_uri
        else:
            # still record presence but avoid huge payloads
            metrics["image_data_uri"] = None
            if data_uri:
                print("prepare_screenshot_data: image_data_uri too large to embed (len {}). skipping raw image".format(len(data_uri)))
    except Exception as e:
        print("prepare_screenshot_data: image->data_uri error:", e)
        metrics["image_data_uri"] = None

    # dominant colors + contrast examples
    try:
        dom = get_dominant_colors(screenshot_path, n=4, sample_size=200)
        hexes = [rgb_to_hex(c) for c in dom]
        metrics["dominant_colors"] = hexes

        examples = []
        if len(dom) >= 2:
            # pair primary (dom[0]) with others
            primary = dom[0]
            for i in range(1, len(dom)):
                bg = dom[i]
                cr = round(contrast_ratio(primary, bg), 2)
                examples.append({"fg": rgb_to_hex(primary), "bg": rgb_to_hex(bg), "contrast": cr})
        metrics["contrast_examples"] = examples
    except Exception as e:
        print("prepare_screenshot_data: color metrics error:", e)

    metrics["screenshot_description"] = (
        "Screenshot likely shows a dark header and lighter content area with a colored CTA. "
        "Use dominant_colors and contrast_examples to reason about color accessibility."
    )

    return metrics

# -----------------------
# Input/Prompt building
# -----------------------
def load_input():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_prompt(data, screenshot_data=None):
    """
    Build a single textual prompt that includes:
    - page excerpt
    - detected issues
    - compact screenshot metrics
    - (optionally) mentions that a data URI is available
    Ask Nemotron to focus on COLOR ACCESSIBILITY and return JSON only.
    """
    issues_text = json.dumps(data.get("issues", []), indent=2, ensure_ascii=False)
    page_excerpt = (data.get("page_text") or "")[:1200]  # truncated for safety

    color_section = ""
    if screenshot_data:
        if screenshot_data.get("dominant_colors"):
            color_section += f"- dominant_colors: {screenshot_data['dominant_colors']}\n"
        if screenshot_data.get("contrast_examples"):
            color_section += "- contrast_examples:\n"
            for ex in screenshot_data["contrast_examples"]:
                color_section += f"  - fg: {ex['fg']}, bg: {ex['bg']}, contrast: {ex['contrast']}\n"
        color_section += f"- screenshot_description: {screenshot_data.get('screenshot_description','')}\n"

        # If small image present, mention it; the actual data URI is embedded as 'image_data_uri' in the prompt below if available.
        if screenshot_data.get("image_data_uri"):
            color_section += "- image_data_uri_present: true (data URI included below)\n"
        else:
            color_section += "- image_data_uri_present: false (image omitted; use metrics)\n"

    template = """
You are an accessibility and usability reasoning agent for a web page. Focus especially on COLOR ACCESSIBILITY.

INPUTS:
- URL: {url}
- Page text excerpt: {page_excerpt}
- Detected issues (from the checker): {issues_text}

COLOR EVIDENCE:
{color_section}

If an 'image_data_uri' is present below, it is a resized JPEG of the page screenshot encoded as a data URI. The model may use it for direct visual inspection. If not, use the provided dominant_colors and contrast_examples.

TASK (COLOR ACCESSIBILITY):
1) Use the provided screenshot (if data URI is present) and the numeric color metrics to evaluate color accessibility.
   - For each contrast_example, state whether it meets WCAG AA for normal text (>=4.5:1) and AA for large text (>=3.0:1), and whether it meets AAA (>=7:1).
   - Identify color-blind risks (deuteranopia/protanopia/tritanopia) for the detected palette and name which UI elements (header, body text, CTA, status indicators) are likely impacted.
2) For each failing or risky UI element produce:
   - concrete evidence (e.g., "contrast_examples[0] ratio=2.1")
   - 2 alternate color pairs (hex codes) that meet WCAG AA for normal text, and 1 pair that meets AAA if possible
   - a short CSS snippet showing the fix (e.g., ".cta {{ background: #0057b7; color: #ffffff; }}")
3) Prioritize the fixes (1 highest) and explain which functional user groups they help (low-vision users, dyslexia-sensitive readers, first-time mobile users).
4) For every claim reference the evidence you used (dominant_colors index or contrast_examples entry).

RETURN valid JSON ONLY with this exact shape:
{{
  "summary": "short summary",
  "top_issues": [
    {{
      "title": "issue title",
      "category": "Color Accessibility",
      "evidence": ["contrast_examples[0] shows ratio 2.1"],
      "suggested_fix": "textual description",
      "css_snippet": "exact CSS snippet",
      "priority": 1
    }}
  ],
  "persona_notes":[
    {{
      "persona":"functional persona description",
      "insight":"..."
    }}
  ]
}}

Now, if an image_data_uri is present, it follows below after the marker:
"""

    # safe .format substitution (we escape literal braces in the template above)
    prompt = template.format(
        url=data.get("url", ""),
        page_excerpt=page_excerpt.replace("{", "{{").replace("}", "}}"),
        issues_text=issues_text.replace("{", "{{").replace("}", "}}"),
        color_section=color_section
    )

    # if small image exists, append it AFTER the prompt text so the model sees it (still part of the message content)
    if screenshot_data and screenshot_data.get("image_data_uri"):
        prompt = prompt + "\n[image_data_uri_start]\n" + screenshot_data["image_data_uri"] + "\n[image_data_uri_end]\n"

    return prompt

# -----------------------
# Model call (NVIDIA integrate)
# -----------------------
def call_model(prompt):
    if not API_KEY:
        raise RuntimeError("Missing NVIDIA API key (NVIDIA_API_KEY) in environment.")

    url = "https://integrate.api.nvidia.com/v1/chat/completions"

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "top_p": 0.9,
        "max_tokens": 2500,
        "stream": False
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    print("Status code:", resp.status_code)
    # print raw only when debugging
    # print("Raw response:", resp.text[:800] + ("... (truncated)" if len(resp.text) > 800 else ""))

    resp.raise_for_status()
    data = resp.json()
    # Safety: ensure the model returned a text message
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("No choices returned from model: " + json.dumps(data)[:400])

    content = choices[0].get("message", {}).get("content")
    if not content:
        # fallback: return full response text
        return json.dumps(data)
    return content

# -----------------------
# JSON extraction helpers
# -----------------------
def extract_first_json(text: str):
    """
    Find the first top-level JSON object in text by scanning for balanced braces.
    Returns the JSON string or None.
    """
    if not text or "{" not in text:
        return None

    # Try to find the first '{' and balance braces
    start = text.find("{")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if ch == '"' and not escape:
            in_string = not in_string
        if ch == "\\" and not escape:
            escape = True
        else:
            escape = False

        if not in_string:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    # candidate JSON substring
                    return text[start:i+1]
    return None


def try_fix_json_candidate(s: str):
    """
    Try some lightweight repairs to help json.loads succeed:
    - convert smart quotes to normal
    - remove trailing commas before } or ]
    - replace single quotes for keys/strings when safe
    """
    if s is None:
        return None
    # normalize smart quotes
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    # remove trailing commas like {"a":1,}
    s = re.sub(r",\s*}", "}", s)
    s = re.sub(r",\s*]", "]", s)
    # if JSON uses single quotes for strings (rare for model output), attempt to convert:
    # only if the string seems to use single quotes for keys/values and double quotes aren't present
    if "'" in s and '"' not in s:
        s = s.replace("'", '"')
    return s

# -----------------------
# Main flow
# -----------------------
def main():
    print("Starting Nemotron reasoning agent (multimodal color accessibility)...")

    if not API_KEY:
        print("Missing NVIDIA_API_KEY in your .env. Add it and re-run.")
        return
    if not MODEL:
        print("Missing MODEL_NAME in your .env. Add it and re-run.")
        return

    data = load_input()
    screenshot_path = data.get("screenshot_path")
    screenshot_data = None
    if screenshot_path:
        if not os.path.exists(screenshot_path):
            print(f"Warning: screenshot_path does not exist: {screenshot_path}")
        else:
            screenshot_data = prepare_screenshot_data(screenshot_path)

    prompt = build_prompt(data, screenshot_data)
    print("Sending request to Nemotron (this may take a few seconds)...")
    result_text = call_model(prompt)

    # try to parse the model response as JSON robustly
    try:
        parsed = json.loads(result_text)
    except Exception:
        # attempt extraction and lightweight repair
        candidate = extract_first_json(result_text)
        parsed = None
        if candidate:
            candidate_fixed = try_fix_json_candidate(candidate)
            try:
                parsed = json.loads(candidate_fixed)
            except Exception:
                # last-ditch attempt: strip control characters and retry
                candidate_fixed2 = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", candidate_fixed)
                try:
                    parsed = json.loads(candidate_fixed2)
                except Exception:
                    parsed = None

        if parsed is None:
            # fallback: save raw output + candidate snippet for debugging
            parsed = {"_raw_output": result_text}
            if candidate:
                parsed["_candidate_json_extract"] = candidate[:2000]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False)

    print(f"Saved parsed output to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()