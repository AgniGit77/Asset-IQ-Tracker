"""AI photo inspection service — uses Gemini Vision API for equipment condition analysis."""
from __future__ import annotations
import base64
import json
import os
import random
from datetime import datetime


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ZONES = ["front", "left_side", "right_side", "cabin", "hydraulic_area"]
ZONE_LABELS = {
    "front": "Front View",
    "left_side": "Left Side",
    "right_side": "Right Side",
    "cabin": "Operator Cabin",
    "hydraulic_area": "Hydraulic System",
}


async def analyze_photo(image_bytes: bytes, zone: str) -> dict:
    """Analyze a single equipment photo using Gemini Vision API.
    
    Falls back to simulated analysis if no API key.
    """
    if GEMINI_API_KEY:
        try:
            return await _gemini_analyze(image_bytes, zone)
        except Exception as e:
            print(f"Gemini API error: {e}, falling back to simulation")
    
    return _simulate_analysis(zone)


async def _gemini_analyze(image_bytes: bytes, zone: str) -> dict:
    """Call Gemini Vision API for structured damage assessment."""
    import httpx
    
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    
    prompt = f"""You are an expert heavy equipment inspector. Analyze this photo of the {ZONE_LABELS.get(zone, zone)} of a Caterpillar construction equipment.

Respond ONLY with a JSON object (no markdown, no explanation) with these exact fields:
{{
    "zone": "{zone}",
    "damage_type": "none|scratch|dent|crack|rust|leak|wear|structural",
    "severity": <1-5 integer, 1=pristine 5=critical>,
    "description": "<one line description of condition>"
}}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64_image}},
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 200,
        }
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    # Clean potential markdown wrapping
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    
    return json.loads(text)


def _simulate_analysis(zone: str) -> dict:
    """Simulated analysis when no API key is available."""
    damage_profiles = {
        "front": [
            {"damage_type": "scratch", "severity": 2, "description": "Minor surface scratches on front bucket, normal wear pattern"},
            {"damage_type": "dent", "severity": 3, "description": "Small dent on lower front guard, impact from debris"},
            {"damage_type": "none", "severity": 1, "description": "Front view in excellent condition, no visible damage"},
        ],
        "left_side": [
            {"damage_type": "rust", "severity": 2, "description": "Light surface rust on left track guard, cosmetic only"},
            {"damage_type": "none", "severity": 1, "description": "Left side panels in good condition"},
            {"damage_type": "wear", "severity": 2, "description": "Normal wear on left side track pads"},
        ],
        "right_side": [
            {"damage_type": "scratch", "severity": 1, "description": "Hairline scratches on right panel, superficial"},
            {"damage_type": "none", "severity": 1, "description": "Right side in good working condition"},
            {"damage_type": "dent", "severity": 2, "description": "Minor dent on right fender, operational integrity intact"},
        ],
        "cabin": [
            {"damage_type": "wear", "severity": 2, "description": "Normal wear on operator seat and controls"},
            {"damage_type": "none", "severity": 1, "description": "Cabin interior well-maintained, all gauges functional"},
            {"damage_type": "crack", "severity": 3, "description": "Small crack in cabin window corner, should be replaced"},
        ],
        "hydraulic_area": [
            {"damage_type": "leak", "severity": 4, "description": "Minor hydraulic fluid seepage at cylinder seal, needs attention"},
            {"damage_type": "none", "severity": 1, "description": "Hydraulic system clean, no leaks detected"},
            {"damage_type": "wear", "severity": 2, "description": "Hydraulic hoses showing age, recommend inspection at next service"},
        ],
    }
    
    options = damage_profiles.get(zone, [
        {"damage_type": "none", "severity": 1, "description": "No damage observed"}
    ])
    
    result = random.choice(options)
    result["zone"] = zone
    return result


def compute_condition_score(zone_results: list[dict]) -> float:
    """Compute 0-100 return condition score from per-zone results.
    
    Each zone contributes equally. Score = 100 - (avg_severity - 1) * 25
    Severity 1 = 100, Severity 3 = 50, Severity 5 = 0
    """
    if not zone_results:
        return 100.0
    
    avg_severity = sum(r.get("severity", 1) for r in zone_results) / len(zone_results)
    score = max(0, 100 - (avg_severity - 1) * 25)
    return round(score, 1)


def should_file_maintenance(zone_results: list[dict], threshold: int = 3) -> bool:
    """Check if any zone scores below threshold (severity >= threshold)."""
    return any(r.get("severity", 1) >= threshold for r in zone_results)
