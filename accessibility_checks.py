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

    # Screen reader capability
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

    return {
        "issues": issues
    }


# --------- SCREEN READER CAPABILITY ---------

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
        "count": len(missing),
        "ratio_missing": ratio_missing,
        "severity": "high" if len(missing) > 0 else "none",
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
        "count": len(issues),
        "heading_structure_score": max(score, 0),
        "severity": severity,
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
        "count": len(missing),
        "severity": "high" if len(missing) > 0 else "none",
        "evidence": missing[:3]
    }


def check_missing_page_title(page_title):
    missing = page_title is None or str(page_title).strip() == ""

    return {
        "issue_type": "missing_page_title",
        "count": 1 if missing else 0,
        "severity": "medium" if missing else "none",
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
        "count": len(bad),
        "severity": "medium" if len(bad) > 0 else "none",
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
        "count": len(long_paragraphs),
        "severity": "medium" if len(long_paragraphs) > 0 else "none",
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
        "count": 1 if text_heavy else 0,
        "severity": "medium" if text_heavy else "none",
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
        "count": len(missing),
        "severity": "high" if len(missing) > 0 else "none",
        "evidence": missing[:3]
    }


# --------- COLOR ACCESSIBILITY ---------
# Nemotron / Agent 3 should interpret screenshot + color_signals for contrast issues.

def check_color_signal_presence(color_signals):
    return {
        "issue_type": "color_signal_elements_detected",
        "count": len(color_signals),
        "severity": "info",
        "evidence": color_signals[:5]
    }


# --------- MOBILE ACCESSIBILITY ---------

def check_mobile_viewport(viewport_meta):
    return {
        "issue_type": "missing_mobile_viewport",
        "count": 0 if viewport_meta else 1,
        "severity": "medium" if not viewport_meta else "none",
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
        "count": len(bad),
        "severity": "high" if len(bad) > 0 else "none",
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
        "count": len(unfocusable),
        "severity": "high" if len(unfocusable) > 0 else "none",
        "evidence": unfocusable[:3]
    }