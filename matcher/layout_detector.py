import re
from typing import Any, Dict, List
import docx
import pdfplumber


def detect_layout_warnings(uploaded_file, extracted_text: str = "") -> List[Dict[str, str]]:
    """Inspects an uploaded PDF or DOCX file (and its extracted text) for ATS pitfalls:

    - Tables
    - Multiple columns
    - Text inside images / graphics
    - Headers and footers
    - Text that appears jumbled or out of order
    """
    if uploaded_file is None:
        return []

    filename = getattr(uploaded_file, "name", "").lower()
    warnings: List[Dict[str, str]] = []

    # Reset seek pointer
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    has_tables = False
    has_columns = False
    has_images = False
    has_headers_footers = False
    has_jumbled = False

    # 1. Inspection for DOCX files
    if filename.endswith(".docx"):
        try:
            doc = docx.Document(uploaded_file)

            # Check tables
            if len(doc.tables) > 0:
                has_tables = True

            # Check images / shapes
            if len(doc.inline_shapes) > 0:
                has_images = True
            elif hasattr(doc, "_element") and doc._element is not None:
                xml_str = doc._element.xml
                if "<w:drawing" in xml_str or "<w:pict" in xml_str:
                    has_images = True

            # Check headers and footers
            for s in doc.sections:
                header_text = "".join(p.text.strip() for p in s.header.paragraphs)
                footer_text = "".join(p.text.strip() for p in s.footer.paragraphs)
                if header_text or footer_text:
                    has_headers_footers = True
                    break

            # Check multiple columns & text boxes
            for s in doc.sections:
                if hasattr(s, "_sectPr") and s._sectPr is not None:
                    sect_xml = s._sectPr.xml
                    if 'num="2"' in sect_xml or 'num="3"' in sect_xml:
                        has_columns = True
                        break

            # Text boxes in DOCX often cause out-of-order text
            if hasattr(doc, "_element") and doc._element is not None:
                if "<w:txbxContent" in doc._element.xml:
                    has_jumbled = True

        except Exception:
            pass

    # 2. Inspection for PDF files
    elif filename.endswith(".pdf"):
        try:
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    # Check tables
                    if not has_tables:
                        try:
                            tables = page.find_tables()
                            if tables and len(tables) > 0:
                                has_tables = True
                        except Exception:
                            pass

                    # Check images
                    if not has_images and getattr(page, "images", None):
                        if len(page.images) > 0:
                            has_images = True

                    # Check headers and footers (top/bottom margin text)
                    if not has_headers_footers:
                        words = page.extract_words()
                        top_words = [w for w in words if w.get("top", 100) < 45]
                        bottom_words = [
                            w for w in words if w.get("bottom", 0) > (page.height - 45)
                        ]
                        if top_words or bottom_words:
                            has_headers_footers = True

                    # Check multi-column layout via word coordinates
                    if not has_columns:
                        words = page.extract_words()
                        if words and len(words) > 30:
                            mid_x = page.width / 2
                            left_words = [w for w in words if w.get("x1", 0) < mid_x - 15]
                            right_words = [w for w in words if w.get("x0", 0) > mid_x + 15]
                            if len(left_words) > 15 and len(right_words) > 15:
                                # Overlapping vertical coordinates between columns
                                left_y_span = (min(w["top"] for w in left_words), max(w["bottom"] for w in left_words))
                                right_y_span = (min(w["top"] for w in right_words), max(w["bottom"] for w in right_words))
                                if max(left_y_span[0], right_y_span[0]) < min(left_y_span[1], right_y_span[1]):
                                    has_columns = True
        except Exception:
            pass

    # 3. Fallback / Text-based heuristics
    if extracted_text:
        lines = [line.strip() for line in extracted_text.splitlines() if line.strip()]

        # Table heuristic in plain text (tab separators or table borders)
        if not has_tables:
            if any("\t" in line or bool(re.search(r"(\|[^\n]+\|)", line)) for line in lines):
                has_tables = True

        # Multi-column heuristic: lines with wide spacing gaps between words
        if not has_columns:
            if any(re.search(r"[A-Za-z0-9,.-]{2,}\s{5,}[A-Za-z0-9,.-]{2,}", line) for line in lines[:60]):
                has_columns = True

        # Jumbled or fragmented text heuristic: unusually high percentage of 1-2 word lines
        if not has_jumbled and len(lines) >= 12:
            short_fragments = [
                line for line in lines
                if len(line.split()) <= 2 and not line.startswith(("-", "•", "*", "–", "—"))
            ]
            if len(short_fragments) / len(lines) > 0.45:
                has_jumbled = True

    # Reset seek pointer before returning
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    # Compile structured warnings with clear fixes
    if has_tables:
        warnings.append({
            "issue": "Tables Detected",
            "description": "Tables can cause ATS parsers to read across columns horizontally, mixing up dates, job titles, and bullet points.",
            "fix": "Remove table grids and format content using simple, linear text with standard bullet points.",
        })

    if has_columns:
        warnings.append({
            "issue": "Multiple Columns Detected",
            "description": "Many ATS systems read text from left-to-right across the whole page, scrambling text between adjacent columns.",
            "fix": "Switch to a clean single-column layout with a natural top-to-bottom reading order.",
        })

    if has_images:
        warnings.append({
            "issue": "Text Inside Images / Graphics",
            "description": "ATS systems cannot read text, contact icons, or skill ratings embedded within image elements.",
            "fix": "Ensure all text, contact details, and skills are typed directly into the document rather than placed in pictures or icons.",
        })

    if has_headers_footers:
        warnings.append({
            "issue": "Headers and Footers Detected",
            "description": "Some ATS software skips header and footer zones entirely, which may cause contact information or your name to be lost.",
            "fix": "Place all contact info and key details inside the document body instead of Word or PDF header/footer areas.",
        })

    if has_jumbled:
        warnings.append({
            "issue": "Jumbled or Out-of-Order Text",
            "description": "Text appears broken into erratic fragments or floating text boxes, which can disrupt reading order.",
            "fix": "Avoid floating text boxes and complex visual templates. Use standard body paragraphs and bulleted lists.",
        })

    return warnings
