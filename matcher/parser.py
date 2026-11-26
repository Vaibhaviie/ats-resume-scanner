from typing import Any, Dict, List, Set
import zipfile
import docx
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
import pdfplumber

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit for Streamlit Cloud free tier
MAX_PDF_PAGES = 25
MAX_TEXT_CHARS = 100_000


def _extract_docx_table_text(table: Table) -> List[str]:
    """Extract readable text from a DOCX table while deduplicating merged cells."""
    lines: List[str] = []
    seen_cells: Set[int] = set()

    for row in table.rows:
        row_parts: List[str] = []
        for cell in row.cells:
            tc_id = id(cell._tc)
            if tc_id in seen_cells:
                continue
            seen_cells.add(tc_id)

            cell_text = " ".join(p.text.strip() for p in cell.paragraphs if p.text.strip())
            if cell_text:
                row_parts.append(cell_text)

            # Handle nested tables if any
            for nested in cell.tables:
                lines.extend(_extract_docx_table_text(nested))

        if row_parts:
            lines.append(" | ".join(row_parts))

    return lines


def _extract_docx_text(doc: DocxDocument) -> str:
    """Extract paragraphs and tables from a DOCX document in reading order."""
    chunks: List[str] = []

    if hasattr(doc, "element") and doc.element is not None and doc.element.body is not None:
        for child in doc.element.body.iterchildren():
            if isinstance(child, CT_P):
                para = Paragraph(child, doc)
                txt = para.text.strip()
                if txt:
                    chunks.append(txt)
            elif isinstance(child, CT_Tbl):
                table = Table(child, doc)
                chunks.extend(_extract_docx_table_text(table))
    else:
        for p in doc.paragraphs:
            if p.text.strip():
                chunks.append(p.text.strip())
        for t in doc.tables:
            chunks.extend(_extract_docx_table_text(t))

    # Fallback: if body was empty, check text boxes or headers/footers
    if not chunks:
        try:
            for section in doc.sections:
                for p in section.header.paragraphs:
                    if p.text.strip():
                        chunks.append(p.text.strip())
                for p in section.footer.paragraphs:
                    if p.text.strip():
                        chunks.append(p.text.strip())
        except Exception:
            pass

    return "\n".join(chunks).strip()


def parse_resume(uploaded_file) -> Dict[str, Any]:
    """Safely parse an uploaded PDF or DOCX file into plain text.

    Returns a dictionary with keys:
      - text (str): Extracted text (empty if parsing failed)
      - error (str | None): Friendly user-facing error message if unsuccessful
      - warning (str | None): Friendly non-fatal notice (e.g., page/length truncation)
      - pages (int): Number of pages inspected (for PDFs)
      - truncated (bool): Whether content was capped for memory safety
    """
    result: Dict[str, Any] = {
        "text": "",
        "error": None,
        "warning": None,
        "pages": 0,
        "truncated": False,
    }

    if uploaded_file is None:
        result["error"] = "Please upload a PDF or DOCX file to begin."
        return result

    filename = getattr(uploaded_file, "name", "") or ""
    lower_name = filename.lower().strip()

    if not (lower_name.endswith(".pdf") or lower_name.endswith(".docx")):
        result["error"] = "Unsupported file format. Please upload a `.pdf` or `.docx` resume file."
        return result

    # Check file size safely
    file_size = getattr(uploaded_file, "size", None)
    if file_size is None and hasattr(uploaded_file, "getbuffer"):
        try:
            file_size = len(uploaded_file.getbuffer())
        except Exception:
            file_size = None

    if file_size == 0:
        result["error"] = "The uploaded file is empty (0 bytes). Please upload a valid PDF or DOCX resume."
        return result

    if file_size is not None and file_size > MAX_FILE_SIZE_BYTES:
        mb = round(file_size / (1024 * 1024), 1)
        result["error"] = (
            f"The uploaded file is too large ({mb} MB). Please upload a file under 10 MB."
        )
        return result

    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    try:
        if lower_name.endswith(".pdf"):
            text_chunks: List[str] = []
            with pdfplumber.open(uploaded_file) as pdf:
                total_pages = len(pdf.pages)
                result["pages"] = total_pages
                if total_pages == 0:
                    result["error"] = "This PDF has no pages. Please upload a valid resume."
                    return result

                pages_to_read = pdf.pages[:MAX_PDF_PAGES]
                if total_pages > MAX_PDF_PAGES:
                    result["truncated"] = True
                    result["warning"] = (
                        f"Your PDF has {total_pages} pages; only the first {MAX_PDF_PAGES} pages were analyzed."
                    )

                for page in pages_to_read:
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text_chunks.append(page_text.strip())

            extracted = "\n\n".join(text_chunks).strip()
            if not extracted:
                result["error"] = (
                    "No readable text was found in this PDF. It appears to be a scanned or image-only PDF. "
                    "Please export your resume as a text-based PDF or DOCX file so an ATS can read it."
                )
                return result

        else:  # .docx
            doc = docx.Document(uploaded_file)
            extracted = _extract_docx_text(doc)
            if not extracted:
                result["error"] = (
                    "No readable text was found in this DOCX file. Please check that the document contains text."
                )
                return result

        if len(extracted) > MAX_TEXT_CHARS:
            extracted = extracted[:MAX_TEXT_CHARS]
            result["truncated"] = True
            result["warning"] = (
                "Your document is unusually long; only the first ~100,000 characters were analyzed."
            )

        result["text"] = extracted
        return result

    except zipfile.BadZipFile:
        result["error"] = (
            "We could not open this DOCX file. It may be corrupted or saved in an older `.doc` format. "
            "Try re-saving it as a `.docx` or `.pdf`."
        )
        return result
    except Exception as exc:
        err_name = type(exc).__name__.lower()
        if "password" in err_name or "encrypt" in err_name or "decrypt" in str(exc).lower():
            result["error"] = (
                "This PDF appears to be password-protected. Please upload an unlocked copy."
            )
        else:
            result["error"] = (
                "We couldn't read this file. It may be corrupted, password-protected, or in an unsupported format. "
                "Please try re-exporting it as a standard PDF or DOCX."
            )
        return result
    finally:
        if hasattr(uploaded_file, "seek"):
            try:
                uploaded_file.seek(0)
            except Exception:
                pass


def extract_text(uploaded_file) -> str:
    """Backward-compatible wrapper returning extracted text or a friendly error message."""
    parsed = parse_resume(uploaded_file)
    if parsed["error"]:
        return parsed["error"]
    return parsed["text"]
