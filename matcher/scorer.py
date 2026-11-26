import re
from typing import Any, Dict, List
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from matcher.semantic import calculate_semantic_score
from matcher.skills_advisor import (
    extract_skills_with_levels,
    find_missing_skills,
    get_generic_words,
)

MAX_SCORER_CHARS = 80_000
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_]{2,}$")


def _compute_skill_overlap_score(resume_text: str, job_description: str) -> float | None:
    """Compute weighted skill overlap percentage (Required=2x, Preferred=1x) if JD has skills."""
    jd_skills = extract_skills_with_levels(job_description)
    if not jd_skills:
        return None

    resume_skills = set(extract_skills_with_levels(resume_text).keys())
    total_weight = 0.0
    matched_weight = 0.0

    for skill, level in jd_skills.items():
        weight = 2.0 if level == "Required" else 1.0
        total_weight += weight
        if skill in resume_skills:
            matched_weight += weight

    if total_weight <= 0:
        return None
    return round((matched_weight / total_weight) * 100.0, 2)


def calculate_match(
    resume_text: str,
    job_description: str,
    top_n_keywords: int = 8
) -> Dict[str, Any]:
    """Compare resume text and job description using filtered TF-IDF, skills, and semantics.

    Generic job-posting terms (data/generic_words.json) are excluded from both
    TF-IDF keyword matching and missing skills extraction.
    """
    clean_resume = resume_text.strip()[:MAX_SCORER_CHARS] if resume_text else ""
    clean_jd = job_description.strip()[:MAX_SCORER_CHARS] if job_description else ""

    if not clean_resume or not clean_jd:
        return {
            "score": 0.0,
            "final_score": 0.0,
            "keyword_score": 0.0,
            "semantic_score": 0.0,
            "missing_keywords": [],
            "missing_skills": [],
        }

    # 1. Filtered TF-IDF cosine similarity (excludes English + generic job-ad words)
    tfidf_pct = 0.0
    try:
        raw_stop_words = set(ENGLISH_STOP_WORDS) | get_generic_words()
        stop_words = sorted(w for w in raw_stop_words if _TOKEN_RE.match(w))
        vectorizer = TfidfVectorizer(
            stop_words=stop_words,
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        tfidf_matrix = vectorizer.fit_transform([clean_resume, clean_jd])
        sim = float(cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0])
        tfidf_pct = max(0.0, min(100.0, sim * 100.0))
    except ValueError:
        tfidf_pct = 0.0

    # Rescale compressed raw TF-IDF similarity gently while anchoring to genuine skill overlap
    rescaled_tfidf = min(100.0, tfidf_pct * 1.6)
    skill_overlap_pct = _compute_skill_overlap_score(clean_resume, clean_jd)

    if skill_overlap_pct is not None:
        keyword_score = round(0.55 * skill_overlap_pct + 0.45 * rescaled_tfidf, 2)
    else:
        keyword_score = round(rescaled_tfidf, 2)

    # 2. Extract genuine missing skills (Required first, generic words filtered)
    missing_skills_data = find_missing_skills(clean_resume, clean_jd, max_skills=top_n_keywords)
    missing_keywords = [item["skill"] for item in missing_skills_data]

    # 3. Semantic matching with sentence-transformers (with keyword fallback)
    semantic_score = calculate_semantic_score(clean_resume, clean_jd)

    # 4. Combine scores cleanly
    if semantic_score is not None:
        final_score = round(0.55 * keyword_score + 0.45 * semantic_score, 2)
    else:
        final_score = keyword_score

    final_score = max(0.0, min(100.0, final_score))

    return {
        "score": final_score,
        "final_score": final_score,
        "keyword_score": keyword_score,
        "semantic_score": semantic_score,
        "missing_keywords": missing_keywords,
        "missing_skills": missing_skills_data,
    }
