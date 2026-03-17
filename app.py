import os
import json
import requests
from dotenv import load_dotenv

from accessibility_checks import accessibility_checks

load_dotenv()

SCAN_API_URL = os.getenv("SCAN_API_URL", "http://localhost:8000/api/scan")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "nvidia/nemotron-3-super-120b-a12b")

OUTPUT_FILE = "output.json"
SAMPLE_INPUT_FILE = "sample_input.json"


def call_scan_api(url: str) -> dict:
    response = httpx.post(
        SCAN_API_URL,
        json={"url": url},
        timeout=60.0
    )
    response.raise_for_status()
    return response.json()


def build_nemotron_prompt(scan_data: dict, issues_data: dict) -> str:
    page_title = scan_data.get("page_title")
    page_text = scan_data.get("page_text", "")
    color_signals = scan_data.get("color_signals", [])
    issues = issues_data.get("issues", [])

    return f"""
You are an accessibility and usability reasoning agent.

Your task is to analyze website accessibility findings and produce a final human-friendly report.

Website title:
{page_title}

Page text excerpt:
{page_text[:3000]}

Detected accessibility issues:
{json.dumps(issues, indent=2)}

Color/style hints:
{json.dumps(color_signals[:10], indent=2)}

Focus especially on:
- color accessibility and likely contrast concerns
- which users are affected
- which issues should be prioritized first
- concrete fixes

Return VALID JSON ONLY in this exact format:
{{
  "summary": "short summary",
  "top_issues": [
    {{
      "title": "issue title",
      "category": "Accessibility category",
      "evidence": ["specific evidence"],
      "suggested_fix": "clear fix",
      "priority": 1
    }}
  ],
  "persona_notes": [
    {{
      "persona": "functional persona",
      "insight": "why this matters"
    }}
  ],
  "final_recommendation": "1-2 sentence recommendation"
}}
""".strip()


def call_nemotron(prompt: str) -> dict:
    if not NVIDIA_API_KEY:
        return {
            "summary": "Nemotron was not called because NVIDIA_API_KEY is missing.",
            "top_issues": [],
            "persona_notes": [],
            "final_recommendation": "Set NVIDIA_API_KEY in your environment to enable AI reasoning."
        }

    url = "https://integrate.api.nvidia.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": "You are a precise accessibility reasoning assistant. Return valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "top_p": 0.9,
        "max_tokens": 1800,
        "stream": False
    }

    response = httpx.post(url, headers=headers, json=payload, timeout=120.0)
    response.raise_for_status()

    data = response.json()
    content = data["choices"][0]["message"]["content"]

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "summary": "Nemotron returned non-JSON output.",
            "raw_output": content
        }


def run_pipeline(url: str) -> dict:
    # Step 1: Scan page
    scan_data = call_scan_api(url)

    # Save intermediate input for debugging / team handoff
    with open(SAMPLE_INPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(scan_data, f, indent=2, ensure_ascii=False)

    # Step 2: Run deterministic accessibility checks
    issues_data = accessibility_checks(scan_data)

    # Step 3: Build Nemotron prompt
    prompt = build_nemotron_prompt(scan_data, issues_data)

    # Step 4: Call Nemotron
    nemotron_output = call_nemotron(prompt)

    # Step 5: Final combined result
    final_result = {
        "url": url,
        "scan_data": scan_data,
        "accessibility_checks": issues_data,
        "nemotron_output": nemotron_output
    }

    return final_result


def main():
    url = input("Enter website URL: ").strip()

    if not url:
        print("No URL provided.")
        return

    try:
        result = run_pipeline(url)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print("\nFinal output saved to output.json\n")
        print(json.dumps(result["nemotron_output"], indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Pipeline failed: {e}")


if __name__ == "__main__":
    main()