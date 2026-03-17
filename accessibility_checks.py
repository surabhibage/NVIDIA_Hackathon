import json


def build_agent3_input(ingestion_data):
    """
    Main Agent 2 entrypoint.
    Takes ingestion output and returns the exact JSON shape Agent 3 expects.
    """
    checker_result = accessibility_checks(ingestion_data)

    return {
        "url": ingestion_data.get("url"),
        "screenshot_path": ingestion_data.get("screenshot_path"),
        "page_text": ingestion_data.get("page_text") or ingestion_data.get("markdown", ""),
        "issues": checker_result["issues"]
    }


def save_agent3_input(ingestion_data, output_path="agent3_nemotron/input.json"):
    """
    Runs checker and saves Agent 3 input JSON to disk.
    """
    output = build_agent3_input(ingestion_data)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return output


def accessibility_checks(ingestion_data):
    issues = []

    images = ingestion_data.get("images", [])
    headings = ingestion_data.get("headings", [])
    forms = ingestion_data.get("forms", [])
    page_text = ingestion_data.get("page_text") or ingestion_data.get("markdown", "")
    paragraphs = ingestion_data.get("paragraphs", [])
    interactive_elements = ingestion_data.get("interactive_elements", [])
    viewport_meta = ingestion_data.get("viewport_meta", False)
    links = ingestion_data.get("links", [])
    videos = ingestion_data.get("videos", [])
    color_signals = ingestion_data.get("color_signals", [])
    page_title = ingestion_data.get("page_title")

    # Screen reader compatibility
    issues.append(check_missing_alt(images))
    issues.append(check_headings(headings))
    issues.append(check_form_labels(forms))
    issues.append(check_missing_page_title(page_title))
    issues.append(check_non_descriptive_links(links))

    # Cognitive accessibility
    issues.append(check_long_paragraphs(page_text, paragraphs))
    issues.append(check_text_blocks_without_headings(page_text, headings, paragraphs))

    # Media accessibility
    issues.append(check_video_captions(videos))

    # Mobile accessibility
    issues.append(check_mobile_viewport(viewport_meta))

    # Keyboard accessibility
    issues.append(check_nonsemantic_clickables(interactive_elements))
    issues.append(check_keyboard_focus(interactive_elements))

    # Color accessibility handoff for Nemotron
    issues.append(check_color_signal_presence(color_signals))

    # Optional: remove "none" issues if you only want surfaced problems
    filtered_issues = [issue for issue in issues if issue.get("severity") != "none"]

    return {
        "issues": filtered_issues
    }


# --------- SCREEN READER COMPATIBILITY ---------

def check_missing_alt(images):
    missing = []

    for img in images:
        alt = img.get("alt")
        if alt is None or str(alt).strip() == "" or str(alt).strip().upper() == "MISSING":
            missing.append(img)

    total_images = len(images)
    ratio_missing = (len(missing) / total_images) if total_images > 0 else 0

    return {
        "issue_type": "missing_alt_text",
        "category": "Screen Reader Compatibility",
        "count": len(missing),
        "ratio_missing": ratio_missing,
        "severity": "high" if len(missing) > 0 else "none",
        "description": f"{len(missing)} images are missing alt text." if len(missing) > 0 else "No missing alt text detected.",
        "evidence": missing[:3]
    }


def check_headings(headings):
    heading_levels = [h.get("level", "").lower() for h in headings]
    has_h1 = "h1" in heading_levels
    heading_count = len(headings)

    issues = []

    if not has_h1:
        issues.append("missing_h1")

    if heading_count < 2:
        issues.append("few_headings")

    score = 100

    if not has_h1:
        score -= 60

    if heading_count < 2:
        score -= 25

    if heading_count == 0:
        score = 0

    if score < 50:
        severity = "high"
    elif score < 80:
        severity = "medium"
    else:
        severity = "none"

    return {
        "issue_type": "weak_heading_structure",
        "category": "Screen Reader Compatibility",
        "count": len(issues),
        "heading_structure_score": max(score, 0),
        "severity": severity,
        "description": (
            "Heading structure is weak or incomplete."
            if len(issues) > 0
            else "Heading structure appears sufficient."
        ),
        "evidence": issues
    }


def check_form_labels(forms):
    missing = []

    for field in forms:
        label = field.get("label")
        aria_label = field.get("aria_label")
        placeholder = field.get("placeholder")

        if not label and not aria_label and not placeholder:
            missing.append(field)

    return {
        "issue_type": "missing_form_labels",
        "category": "Screen Reader Compatibility",
        "count": len(missing),
        "severity": "high" if len(missing) > 0 else "none",
        "description": (
            f"{len(missing)} form fields are missing clear labels."
            if len(missing) > 0
            else "No missing form labels detected."
        ),
        "evidence": missing[:3]
    }


def check_missing_page_title(page_title):
    missing = page_title is None or str(page_title).strip() == ""

    return {
        "issue_type": "missing_page_title",
        "category": "Screen Reader Compatibility",
        "count": 1 if missing else 0,
        "severity": "medium" if missing else "none",
        "description": (
            "Page title is missing or empty."
            if missing
            else "Page title is present."
        ),
        "evidence": [] if not missing else ["Page title missing or empty"]
    }


def check_non_descriptive_links(links):
    vague_terms = {
        "click here",
        "here",
        "learn more",
        "read more",
        "more",
        "link"
    }

    bad = []

    for link in links:
        text = (link.get("text") or link.get("aria_label") or "").strip().lower()
        if text in vague_terms or text == "":
            bad.append(link)

    return {
        "issue_type": "non_descriptive_links",
        "category": "Screen Reader Compatibility",
        "count": len(bad),
        "severity": "medium" if len(bad) > 0 else "none",
        "description": (
            f"{len(bad)} links use vague or non-descriptive text."
            if len(bad) > 0
            else "No non-descriptive links detected."
        ),
        "evidence": bad[:3]
    }


# --------- COGNITIVE ACCESSIBILITY ---------

def check_long_paragraphs(page_text, paragraphs):
    if paragraphs:
        paragraph_list = [p.strip() for p in paragraphs if p and p.strip()]
    else:
        paragraph_list = [p.strip() for p in page_text.split("\n") if p.strip()]

    long_paragraphs = [p for p in paragraph_list if len(p) > 408]

    return {
        "issue_type": "long_paragraphs",
        "category": "Cognitive Accessibility",
        "count": len(long_paragraphs),
        "severity": "medium" if len(long_paragraphs) > 0 else "none",
        "description": (
            f"{len(long_paragraphs)} paragraphs exceed the readability threshold."
            if len(long_paragraphs) > 0
            else "No long paragraphs detected."
        ),
        "evidence": long_paragraphs[:2]
    }


def check_text_blocks_without_headings(page_text, headings, paragraphs):
    if paragraphs:
        paragraph_list = [p.strip() for p in paragraphs if p and p.strip()]
    else:
        paragraph_list = [p.strip() for p in page_text.split("\n") if p.strip()]

    heading_count = len(headings)
    long_paragraphs = [p for p in paragraph_list if len(p) > 250]
    text_heavy = len(long_paragraphs) >= 2 and heading_count < 2

    return {
        "issue_type": "text_blocks_without_headings",
        "category": "Cognitive Accessibility",
        "count": 1 if text_heavy else 0,
        "severity": "medium" if text_heavy else "none",
        "description": (
            "Text-heavy content appears without enough heading structure."
            if text_heavy
            else "Text blocks appear reasonably structured."
        ),
        "evidence": {
            "long_paragraph_count": len(long_paragraphs),
            "heading_count": heading_count
        }
    }


# --------- MEDIA ACCESSIBILITY ---------

def check_video_captions(videos):
    missing = [video for video in videos if not video.get("has_captions", False)]

    return {
        "issue_type": "video_missing_captions",
        "category": "Media Accessibility",
        "count": len(missing),
        "severity": "high" if len(missing) > 0 else "none",
        "description": (
            f"{len(missing)} videos are missing captions."
            if len(missing) > 0
            else "No missing video captions detected."
        ),
        "evidence": missing[:3]
    }


# --------- COLOR ACCESSIBILITY ---------
# Nemotron / Agent 3 should interpret screenshot + color_signals for contrast issues.

def check_color_signal_presence(color_signals):
    return {
        "issue_type": "color_signal_elements_detected",
        "category": "Color Accessibility",
        "count": len(color_signals),
        "severity": "info",
        "description": f"{len(color_signals)} color-relevant UI elements were detected for multimodal analysis.",
        "evidence": color_signals[:5]
    }


# --------- MOBILE / TOUCH ACCESSIBILITY ---------

def check_mobile_viewport(viewport_meta):
    return {
        "issue_type": "missing_mobile_viewport",
        "category": "Mobile / Touch Accessibility",
        "count": 0 if viewport_meta else 1,
        "severity": "medium" if not viewport_meta else "none",
        "description": (
            "Viewport meta tag is missing, which may affect mobile rendering."
            if not viewport_meta
            else "Viewport meta tag is present."
        ),
        "evidence": {
            "viewport_meta_present": viewport_meta
        }
    }


# --------- KEYBOARD ACCESSIBILITY ---------

def check_nonsemantic_clickables(interactive_elements):
    bad = []

    for el in interactive_elements:
        tag = el.get("tag", "").lower()
        onclick = el.get("onclick", False)
        role = (el.get("role") or "").lower()

        if onclick and tag not in ["button", "a"] and role not in ["button", "link"]:
            bad.append(el)

    return {
        "issue_type": "nonsemantic_clickables",
        "category": "Keyboard Accessibility",
        "count": len(bad),
        "severity": "high" if len(bad) > 0 else "none",
        "description": (
            f"{len(bad)} clickable elements are non-semantic and may break keyboard workflows."
            if len(bad) > 0
            else "No non-semantic clickable elements detected."
        ),
        "evidence": bad[:3]
    }


def check_keyboard_focus(interactive_elements):
    unfocusable = []

    for el in interactive_elements:
        tag = el.get("tag", "").lower()
        onclick = el.get("onclick", False)
        tabindex = el.get("tabindex")
        role = (el.get("role") or "").lower()

        if (
            onclick
            and tag not in ["button", "a", "input", "select", "textarea"]
            and tabindex is None
            and role not in ["button", "link"]
        ):
            unfocusable.append(el)

    return {
        "issue_type": "keyboard_unfocusable_elements",
        "category": "Keyboard Accessibility",
        "count": len(unfocusable),
        "severity": "high" if len(unfocusable) > 0 else "none",
        "description": (
            f"{len(unfocusable)} interactive elements may not be reachable by keyboard."
            if len(unfocusable) > 0
            else "No keyboard-unfocusable elements detected."
        ),
        "evidence": unfocusable[:3]
    }


if __name__ == "__main__":
    # Example local test
    example_ingestion_data = {
        "url": "https://example.com",
        "screenshot_path": "agent3_nemotron/outputs/amazon_screenshot.png",
        "page_text": "Welcome to our site.\n\nThis is a very long paragraph that might cause readability issues..." * 20,
        "images": [{"src": "hero.png", "alt": ""}],
        "headings": [{"level": "h2", "text": "Welcome"}],
        "forms": [{"type": "text", "label": None, "aria_label": None, "placeholder": None}],
        "paragraphs": ["This is a short paragraph.", "A" * 500],
        "interactive_elements": [{"tag": "div", "onclick": True, "role": None, "tabindex": None}],
        "viewport_meta": False,
        "links": [{"text": "Click here"}],
        "videos": [{"src": "intro.mp4", "has_captions": False}],
        "color_signals": [{"element": "cta_button", "foreground": "#ffffff", "background": "#d3bfb3"}],
        "page_title": ""
    }

    result = save_agent3_input(example_ingestion_data, output_path="input.json")
    print(json.dumps(result, indent=2, ensure_ascii=False))
