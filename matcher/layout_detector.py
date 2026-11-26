import re
from typing import Dict, List
import docx
import pdfplumber

MAX_INSPECT_PAGES = 10


def detect_layout_warnings(uploaded_file, extracted_text: str = "") -> List[Dict[str, str]]:
    """Inspect an uploaded PDF or DOCX file for common ATS layout pitfalls.

    Checks for tables, multiple columns, embedded images/graphics,
    headers/footers, and jumbled/fragmented reading order.
    """
    if uploaded_file is None:
        return []

    filename = (getattr(uploaded_file, "name", "") or "").lower()
    warnings: List[Dict[str, str]] = []

    if hasattr(uploaded_file, "seek"):
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

    has_tables = False
    has_columns = False
    has_images = False
    has_headers_footers = False
    has_jumbled = False
    inspected_file_structure = False

    # 1. Inspection for DOCX files
    if filename.endswith(".docx"):
        try:
            doc = docx.Document(uploaded_file)
            inspected_file_structure = True

            if len(doc.tables) > 0:
                has_tables = True

            if len(doc.inline_shapes) > 0:
                has_images = True
            elif hasattr(doc, "_element") and doc._element is not None:
                xml_str = doc._element.xml
                if "<w:drawing" in xml_str or "<w:pict" in xml_str:
                    has_images = True

            for s in doc.sections:
                header_text = "".join(p.text.strip() for p in s.header.paragraphs)
                footer_text = "".join(p.text.strip() for p in s.footer.paragraphs)
                if header_text or footer_text:
                    has_headers_footers = True
                    break

            for s in doc.sections:
                if hasattr(s, "_sectPr") and s._sectPr is not None:
                    sect_xml = s._sectPr.xml
                    if 'num="2"' in sect_xml or 'num="3"' in sect_xml:
                        has_columns = True
                        break

            if hasattr(doc, "_element") and doc._element is not None:
                if "<w:txbxContent" in doc._element.xml:
                    has_jumbled = True

        except Exception:
            pass

    # 2. Inspection for PDF files
    elif filename.endswith(".pdf"):
        try:
            with pdfplumber.open(uploaded_file) as pdf:
                inspected_file_structure = True
                for page in pdf.pages[:MAX_INSPECT_PAGES]:
                    if not has_tables:
                        try:
                            tables = page.find_tables()
                            if tables and len(tables) > 0:
                                has_tables = True
                        except Exception:
                            pass

                    if not has_images and getattr(page, "images", None):
                        if len(page.images) > 0:
                            has_images = True

                    words = None
                    try:
                        words = page.extract_words()
                    except Exception:
                        words = []

                    # Standard 0.5-inch margins are 36pt; only flag < 28pt as header/footer zone
                    if not has_headers_footers and words:
                        top_words = [w for w in words if w.get("top", 100) < 28]
                        bottom_words = [
                            w for w in words if w.get("bottom", 0) > (page.height - 28)
                        ]
                        if top_words or bottom_words:
                            has_headers_footers = True

                    # Multi-column check: ignore sparse right-aligned dates
                    if not has_columns and words and len(words) > 40:
                        mid_x = page.width / 2
                        left_words = [w for w in words if w.get("x1", 0) < mid_x - 20]
                        right_words = [w for w in words if w.get("x0", 0) > mid_x + 20]
                        if len(left_words) > 25 and len(right_words) > 25:
                            # Group right-side words by vertical line (~4pt bucket) to distinguish
                            # right-aligned dates (1-3 tokens per line) from real prose columns
                            right_lines: Dict[int, int] = {}
                            for w in right_words:
                                y_key = int(round(w.get("top", 0) / 5.0))
                                right_lines[y_key] = right_lines.get(y_key, 0) + 1
                            avg_right_per_line = sum(right_lines.values()) / max(1, len(right_lines))

                            left_y_span = (
                                min(w["top"] for w in left_words),
                                max(w["bottom"] for w in left_words),
                            )
                            right_y_span = (
                                min(w["top"] for w in right_words),
                                max(w["bottom"] for w in right_words),
                            )
                            overlaps_vertically = max(left_y_span[0], right_y_span[0]) < min(
                                left_y_span[1], right_y_span[1]
                            )
                            if overlaps_vertically and avg_right_per_line >= 3.0 and len(right_lines) >= 6:
                                has_columns = True
        except Exception:
            pass

    # 3. Text-based heuristics (only when structural clues are absent or for text boxes)
    if extracted_text:
        lines = [line.strip() for line in extracted_text.splitlines() if line.strip()]

        if not has_tables:
            # Look for multiple lines with pipe-delimited cells or tabs
            tab_or_pipe_lines = sum(
                1 for line in lines if "\t" in line or bool(re.search(r"\|[^|\n]+\|", line))
            )
            if tab_or_pipe_lines >= 2:
                has_tables = True

        if not has_columns and not inspected_file_structure:
            wide_gap_lines = sum(
                1
                for line in lines[:60]
                if re.search(r"[A-Za-z0-9,.-]{3,}\s{6,}[A-Za-z0-9,.-]{3,}", line)
            )
            if wide_gap_lines >= 4:
                has_columns = True

        # Jumbled text heuristic: high percentage of disconnected 1-2 word fragments
        if not has_jumbled and len(lines) >= 16:
            short_fragments = [
                line
                for line in lines
                if len(line.split()) <= 2
                and not line.startswith(("-", "•", "*", "–", "—"))
                and not line.endswith(":")
            ]
            if len(short_fragments) / len(lines) > 0.58:
                has_jumbled = True

    if hasattr(uploaded_file, "seek"):
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

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
