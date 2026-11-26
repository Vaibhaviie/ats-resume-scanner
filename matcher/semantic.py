import hashlib
import re
from typing import Dict, List, Optional, Tuple
from sklearn.metrics.pairwise import cosine_similarity

MAX_SEMANTIC_CHARS = 30_000
MAX_SECTIONS = 15

# Small bounded cache for resume embeddings so comparing 5 jobs encodes the resume once
_RESUME_EMBED_CACHE: Dict[str, Tuple[object, object]] = {}
_CACHED_MODEL = None
_MODEL_LOAD_ATTEMPTED = False


def _load_sentence_transformer_uncached():
    """Load SentenceTransformer trying local cache first to avoid offline hub stalls."""
    try:
        import torch
        torch.set_num_threads(1)
    except Exception:
        pass

    from sentence_transformers import SentenceTransformer

    try:
        return SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
    except Exception:
        return SentenceTransformer("all-MiniLM-L6-v2")


try:
    import streamlit as st

    @st.cache_resource(show_spinner=False)
    def _st_cached_semantic_model():
        try:
            return _load_sentence_transformer_uncached()
        except Exception:
            return None

    _HAS_STREAMLIT = True
except Exception:
    _HAS_STREAMLIT = False


def get_semantic_model():
    """Load and cache the lightweight all-MiniLM-L6-v2 embedding model."""
    global _CACHED_MODEL, _MODEL_LOAD_ATTEMPTED

    if _HAS_STREAMLIT:
        try:
            return _st_cached_semantic_model()
        except Exception:
            pass

    if _MODEL_LOAD_ATTEMPTED:
        return _CACHED_MODEL

    _MODEL_LOAD_ATTEMPTED = True
    try:
        _CACHED_MODEL = _load_sentence_transformer_uncached()
    except Exception:
        _CACHED_MODEL = None
    return _CACHED_MODEL


def split_into_sections(text: str) -> List[str]:
    """Split resume text into meaningful sections or paragraph blocks."""
    if not text:
        return []

    trimmed = text[:MAX_SEMANTIC_CHARS]
    lines = [line.strip() for line in trimmed.splitlines() if line.strip()]
    sections: List[str] = []
    current_chunk: List[str] = []

    header_regex = re.compile(
        r"^(?:summary|objective|skills|experience|work\s+experience|employment|"
        r"education|projects|certifications)\b",
        re.IGNORECASE,
    )

    for line in lines:
        clean_header = re.sub(r"^[#*_\-\u2022\s]+|[#*_\s:]+$", "", line).strip()
        if header_regex.match(clean_header) and len(clean_header.split()) <= 5 and current_chunk:
            sections.append("\n".join(current_chunk))
            current_chunk = [line]
        else:
            current_chunk.append(line)

    if current_chunk:
        sections.append("\n".join(current_chunk))

    if len(sections) <= 1:
        paragraphs = [p.strip() for p in trimmed.split("\n\n") if len(p.strip().split()) >= 4]
        if paragraphs:
            return paragraphs[:MAX_SECTIONS]

    return sections[:MAX_SECTIONS] if sections else [trimmed]


def _get_resume_embeddings(model, clean_resume: str):
    """Encode resume sections and full text once per unique resume."""
    digest = hashlib.sha256(clean_resume.encode("utf-8", errors="ignore")).hexdigest()
    if digest in _RESUME_EMBED_CACHE:
        return _RESUME_EMBED_CACHE[digest]

    sections = split_into_sections(clean_resume)
    section_embeddings = model.encode(sections, convert_to_numpy=True)
    full_resume_embedding = model.encode([clean_resume[:MAX_SEMANTIC_CHARS]], convert_to_numpy=True)

    if len(_RESUME_EMBED_CACHE) >= 3:
        _RESUME_EMBED_CACHE.clear()
    _RESUME_EMBED_CACHE[digest] = (section_embeddings, full_resume_embedding)
    return section_embeddings, full_resume_embedding


def calculate_semantic_score(resume_text: str, job_description: str) -> Optional[float]:
    """Compare resume sections with the job description using embeddings.

    Returns a similarity score between 0.0 and 100.0, or None if unavailable.
    """
    clean_resume = resume_text.strip() if resume_text else ""
    clean_jd = job_description.strip() if job_description else ""

    if not clean_resume or not clean_jd:
        return 0.0

    model = get_semantic_model()
    if model is None:
        return None

    try:
        jd_embedding = model.encode([clean_jd[:MAX_SEMANTIC_CHARS]], convert_to_numpy=True)
        section_embeddings, full_resume_embedding = _get_resume_embeddings(model, clean_resume)

        overall_sim = float(cosine_similarity(full_resume_embedding, jd_embedding)[0][0])
        section_sims = cosine_similarity(section_embeddings, jd_embedding).flatten()
        top_section_sim = float(max(section_sims)) if len(section_sims) > 0 else overall_sim

        blended = 0.5 * overall_sim + 0.5 * top_section_sim
        score = max(0.0, min(100.0, round(blended * 100, 2)))
        return score
    except Exception:
        return None
