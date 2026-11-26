import re
from typing import Any, Dict, List


def check_headings(text: str) -> Dict[str, Any]:
    """Check whether standard resume section headings are present on heading-like lines."""
    required_sections = {
        "Summary or Objective": re.compile(
            r"^(?:summary|professional\s+summary|executive\s+summary|career\s+summary|"
            r"objective|career\s+objective|profile|about\s+me)\b",
            re.IGNORECASE,
        ),
        "Skills": re.compile(
            r"^(?:skills|technical\s+skills|core\s+skills|key\s+skills|"
            r"competencies|core\s+competencies|technologies|proficiencies)\b",
            re.IGNORECASE,
        ),
        "Experience or Projects": re.compile(
            r"^(?:experience|work\s+experience|professional\s+experience|relevant\s+experience|"
            r"employment|employment\s+history|work\s+history|internships?|projects|academic\s+projects)\b",
            re.IGNORECASE,
        ),
        "Education": re.compile(
            r"^(?:education|academic\s+background|academics|qualifications|educational\s+qualifications)\b",
            re.IGNORECASE,
        ),
    }

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidate_headings: List[str] = []
    for line in lines:
        cleaned = re.sub(r"^[#*_\-\u2022\s]+|[#*_\s]+$", "", line).strip()
        if not cleaned:
            continue
        # Match standalone headings (<= 6 words) or inline "Heading: content"
        if ":" in cleaned:
            prefix = cleaned.split(":", 1)[0].strip()
            if len(prefix.split()) <= 5:
                candidate_headings.append(prefix)
        elif len(cleaned.split()) <= 6:
            candidate_headings.append(cleaned)

    missing = []
    for section_name, pattern in required_sections.items():
        if not any(pattern.match(h) for h in candidate_headings):
            missing.append(section_name)

    passed = len(missing) == 0
    if passed:
        tip = "All standard headings (Summary/Objective, Skills, Experience/Projects, Education) detected."
    else:
        tip = (
            f"Missing standard section heading(s): {', '.join(missing)}. "
            "Use clear, standalone section titles so ATS parsers categorize your resume accurately."
        )

    return {
        "name": "Standard Section Headings",
        "passed": passed,
        "tip": tip,
    }


def check_contact_info(text: str) -> Dict[str, Any]:
    """Check whether a valid email address and phone number are present."""
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    # Candidate phone substrings; validate digit counts to avoid matching year ranges like 2020-2024
    phone_candidate_pattern = r"(?:\+|00)?\d[\d\s().-]{7,18}\d"

    has_email = bool(re.search(email_pattern, text))

    has_phone = False
    for match in re.finditer(phone_candidate_pattern, text):
        raw = match.group(0).strip()
        # Reject date ranges such as 2020-2024 or 1999-2003
        if re.fullmatch(r"(?:19|20)\d{2}\s*[-–/.]\s*(?:19|20)\d{2}", raw):
            continue
        digits = re.sub(r"\D", "", raw)
        if 10 <= len(digits) <= 15:
            has_phone = True
            break

    passed = has_email and has_phone
    if passed:
        tip = "Both email address and phone number were found."
    elif not has_email and not has_phone:
        tip = "Neither email nor phone number was detected. Add clear contact details at the top of your resume."
    elif not has_email:
        tip = "Email address is missing. Include a professional email address near the top."
    else:
        tip = "Phone number is missing or unformatted. Add a standard 10-digit phone number."

    return {
        "name": "Contact Information",
        "passed": passed,
        "tip": tip,
    }


def check_length(text: str, min_words: int = 60, max_words: int = 900) -> Dict[str, Any]:
    """Check that the resume word count is neither too sparse nor overly long."""
    word_count = len(text.split())

    if word_count < min_words:
        passed = False
        tip = (
            f"Resume is very short ({word_count} words; recommended {min_words}–{max_words} words). "
            "Expand on your skills, responsibilities, and measurable outcomes."
        )
    elif word_count > max_words:
        passed = False
        tip = (
            f"Resume is {word_count} words (exceeds recommended ~{max_words} words). "
            "Condense older or redundant details to fit cleanly within 1–2 pages."
        )
    else:
        passed = True
        tip = f"Resume length is appropriate ({word_count} words; within the {min_words}–{max_words} word range)."

    return {
        "name": "Resume Length",
        "passed": passed,
        "tip": tip,
    }


def check_odd_symbols(text: str) -> Dict[str, Any]:
    """Check for control characters, replacement glyphs, emoji, or icon-font symbols."""
    problematic_found = set()

    for ch in text:
        cp = ord(ch)
        if ch in "\t\n\r":
            continue
        if cp < 32 or (127 <= cp <= 159):
            problematic_found.add("Control character")
        elif cp == 0xFFFD:
            problematic_found.add("Unicode replacement glyph")
        elif 0xE000 <= cp <= 0xF8FF:
            problematic_found.add("Icon-font glyph")
        elif cp >= 0x1F000 or (0x2600 <= cp <= 0x27BF):
            problematic_found.add(f"Emoji/Symbol '{ch}'")

    passed = len(problematic_found) == 0
    if passed:
        tip = "No unusual symbols, emoji, or font-encoding errors detected."
    else:
        symbols_str = ", ".join(sorted(problematic_found)[:4])
        tip = (
            f"Found non-standard characters ({symbols_str}). "
            "Replace icons, emoji, and fancy symbols with plain text or standard bullet points."
        )

    return {
        "name": "ATS-Friendly Characters",
        "passed": passed,
        "tip": tip,
    }


def run_ats_checks(text: str) -> List[Dict[str, Any]]:
    """Run all ATS-friendliness checks on the resume text."""
    if not text or not text.strip():
        return [
            {
                "name": "Resume Content",
                "passed": False,
                "tip": "No readable text provided to analyze.",
            }
        ]

    return [
        check_headings(text),
        check_contact_info(text),
        check_length(text),
        check_odd_symbols(text),
    ]
