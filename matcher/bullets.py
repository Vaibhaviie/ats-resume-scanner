import json
import os
import re
from typing import Any, Dict, List

DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "action_verbs.json"
)

MAX_BULLETS_TO_ANALYZE = 50


def load_action_verbs() -> Dict[str, List[str]]:
    """Load action verbs categorized by skill area."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "leadership": ["Spearheaded", "Orchestrated", "Led", "Directed"],
        "technical_and_development": ["Architected", "Engineered", "Developed", "Automated"],
        "optimization_and_impact": ["Optimized", "Streamlined", "Accelerated", "Enhanced"],
        "delivery_and_results": ["Delivered", "Generated", "Reduced", "Increased"],
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


def _looks_like_date_or_job_header(line: str) -> bool:
    """Return True if a line appears to be a job title/company/date header rather than a bullet."""
    words = line.split()
    if line.endswith(":"):
        return True
    if "|" in line and len(words) <= 12:
        return True
    # Date ranges like '2020 - 2024' or 'Jan 2022 - Present' on short lines
    if len(words) <= 9 and re.search(
        r"\b(?:19|20)\d{2}\s*[-–—]\s*(?:(?:19|20)\d{2}|present|current)\b",
        line,
        re.IGNORECASE,
    ):
        return True
    return False


def extract_experience_bullets(text: str) -> List[str]:
    """Extract candidate bullet points from Experience (or Projects for freshers)."""
    if not text or not text.strip():
        return []

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    exp_pattern = re.compile(
        r"^(?:work\s+experience|professional\s+experience|relevant\s+experience|"
        r"employment\s+history|experience|work\s+history|internships?)\b",
        re.IGNORECASE,
    )
    proj_pattern = re.compile(
        r"^(?:projects|academic\s+projects|key\s+projects)\b",
        re.IGNORECASE,
    )
    other_section_pattern = re.compile(
        r"^(?:education|skills|technical\s+skills|core\s+skills|competencies|"
        r"certifications|awards|summary|objective|profile|publications|references)\b",
        re.IGNORECASE,
    )

    def _slice_section(start_regex: re.Pattern, stop_regex: re.Pattern) -> List[str]:
        s_idx = -1
        e_idx = len(lines)
        for idx, line in enumerate(lines):
            clean_line = re.sub(r"^[#*_\-\u2022\s]+|[#*_\s:]+$", "", line).strip()
            if s_idx == -1 and start_regex.match(clean_line) and len(clean_line.split()) <= 5:
                s_idx = idx + 1
            elif s_idx != -1 and idx > s_idx and stop_regex.match(clean_line) and len(clean_line.split()) <= 5:
                e_idx = idx
                break
        return lines[s_idx:e_idx] if s_idx != -1 else []

    stop_after_exp = re.compile(
        r"^(?:education|skills|technical\s+skills|core\s+skills|competencies|"
        r"projects|academic\s+projects|certifications|awards|summary|objective|publications|references)\b",
        re.IGNORECASE,
    )
    target_lines = _slice_section(exp_pattern, stop_after_exp)
    in_named_section = bool(target_lines)

    # For freshers without an Experience section, inspect Projects
    if not target_lines:
        stop_after_proj = re.compile(
            r"^(?:education|skills|technical\s+skills|core\s+skills|competencies|"
            r"certifications|awards|summary|objective|publications|references)\b",
            re.IGNORECASE,
        )
        target_lines = _slice_section(proj_pattern, stop_after_proj)
        in_named_section = bool(target_lines)

    # Final fallback: scan only explicit bullet-marked action lines (skipping Skills/Education)
    if not target_lines:
        filtered: List[str] = []
        skip_section = False
        for line in lines:
            clean_line = re.sub(r"^[#*_\-\u2022\s]+|[#*_\s:]+$", "", line).strip()
            if other_section_pattern.match(clean_line) and len(clean_line.split()) <= 5:
                skip_section = True
                continue
            if not skip_section:
                filtered.append(line)
        target_lines = filtered

    bullets: List[str] = []
    # Properly anchored leading bullet marker so inline numbers like '15.5%' are preserved
    bullet_marker_regex = re.compile(
        r"^(?:[\u2022\u25e6\u2023\u2043\u25aa\u25ab\-*–—]\s*|\d{1,2}[\.\)]\s+)"
    )

    for line in target_lines:
        if bullet_marker_regex.match(line):
            clean_bullet = bullet_marker_regex.sub("", line, count=1).strip()
            if len(clean_bullet.split()) >= 4 and not _looks_like_date_or_job_header(clean_bullet):
                bullets.append(clean_bullet)
        elif in_named_section and len(line.split()) >= 6:
            if not _looks_like_date_or_job_header(line):
                bullets.append(line)

        if len(bullets) >= MAX_BULLETS_TO_ANALYZE:
            break

    return bullets


def analyze_bullets(text: str, max_words_per_bullet: int = 35) -> Dict[str, Any]:
    """Analyze experience bullet points for weak starts, missing metrics, and length."""
    bullets = extract_experience_bullets(text)
    action_verbs_dict = load_action_verbs()

    sample_recommendations = (
        action_verbs_dict.get("leadership", [])[:2]
        + action_verbs_dict.get("technical_and_development", action_verbs_dict.get("technical", []))[:2]
        + action_verbs_dict.get("optimization_and_impact", action_verbs_dict.get("optimization", []))[:2]
        + action_verbs_dict.get("delivery_and_results", action_verbs_dict.get("results", []))[:2]
    )

    results: List[Dict[str, Any]] = []
    flagged_count = 0

    metric_regex = re.compile(
        r"(\b\d+(?:[\.,]\d+)?%|\$\s*\d+|\b\d+(?:[\.,]\d+)?\s*"
        r"(?:k|m|million|billion|x|\+|users|students|clients|customers|accounts|"
        r"hours|days|weeks|months|percent|deals|tickets)\b|\b\d{2,}\b)",
        re.IGNORECASE,
    )

    for bullet in bullets:
        issues: List[str] = []
        suggestions: List[str] = []
        word_count = len(bullet.split())

        weak_match_label = None
        for pattern, label in WEAK_START_PATTERNS:
            if re.search(pattern, bullet, re.IGNORECASE):
                weak_match_label = label
                break

        if weak_match_label:
            issues.append(f"Passive start ('{weak_match_label}')")
            suggestions.append(
                f"Start with a stronger action verb (e.g., {', '.join(sample_recommendations[:4])})."
            )

        if not metric_regex.search(bullet):
            issues.append("No measurable numbers or scope detected")
            suggestions.append(
                "Where accurate, quantify the scale or outcome (e.g., %, dollar impact, time saved, or people served)."
            )

        if word_count > max_words_per_bullet:
            issues.append(f"Long bullet ({word_count} words; target <= {max_words_per_bullet})")
            suggestions.append(
                "Condense into one concise line: [Action Verb] + [What You Did] + [Measurable Result]."
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
