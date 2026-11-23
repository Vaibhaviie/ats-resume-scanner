import re
from typing import List, Optional
from sklearn.metrics.pairwise import cosine_similarity

# In-memory singleton cache for the semantic model
_CACHED_MODEL = None
_MODEL_LOAD_ATTEMPTED = False


def get_semantic_model():
    """Loads the sentence-transformers model once and caches it in memory.

    If the model fails to load, returns None so callers can fall back.
    """
    global _CACHED_MODEL, _MODEL_LOAD_ATTEMPTED
    if _MODEL_LOAD_ATTEMPTED:
        return _CACHED_MODEL

    _MODEL_LOAD_ATTEMPTED = True
    try:
        from sentence_transformers import SentenceTransformer

        # all-MiniLM-L6-v2 is lightweight (~80MB), fast, and effective for semantic similarity
        _CACHED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception as e:
        print(f"Notice: Semantic model could not be loaded ({e}). Falling back to keyword score.")
        _CACHED_MODEL = None

    return _CACHED_MODEL


def split_into_sections(text: str) -> List[str]:
    """Splits resume text into meaningful sections or paragraph blocks."""
    if not text:
        return []

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    sections: List[str] = []
    current_chunk: List[str] = []

    header_regex = re.compile(
        r"^(?:summary|objective|skills|experience|work\s+experience|employment|education|projects|certifications)\b",
        re.IGNORECASE,
    )

    for line in lines:
        clean_header = re.sub(r"^[#*_\s]+|[#*_\s:]+$", "", line).strip()
        if header_regex.match(clean_header) and current_chunk:
            sections.append("\n".join(current_chunk))
            current_chunk = [line]
        else:
            current_chunk.append(line)

    if current_chunk:
        sections.append("\n".join(current_chunk))

    # If section headers weren't found, chunk by double linebreaks
    if len(sections) <= 1:
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip().split()) >= 4]
        if paragraphs:
            return paragraphs

    return sections if sections else [text]


def calculate_semantic_score(resume_text: str, job_description: str) -> Optional[float]:
    """Compares resume sections with the job description using embeddings.

    Returns a similarity score between 0.0 and 100.0, or None if the model is unavailable.
    """
    clean_resume = resume_text.strip() if resume_text else ""
    clean_jd = job_description.strip() if job_description else ""

    if not clean_resume or not clean_jd:
        return 0.0

    model = get_semantic_model()
    if model is None:
        return None

    try:
        # Encode the target job description
        jd_embedding = model.encode([clean_jd], convert_to_numpy=True)

        # Encode full resume and sections
        sections = split_into_sections(clean_resume)
        section_embeddings = model.encode(sections, convert_to_numpy=True)
        full_resume_embedding = model.encode([clean_resume], convert_to_numpy=True)

        # Calculate overall similarity and section-level peak similarities
        overall_sim = float(cosine_similarity(full_resume_embedding, jd_embedding)[0][0])
        section_sims = cosine_similarity(section_embeddings, jd_embedding).flatten()
        top_section_sim = float(max(section_sims)) if len(section_sims) > 0 else overall_sim

        # Blend overall alignment (50%) and strongest section alignment (50%)
        blended = 0.5 * overall_sim + 0.5 * top_section_sim
        score = max(0.0, min(100.0, round(blended * 100, 2)))
        return score

    except Exception as e:
        print(f"Error during semantic calculation: {e}")
        return None
