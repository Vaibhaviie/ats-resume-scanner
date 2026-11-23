from typing import Any, Dict, List
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from matcher.semantic import calculate_semantic_score


def calculate_match(
    resume_text: str,
    job_description: str,
    top_n_keywords: int = 15
) -> Dict[str, Any]:
    """Compare resume text and job description using both TF-IDF keyword matching

    and semantic embeddings. Combines them into a single final score.
    Falls back to keyword scoring if the semantic model cannot load.
    """
    clean_resume = resume_text.strip() if resume_text else ""
    clean_jd = job_description.strip() if job_description else ""

    if not clean_resume or not clean_jd:
        return {
            "score": 0.0,
            "final_score": 0.0,
            "keyword_score": 0.0,
            "semantic_score": 0.0,
            "missing_keywords": [],
        }

    # 1. Keyword matching via TF-IDF & Cosine Similarity
    keyword_score = 0.0
    missing_keywords: List[str] = []

    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform([clean_resume, clean_jd])

        sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        keyword_score = round(float(sim) * 100, 2)

        # Identify missing keywords from JD
        feature_names = vectorizer.get_feature_names_out()
        resume_weights = tfidf_matrix[0].toarray().flatten()
        jd_weights = tfidf_matrix[1].toarray().flatten()

        missing_candidates = []
        for idx, word in enumerate(feature_names):
            if jd_weights[idx] > 0 and resume_weights[idx] == 0:
                if not word.isdigit():
                    missing_candidates.append((word, jd_weights[idx]))

        missing_candidates.sort(key=lambda item: item[1], reverse=True)
        missing_keywords = [
            word for word, _ in missing_candidates[:top_n_keywords]
        ]
    except ValueError:
        keyword_score = 0.0
        missing_keywords = []

    # 2. Semantic matching with sentence-transformers (with fallback)
    semantic_score = calculate_semantic_score(clean_resume, clean_jd)

    # 3. Combine scores into one final score
    if semantic_score is not None:
        # Balanced 50% keyword matching + 50% semantic context matching
        final_score = round(0.5 * keyword_score + 0.5 * semantic_score, 2)
    else:
        # Fall back to keyword score if semantic model could not load
        final_score = keyword_score

    return {
        "score": final_score,
        "final_score": final_score,
        "keyword_score": keyword_score,
        "semantic_score": semantic_score,
        "missing_keywords": missing_keywords,
    }
