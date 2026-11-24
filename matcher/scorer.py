from typing import Any, Dict, List
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from matcher.semantic import calculate_semantic_score
from matcher.skills_advisor import find_missing_skills


def calculate_match(
    resume_text: str,
    job_description: str,
    top_n_keywords: int = 8
) -> Dict[str, Any]:
    """Compare resume text and job description using TF-IDF and semantic embeddings.

    Missing skills are strictly derived from genuine skills (data/skills.json and data/synonyms.json),
    filtering out generic job-post terms (data/generic_words.json).
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
            "missing_skills": [],
        }

    # 1. Keyword matching via TF-IDF & Cosine Similarity
    keyword_score = 0.0
    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform([clean_resume, clean_jd])
        sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        keyword_score = round(float(sim) * 100, 2)
    except ValueError:
        keyword_score = 0.0

    # 2. Extract genuine missing skills (never raw TF-IDF generic words)
    missing_skills_data = find_missing_skills(clean_resume, clean_jd, max_skills=top_n_keywords)
    missing_keywords = [item["skill"] for item in missing_skills_data]

    # 3. Semantic matching with sentence-transformers (with fallback)
    semantic_score = calculate_semantic_score(clean_resume, clean_jd)

    # 4. Combine scores into one final score
    if semantic_score is not None:
        final_score = round(0.5 * keyword_score + 0.5 * semantic_score, 2)
    else:
        final_score = keyword_score

    return {
        "score": final_score,
        "final_score": final_score,
        "keyword_score": keyword_score,
        "semantic_score": semantic_score,
        "missing_keywords": missing_keywords,
        "missing_skills": missing_skills_data,
    }
