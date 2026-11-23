import docx
import pdfplumber


def extract_text(uploaded_file) -> str:
    """Extract plain text from an uploaded PDF or DOCX file.

    Returns a descriptive message if no readable text is found.
    """
    if uploaded_file is None:
        return ""

    filename = getattr(uploaded_file, "name", "").lower()

    # Reset file pointer to beginning if seek is supported
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    try:
        # Handle PDF documents
        if filename.endswith(".pdf"):
            text_chunks = []
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_chunks.append(page_text.strip())

            extracted = "\n\n".join(text_chunks).strip()
            if not extracted:
                return "No readable text found in the PDF. It may be an image-only scan or empty."
            return extracted

        # Handle DOCX documents
        elif filename.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            extracted = "\n".join(paragraphs).strip()
            if not extracted:
                return "No readable text found in the DOCX file."
            return extracted

        else:
            return "Unsupported file format. Please upload a PDF or DOCX file."

    except Exception as e:
        return f"Error extracting text from file: {e}"
