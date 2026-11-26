import json
import os
import re
from typing import Dict, List, Set, Tuple

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

_SKILLS_CACHE: List[str] = []
_SYNONYMS_CACHE: Dict[str, str] = {}
_GENERIC_WORDS_CACHE: Set[str] = set()
_COMPILED_TARGETS: List[Tuple[str, str, re.Pattern, str]] = []
_DATA_LOADED = False

# Ambiguous English words that require case-sensitive / contextual matching
_CASE_SENSITIVE_SKILLS = {
    "go", "r", "excel", "swift", "express", "vue", "rust", "dart", "oracle", "bootstrap"
}


def _build_skill_pattern(term: str) -> Tuple[re.Pattern, str]:
    """Builds a compiled regex for a skill/synonym, guarding ambiguous short words."""
    lower = term.lower().strip()
    escaped = re.escape(term)

    if lower == "go":
        # Match capitalized 'Go' not used as common English verb/phrase like 'Go-to' or 'Go above'
        pattern = re.compile(
            r"(?<!\w)Go(?!\w)(?!\s*-\s*to\b)(?!\s+(?:above|beyond|to|for|with|into|through|out|ahead|live|back|on)\b)"
        )
        return pattern, "go_guard"

    if lower == "r":
        # Match uppercase standalone 'R' (not R&D / H&R / etc.)
        pattern = re.compile(r"(?<![\w&])R(?![\w&])")
        return pattern, "r_guard"

    if lower == "excel":
        # Match capitalized 'Excel' when not used as verb 'Excel at/in ...'
        pattern = re.compile(r"(?<!\w)Excel(?!\w)(?!\s+(?:at|in)\b)")
        return pattern, "case_guard"

    if lower == "swift":
        pattern = re.compile(
            r"(?<!\w)Swift(?!\w)(?!\s+(?:action|response|onboarding|execution|decision|resolution)\b)"
        )
        return pattern, "case_guard"

    if lower == "express":
        pattern = re.compile(
            r"(?<!American\s)(?<!\w)Express(?!\w)(?!\s+(?:interest|yourself|lane|delivery|shipping)\b)"
        )
        return pattern, "case_guard"

    if lower in _CASE_SENSITIVE_SKILLS:
        pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)")
        return pattern, "case_guard"

    pattern = re.compile(r"(?<!\w)" + escaped + r"(?!\w)", re.IGNORECASE)
    return pattern, "standard"


def load_data() -> None:
    """Load skills, synonyms, and generic words from the data directory once."""
    global _SKILLS_CACHE, _SYNONYMS_CACHE, _GENERIC_WORDS_CACHE, _COMPILED_TARGETS, _DATA_LOADED
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
                _GENERIC_WORDS_CACHE = {str(w).lower().strip() for w in raw_generic if str(w).strip()}
        except Exception:
            _GENERIC_WORDS_CACHE = set()

    compiled: List[Tuple[str, str, re.Pattern, str]] = []
    seen_terms: Set[Tuple[str, str]] = set()

    for alias, canonical in _SYNONYMS_CACHE.items():
        if alias.lower() in _GENERIC_WORDS_CACHE or canonical.lower() in _GENERIC_WORDS_CACHE:
            continue
        key = (alias.lower(), canonical)
        if key not in seen_terms:
            seen_terms.add(key)
            pat, guard = _build_skill_pattern(alias)
            compiled.append((alias, canonical, pat, guard))

    for canonical in _SKILLS_CACHE:
        if canonical.lower() in _GENERIC_WORDS_CACHE:
            continue
        key = (canonical.lower(), canonical)
        if key not in seen_terms:
            seen_terms.add(key)
            pat, guard = _build_skill_pattern(canonical)
            compiled.append((canonical, canonical, pat, guard))

    _COMPILED_TARGETS = compiled
    _DATA_LOADED = True


def get_generic_words() -> Set[str]:
    """Return the cached set of generic words to exclude from skills and keywords."""
    load_data()
    return set(_GENERIC_WORDS_CACHE)


def determine_best_section(skill: str) -> str:
    """Determine the most appropriate resume section for a given skill."""
    s = skill.lower()

    experience_patterns = [
        "agile", "scrum", "kanban", "microservices", "system design",
        "ci/cd", "test-driven", "unit testing", "integration testing",
        "etl", "data warehousing", "data modeling", "cybersecurity",
        "penetration testing", "project management", "product management",
        "object-oriented", "curriculum development", "lesson planning",
        "classroom management", "differentiated instruction", "student assessment",
        "special education", "b2b sales", "b2c sales", "cold calling",
        "lead generation", "account management", "pipeline management",
        "negotiation", "upselling", "cross-selling", "quota attainment",
        "sales forecasting", "prospecting", "saas sales", "territory management",
        "client retention", "account-based marketing", "financial analysis",
        "budgeting", "forecasting", "auditing", "risk management",
        "portfolio management", "reconciliation", "variance analysis", "compliance"
    ]
    if any(p in s for p in experience_patterns):
        return "Experience"

    project_patterns = [
        "wireframing", "user research", "financial modeling", "instructional design",
        "data visualization", "valuation"
    ]
    if any(p in s for p in project_patterns):
        return "Projects"

    return "Skills"


def _is_go_false_positive(line: str, match_start: int) -> bool:
    """Extra guard for 'Go' when capitalized at start of bullet or after 'to'."""
    prefix = line[:match_start].lower().rstrip()
    if prefix.endswith(("to", "will", "can", "must", "let's", "ready to", "able to")):
        return True
    return False


def _extract_skills_detailed(text: str) -> Tuple[Dict[str, str], Dict[str, int]]:
    """Extract skills with Required/Preferred level and line-occurrence counts."""
    load_data()
    if not text or not text.strip():
        return {}, {}

    skills_found: Dict[str, str] = {}
    skill_counts: Dict[str, int] = {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    current_context = "Required"

    # Section-level Preferred headers (avoid matching 'annual bonus' in Benefits)
    preferred_heading_re = re.compile(
        r"^(?:preferred(?:\s+qualifications|\s+skills|\s+experience)?|nice\s+to\s+have|"
        r"bonus(?:\s+skills|\s+points|\s+qualifications)?|desired(?:\s+skills)?|"
        r"optional(?:\s+skills)?|pluses|good\s+to\s+have)\s*:?$",
        re.IGNORECASE,
    )
    preferred_inline_re = re.compile(
        r"\b(preferred|nice to have|is a plus|as a plus|bonus points|a bonus|desired|optional|good to have)\b",
        re.IGNORECASE,
    )
    required_heading_re = re.compile(
        r"^(?:required(?:\s+qualifications|\s+skills)?|requirements|qualifications|"
        r"basic\s+qualifications|minimum\s+qualifications|must\s+have|essential\s+skills|"
        r"what\s+you(?:'ll|\s+will)\s+bring|who\s+you\s+are)\s*:?$",
        re.IGNORECASE,
    )
    benefits_heading_re = re.compile(
        r"^(?:benefits|compensation|perks|what\s+we\s+offer)\s*:?$",
        re.IGNORECASE,
    )

    for raw_line in lines:
        clean_header = re.sub(r"^[#*_\-\u2022\s]+|[#*_\s]+$", "", raw_line).strip()

        if preferred_heading_re.match(clean_header):
            current_context = "Preferred"
            continue
        if required_heading_re.match(clean_header):
            current_context = "Required"
            continue
        if benefits_heading_re.match(clean_header):
            # Don't accidentally extract 'bonus' context or benefits prose as Preferred requirements
            current_context = "Preferred"
            continue

        # Split line into clauses on ';' so "Python required; Docker is a plus" works accurately
        clauses = [c.strip() for c in raw_line.split(";") if c.strip()] or [raw_line]

        for clause in clauses:
            clause_is_preferred = bool(preferred_inline_re.search(clause))
            clause_has_required = bool(
                re.search(r"\b(required|must have|minimum|essential)\b", clause, re.IGNORECASE)
            )
            if clause_has_required and not clause_is_preferred:
                clause_level = "Required"
            elif clause_is_preferred:
                clause_level = "Preferred"
            else:
                clause_level = current_context

            clause_matches: List[Tuple[str, int, int]] = []
            for _, canonical, regex, guard in _COMPILED_TARGETS:
                if canonical.lower() in _GENERIC_WORDS_CACHE:
                    continue

                match = regex.search(clause)
                if match:
                    if guard == "go_guard" and _is_go_false_positive(clause, match.start()):
                        continue
                    clause_matches.append((canonical, match.start(), match.end()))

            # Suppress shorter skills subsumed inside a longer matched skill span
            kept_matches: List[str] = []
            for canonical, start, end in clause_matches:
                is_subsumed = any(
                    other_canon != canonical
                    and other_start <= start
                    and end <= other_end
                    and (other_end - other_start) > (end - start)
                    for other_canon, other_start, other_end in clause_matches
                )
                if not is_subsumed:
                    kept_matches.append(canonical)

            for canonical in kept_matches:
                skill_counts[canonical] = skill_counts.get(canonical, 0) + 1
                if canonical in skills_found:
                    if skills_found[canonical] != "Required" and clause_level == "Required":
                        skills_found[canonical] = "Required"
                else:
                    skills_found[canonical] = clause_level

    return skills_found, skill_counts


def extract_skills_with_levels(text: str) -> Dict[str, str]:
    """Scan text and extract genuine skills mapped to 'Required' or 'Preferred'."""
    skills_found, _ = _extract_skills_detailed(text)
    return skills_found


def extract_all_skills(text: str) -> List[str]:
    """Return a list of unique genuine skills detected in the text."""
    return list(extract_skills_with_levels(text).keys())


def find_missing_skills(
    resume_text: str,
    job_description: str,
    max_skills: int = 8
) -> List[Dict[str, str]]:
    """Identify skills in the JD missing from the resume.

    - Only includes genuine skills from data/skills.json and data/synonyms.json.
    - Filters out all words from data/generic_words.json.
    - Orders 'Required' skills first, then by frequency in JD, then alphabetically.
    - Returns at most max_skills items.
    """
    load_data()
    jd_skills, jd_counts = _extract_skills_detailed(job_description)
    resume_skills = set(extract_skills_with_levels(resume_text).keys())

    missing: List[Dict[str, str]] = []
    for skill, level in jd_skills.items():
        if skill not in resume_skills and skill.lower() not in _GENERIC_WORDS_CACHE:
            missing.append({
                "skill": skill,
                "level": level,
                "best_section": determine_best_section(skill),
                "_count": jd_counts.get(skill, 1),
            })

    missing.sort(key=lambda x: (0 if x["level"] == "Required" else 1, -x["_count"], x["skill"].lower()))

    return [
        {
            "skill": item["skill"],
            "level": item["level"],
            "best_section": item["best_section"],
        }
        for item in missing[:max_skills]
    ]


def generate_skill_advice(missing_skills: List[str]) -> List[Dict[str, str]]:
    """Return structured advice for missing skills."""
    results = []
    for skill in missing_skills:
        sec = determine_best_section(skill)
        results.append({
            "skill": skill,
            "section": sec,
            "how_to_add": f"Add '{skill}' under your {sec} section.",
            "how_to_learn": f"Review official guides and tutorials for {skill} to build proficiency.",
        })
    return results
