import json
import os
import re
from typing import Any, Dict, List

# Load action verbs from data/action_verbs.json
DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "action_verbs.json"
)


def load_action_verbs() -> Dict[str, List[str]]:
    """Loads action verbs categorized by skill area."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "leadership": ["Spearheaded", "Orchestrated", "Led", "Directed"],
        "technical": ["Architected", "Engineered", "Developed", "Automated"],
        "optimization": ["Optimized", "Streamlined", "Accelerated", "Enhanced"],
        "results": ["Delivered", "Generated", "Reduced", "Increased"],
    }


WEAK_START_PATTERNS = [
    (r"^(?:was\s+)?responsible\s+for\b", "responsible for"),
    (r"^(?:duties\s+included|duties\s+were)\b", "duties included"),
    (r"^worked\s+(?:on|with|in)\b", "worked on/with"),
    (r"^helped\s+(?:to|with|in)\b", "helped with/to"),
    (r"^assisted\s+(?:with|in|to)\b", "assisted with/in"),
    (r"^tasked\s+with\b", "tasked with"),
    (r"^handled\b", "handled"),
    (r"^participated\s+in\b", "participated in"),
    (r"^involved\s+in\b", "involved in"),
    (r"^contributed\s+to\b", "contributed to"),
    (r"^supported\b", "supported"),
    (r"^served\s+as\b", "served as"),
]


def extract_experience_bullets(text: str) -> List[str]:
    """Extracts candidate bullet points from the resume text."""
    if not text:
        return []

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Locate the Experience section boundary if present
    exp_start = -1
    exp_end = len(lines)

    section_pattern = re.compile(
        r"^(?:work\s+experience|professional\s+experience|employment\s+history|experience|work\s+history)\b",
        re.IGNORECASE,
    )
    next_section_pattern = re.compile(
        r"^(?:education|skills|technical\s+skills|projects|certifications|awards|summary|objective|publications)\b",
        re.IGNORECASE,
    )

    for idx, line in enumerate(lines):
        clean_line = re.sub(r"^[#*_\s]+|[#*_\s:]+$", "", line).strip()
        if exp_start == -1 and section_pattern.match(clean_line):
            exp_start = idx + 1
        elif exp_start != -1 and next_section_pattern.match(clean_line) and idx > exp_start:
            exp_end = idx
            break

    target_lines = lines[exp_start:exp_end] if exp_start != -1 else lines

    bullets: List[str] = []
    bullet_marker_regex = re.compile(r"^[\u2022\u25e6\u2023\u2043\u25aa\u25ab\-*–—]\s*|\b\d+[\.\)]\s*")

    for line in target_lines:
        # Matches lines starting with bullet symbols or numbered items
        if bullet_marker_regex.match(line):
            clean_bullet = bullet_marker_regex.sub("", line).strip()
            if len(clean_bullet.split()) >= 3:
                bullets.append(clean_bullet)
        # If in experience section and no explicit markers, capture multi-word sentences
        elif exp_start != -1 and len(line.split()) >= 4:
            # Exclude lines that look like company names or date ranges
            if not re.search(r"\b(19|20)\d{2}\b", line) and not line.endswith(":"):
                bullets.append(line)

    return bullets


def analyze_bullets(text: str, max_words_per_bullet: int = 35) -> Dict[str, Any]:
    """Analyzes experience bullet points for:

    1. Weak starts (e.g., 'responsible for', 'worked on')
    2. Missing numbers/measurable results
    3. Overly long bullets (> max_words_per_bullet words)
    Suggests stronger action verbs without hallucinating facts.
    """
    bullets = extract_experience_bullets(text)
    action_verbs_dict = load_action_verbs()

    # Flatten recommended verbs for suggestions
    sample_recommendations = (
        action_verbs_dict.get("leadership", [])[:2]
        + action_verbs_dict.get("technical_and_development", action_verbs_dict.get("technical", []))[:2]
        + action_verbs_dict.get("optimization_and_impact", action_verbs_dict.get("optimization", []))[:2]
        + action_verbs_dict.get("delivery_and_results", action_verbs_dict.get("results", []))[:2]
    )

    results: List[Dict[str, Any]] = []
    flagged_count = 0

    metric_regex = re.compile(
        r"(\b\d+(?:[\.,]\d+)?%?|\$\s*\d+|\b\d+\s*(?:k|m|million|billion|x|users|clients|hours|days|percent)\b)",
        re.IGNORECASE,
    )

    for bullet in bullets:
        issues = []
        suggestions = []
        words = bullet.split()
        word_count = len(words)

        # 1. Check for weak start
        weak_match_label = None
        for pattern, label in WEAK_START_PATTERNS:
            if re.search(pattern, bullet, re.IGNORECASE):
                weak_match_label = label
                break

        if weak_match_label:
            issues.append(f"Weak start: starts with passive phrasing ('{weak_match_label}')")
            suggestions.append(
                f"Replace with a proactive action verb (e.g. {', '.join(sample_recommendations[:4])})."
            )

        # 2. Check for missing quantifiable metrics / results
        if not metric_regex.search(bullet):
            issues.append("No measurable numbers or results detected")
            suggestions.append(
                "Add specific, genuine metrics (e.g., % improvement, revenue, time saved, or team/user count). Never invent facts—only include real results."
            )

        # 3. Check for excessive length
        if word_count > max_words_per_bullet:
            issues.append(f"Very long bullet ({word_count} words; recommended < {max_words_per_bullet})")
            suggestions.append(
                "Split or condense into concise format: [Action Verb] + [Context/Problem] + [Measurable Outcome]."
            )

        is_flagged = len(issues) > 0
        if is_flagged:
            flagged_count += 1

        results.append({
            "bullet": bullet,
            "word_count": word_count,
            "passed": not is_flagged,
            "issues": issues,
            "suggestions": suggestions,
        })

    return {
        "total_bullets": len(bullets),
        "flagged_count": flagged_count,
        "clean_count": len(bullets) - flagged_count,
        "results": results,
        "recommended_verbs": action_verbs_dict,
    }
