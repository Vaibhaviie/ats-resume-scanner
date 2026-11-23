import re
from typing import Any, Dict, List


def check_headings(text: str) -> Dict[str, Any]:
    """Check whether standard resume section headings are present."""
    required_sections = {
        "Summary or Objective": r"\b(summary|objective|profile|about\s+me)\b",
        "Skills": r"\b(skills|competencies|technologies|proficiencies)\b",
        "Experience": r"\b(experience|employment|work\s+history|history)\b",
        "Education": r"\b(education|academic|qualifications|degree)\b",
    }

    missing = []
    for section_name, pattern in required_sections.items():
        if not re.search(pattern, text, re.IGNORECASE):
            missing.append(section_name)

    passed = len(missing) == 0
    if passed:
        tip = "All standard headings (Summary/Objective, Skills, Experience, Education) detected."
    else:
        tip = f"Missing standard section headings: {', '.join(missing)}. Add clear headings so ATS can parse your background."

    return {
        "name": "Standard Section Headings",
        "passed": passed,
        "tip": tip,
    }


def check_contact_info(text: str) -> Dict[str, Any]:
    """Check whether an email address and phone number are present."""
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    # Matches international and standard phone formats (10-15 digits with common separators)
    phone_pattern = r"(?:(?:\+|00)\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}\b"

    has_email = bool(re.search(email_pattern, text))
    has_phone = bool(re.search(phone_pattern, text))

    passed = has_email and has_phone
    if passed:
        tip = "Both email address and phone number were found."
    elif not has_email and not has_phone:
        tip = "Neither email nor phone number was detected. Include clear contact information at the top."
    elif not has_email:
        tip = "Email address is missing. Ensure a professional email is clearly visible."
    else:
        tip = "Phone number is missing or unformatted. Add an easily readable phone number."

    return {
        "name": "Contact Information",
        "passed": passed,
        "tip": tip,
    }


def check_length(text: str, max_words: int = 900) -> Dict[str, Any]:
    """Check that the resume is within recommended word count (~900 words)."""
    words = text.split()
    word_count = len(words)

    passed = word_count <= max_words
    if passed:
        tip = f"Resume length is appropriate ({word_count} words; within the ~{max_words} word limit)."
    else:
        tip = f"Resume is {word_count} words (exceeds recommended ~{max_words} words). Condense descriptions to fit 1-2 pages."

    return {
        "name": "Resume Length",
        "passed": passed,
        "tip": tip,
    }


def check_odd_symbols(text: str) -> Dict[str, Any]:
    """Check for odd characters, replacement glyphs, emoji, or icon font characters."""
    problematic_found = set()

    for ch in text:
        cp = ord(ch)
        # Standard whitespace is fine
        if ch in "\t\n\r":
            continue
        # Unprintable control characters
        if cp < 32 or (127 <= cp <= 159):
            problematic_found.add("Control character")
        # Replacement character from failed font encodings
        elif cp == 0xFFFD:
            problematic_found.add(" (Unicode replacement glyph)")
        # Private Use Area (frequently used by icon fonts like FontAwesome that ATS cannot read)
        elif 0xE000 <= cp <= 0xF8FF:
            problematic_found.add("Private Use icon glyph")
        # Emojis & miscellaneous dingbats/symbols
        elif cp >= 0x1F000 or (0x2600 <= cp <= 0x27BF):
            problematic_found.add(f"Emoji/Symbol '{ch}'")

    passed = len(problematic_found) == 0
    if passed:
        tip = "No unusual symbols, emoji, or font-encoding errors detected."
    else:
        symbols_str = ", ".join(list(problematic_found)[:4])
        tip = f"Found non-standard characters ({symbols_str}). Replace icons, emoji, and special symbols with plain text or standard bullets."

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
