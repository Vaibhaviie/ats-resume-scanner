import json
import os
import re
from typing import Dict, List, Set, Tuple

# Base data directory
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

_SKILLS_CACHE: List[str] = []
_SYNONYMS_CACHE: Dict[str, str] = {}
_GENERIC_WORDS_CACHE: Set[str] = set()
_DATA_LOADED = False


def load_data():
    """Load skills, synonyms, and generic words from the data directory."""
    global _SKILLS_CACHE, _SYNONYMS_CACHE, _GENERIC_WORDS_CACHE, _DATA_LOADED
    if _DATA_LOADED:
        return

    skills_file = os.path.join(DATA_DIR, "skills.json")
    if os.path.exists(skills_file):
        try:
            with open(skills_file, "r", encoding="utf-8") as f:
                _SKILLS_CACHE = json.load(f)
        except Exception:
            _SKILLS_CACHE = []

    synonyms_file = os.path.join(DATA_DIR, "synonyms.json")
    if os.path.exists(synonyms_file):
        try:
            with open(synonyms_file, "r", encoding="utf-8") as f:
                _SYNONYMS_CACHE = json.load(f)
        except Exception:
            _SYNONYMS_CACHE = {}

    generic_file = os.path.join(DATA_DIR, "generic_words.json")
    if os.path.exists(generic_file):
        try:
            with open(generic_file, "r", encoding="utf-8") as f:
                raw_generic = json.load(f)
                _GENERIC_WORDS_CACHE = {w.lower().strip() for w in raw_generic}
        except Exception:
            _GENERIC_WORDS_CACHE = set()

    _DATA_LOADED = True


def determine_best_section(skill: str) -> str:
    """Determines the most appropriate resume section for a given skill."""
    s = skill.lower()

    # Methodologies, architecture, and engineering practices are best shown in Experience
    experience_patterns = [
        "agile", "scrum", "kanban", "microservices", "system design",
        "ci/cd", "test-driven", "unit testing", "integration testing",
        "etl", "data warehousing", "data modeling", "cybersecurity",
        "penetration testing", "project management", "product management",
        "object-oriented"
    ]
    if any(p in s for p in experience_patterns):
        return "Experience"

    # Hands-on projects / portfolios
    project_patterns = [
        "wireframing", "user research", "financial modeling"
    ]
    if any(p in s for p in project_patterns):
        return "Projects"

    # Languages, frameworks, tools, cloud, and databases belong in Skills
    return "Skills"


def extract_skills_with_levels(text: str) -> Dict[str, str]:
    """Scans text and extracts genuine skills defined in skills.json and synonyms.json.

    Returns a dict mapping canonical_skill -> 'Required' or 'Preferred'.
    Filters out any words defined in generic_words.json.
    """
    load_data()
    if not text:
        return {}

    skills_found: Dict[str, str] = {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Build compiled search patterns for each canonical skill and synonym
    all_targets: List[Tuple[str, str, re.Pattern]] = []

    # Synonyms first
    for alias, canonical in _SYNONYMS_CACHE.items():
        if alias.lower() not in _GENERIC_WORDS_CACHE:
            pattern = re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", re.IGNORECASE)
            all_targets.append((alias, canonical, pattern))

    # Canonical skills
    for canonical in _SKILLS_CACHE:
        if canonical.lower() not in _GENERIC_WORDS_CACHE:
            pattern = re.compile(r"(?<!\w)" + re.escape(canonical) + r"(?!\w)", re.IGNORECASE)
            all_targets.append((canonical, canonical, pattern))

    # Track current section context (Default is Required for job postings)
    current_context = "Required"

    preferred_keywords = re.compile(
        r"\b(preferred|nice to have|pluses|bonus|plus|desired|optional|good to have)\b",
        re.IGNORECASE,
    )
    required_keywords = re.compile(
        r"\b(required|must have|minimum|essential|requirements|qualifications|basic qualifications)\b",
        re.IGNORECASE,
    )

    for line in lines:
        if preferred_keywords.search(line):
            current_context = "Preferred"
        elif required_keywords.search(line):
            current_context = "Required"

        line_has_preferred_marker = bool(preferred_keywords.search(line))

        for _, canonical, regex in all_targets:
            if canonical.lower() in _GENERIC_WORDS_CACHE:
                continue

            if regex.search(line):
                level = "Preferred" if line_has_preferred_marker or current_context == "Preferred" else "Required"
                if canonical in skills_found:
                    if skills_found[canonical] != "Required" and level == "Required":
                        skills_found[canonical] = "Required"
                else:
                    skills_found[canonical] = level

    return skills_found


def find_missing_skills(
    resume_text: str,
    job_description: str,
    max_skills: int = 8
) -> List[Dict[str, str]]:
    """Identifies skills present in the job description that are missing from the resume.

    - Only includes genuine skills from data/skills.json and data/synonyms.json.
    - Filters out all words from data/generic_words.json.
    - Orders 'Required' skills first, then 'Preferred'.
    - Returns at most max_skills items with Skill, Level, and Best Section.
    """
    load_data()
    jd_skills = extract_skills_with_levels(job_description)
    resume_skills = set(extract_skills_with_levels(resume_text).keys())

    missing: List[Dict[str, str]] = []
    for skill, level in jd_skills.items():
        if skill not in resume_skills and skill.lower() not in _GENERIC_WORDS_CACHE:
            missing.append({
                "skill": skill,
                "level": level,
                "best_section": determine_best_section(skill),
            })

    # Sort: Required first, then Preferred; alphabetical within same level
    missing.sort(key=lambda x: (0 if x["level"] == "Required" else 1, x["skill"]))

    return missing[:max_skills]


def generate_skill_advice(missing_skills: List[str]) -> List[Dict[str, str]]:
    """Legacy helper for compatibility; returns structured advice for skills."""
    results = []
    for skill in missing_skills:
        results.append({
            "skill": skill,
            "section": determine_best_section(skill),
            "how_to_add": f"Add '{skill}' under your {determine_best_section(skill)} section.",
            "how_to_learn": f"Review official guides and tutorials for {skill} to build proficiency.",
        })
    return results
