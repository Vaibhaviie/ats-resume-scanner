from typing import Any, Dict, List

# Common technology tools, libraries, and languages
TECH_KEYWORDS = {
    "python", "java", "c++", "c#", "javascript", "typescript", "golang", "rust",
    "react", "angular", "vue", "django", "flask", "fastapi", "spring", "node",
    "sql", "postgresql", "mysql", "mongodb", "redis", "docker", "kubernetes",
    "aws", "azure", "gcp", "git", "linux", "terraform", "graphql", "rest",
    "pandas", "numpy", "scikit-learn", "pytorch", "tensorflow", "tableau", "powerbi"
}

# Domain methodologies, practices, and concepts
METHODOLOGY_KEYWORDS = {
    "agile", "scrum", "ci/cd", "devops", "microservices", "machine learning",
    "deep learning", "ai", "data analysis", "cloud", "testing", "security",
    "system design", "architecture", "optimization", "automation", "etl", "analytics"
}


def get_skill_tip(skill: str) -> Dict[str, str]:
    """Generates placement guidance and learning suggestions for a missing skill."""
    s_lower = skill.strip().lower()

    if any(tech in s_lower for tech in TECH_KEYWORDS):
        section = "Skills (and back up in Experience or Projects)"
        how_to_add = (
            f"Add '{skill}' under your **Skills** section (e.g. under Languages or Tools), "
            f"and mention a specific achievement or task using it in your **Experience** or **Projects** bullets."
        )
        how_to_learn = (
            f"Review the official documentation for {skill.title()}, follow beginner-to-intermediate tutorials "
            f"(e.g., freeCodeCamp, Codecademy, or official quickstarts), and build a small practice project."
        )
    elif any(method in s_lower for method in METHODOLOGY_KEYWORDS):
        section = "Experience or Projects (Contextualized)"
        how_to_add = (
            f"Incorporate '{skill}' into your **Experience** or **Projects** bullet points showing how you applied it "
            f"(e.g., 'Implemented {skill} workflows that improved team delivery time')."
        )
        how_to_learn = (
            f"Explore practical guides, books, or online courses (e.g., Coursera, edX) covering {skill.title()} fundamentals, "
            f"and apply the practices in personal or open-source projects."
        )
    else:
        section = "Skills or Experience"
        how_to_add = (
            f"If you have experience with '{skill}', list it in your **Skills** section and reference it within a relevant "
            f"bullet point under **Experience**."
        )
        how_to_learn = (
            f"Research foundational guides, industry articles, or tutorials on {skill.title()} to build working familiarity "
            f"before including it on your resume."
        )

    return {
        "skill": skill,
        "section": section,
        "how_to_add": how_to_add,
        "how_to_learn": how_to_learn,
    }


def generate_skill_advice(missing_skills: List[str]) -> List[Dict[str, str]]:
    """Generates advice for each missing skill in the list."""
    return [get_skill_tip(skill) for skill in missing_skills]
