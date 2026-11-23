import re
from typing import Dict, List, Any

# Common technical skill tokens for template matching
TECH_DICTIONARY = [
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "golang",
    "rust", "sql", "react", "angular", "vue", "django", "fastapi", "flask",
    "docker", "kubernetes", "aws", "azure", "gcp", "ci/cd", "microservices",
    "postgresql", "mongodb", "redis", "linux", "git", "machine learning",
    "pandas", "scikit-learn", "data engineering", "rest", "graphql", "devops"
]


def extract_key_technologies(text: str) -> List[str]:
    """Finds recognized technical skills mentioned in the text."""
    lower_text = text.lower()
    found: List[str] = []
    for tech in TECH_DICTIONARY:
        pattern = r"\b" + re.escape(tech) + r"\b"
        if re.search(pattern, lower_text):
            found.append(tech.title() if len(tech) > 3 else tech.upper())
    return found


def generate_interview_questions(
    job_description: str,
    resume_text: str,
    missing_keywords: List[str]
) -> Dict[str, List[Dict[str, str]]]:
    """Generates exactly 8 interview questions grouped by:

    - Technical (3)
    - Behavioral (2)
    - Gap-Related (3)
    """
    clean_jd = job_description.strip() if job_description else ""
    clean_resume = resume_text.strip() if resume_text else ""

    jd_technologies = extract_key_technologies(clean_jd)
    resume_technologies = extract_key_technologies(clean_resume)

    # 1. Technical Questions (3 questions)
    t1_skill = jd_technologies[0] if len(jd_technologies) > 0 else "core application architecture"
    t2_skill = jd_technologies[1] if len(jd_technologies) > 1 else (
        resume_technologies[0] if len(resume_technologies) > 0 else "system reliability and testing"
    )
    t3_skill = jd_technologies[2] if len(jd_technologies) > 2 else "scaling and performance optimization"

    technical_questions = [
        {
            "question": f"How have you designed, implemented, and maintained solutions using {t1_skill} in production?",
            "tip": f"Describe real architecture decisions, patterns, and trade-offs you encountered while working with {t1_skill}."
        },
        {
            "question": f"When troubleshooting complex bugs or performance bottlenecks related to {t2_skill}, what diagnostic process do you follow?",
            "tip": "Walk through your step-by-step debugging workflow: metrics, logs, root-cause isolation, and permanent mitigation."
        },
        {
            "question": f"How do you ensure maintainability, code quality, and test coverage when building systems with {t3_skill}?",
            "tip": "Mention automated testing, CI/CD integration, code reviews, and modular design practices."
        }
    ]

    # 2. Behavioral Questions (2 questions)
    behavioral_questions = [
        {
            "question": "Can you describe a challenging project where deadlines or requirements shifted unexpectedly? How did you prioritize deliverables and keep stakeholders aligned?",
            "tip": "Use the STAR framework (Situation, Task, Action, Result). Emphasize proactive communication and realistic prioritization."
        },
        {
            "question": "Tell me about a time you faced technical disagreement with a teammate or senior engineer. How did you resolve the conflict constructively?",
            "tip": "Focus on data-driven reasoning, collaborative problem solving, empathy, and working toward shared business goals."
        }
    ]

    # 3. Gap-Related Questions (3 questions)
    # Filter missing keywords to clean words (excluding numbers or trivial tokens)
    clean_gaps = [w.title() for w in missing_keywords if len(w) > 2 and not w.isdigit()]

    gap_1 = clean_gaps[0] if len(clean_gaps) > 0 else None
    gap_2 = clean_gaps[1] if len(clean_gaps) > 1 else None
    gap_3 = clean_gaps[2] if len(clean_gaps) > 2 else None

    gap_questions = []

    # Question 1: Direct Gap Inquiry
    if gap_1:
        gap_questions.append({
            "question": f"The job description highlights {gap_1} as a key requirement, which is not strongly emphasized in your resume. How familiar are you with it, and how would you approach ramping up?",
            "tip": f"Be honest. Acknowledge your current level with {gap_1}, highlight analogous tools you already know, and outline your 30-day learning plan."
        })
    else:
        gap_questions.append({
            "question": "Your background closely matches the requirements. What is an area or technology from the job description you are most excited to deepen your mastery in?",
            "tip": "Show intellectual curiosity and identify a nuanced area of the stack you want to specialize in further."
        })

    # Question 2: Transferable Skills & Adjacent Tools
    if gap_2:
        adjacent_context = resume_technologies[0] if resume_technologies else "your existing tech stack"
        gap_questions.append({
            "question": f"We noted {gap_2} is crucial for this position. How does your past experience with {adjacent_context} prepare you to tackle challenges involving {gap_2}?",
            "tip": "Highlight transferable architectural concepts, patterns, or similar tools to demonstrate that foundational knowledge transfers quickly."
        })
    else:
        gap_questions.append({
            "question": "Have you ever been assigned a project requiring a tool or language you had never used before? How did you deliver results on time?",
            "tip": "Detail your rapid learning strategy: reading docs, creating POCs, seeking mentorship, and delivering incrementally."
        })

    # Question 3: Proactive Learning & Adaptation Strategy
    if gap_3:
        gap_questions.append({
            "question": f"If tasked with delivering a feature using {gap_3} in your first month, how would you validate your work and avoid common beginner pitfalls?",
            "tip": "Talk about pair programming, reviewing established codebases for conventions, setting up comprehensive tests, and consulting official documentation."
        })
    else:
        gap_questions.append({
            "question": "When stepping into a new engineering team with established patterns, how do you balance adapting to their conventions while introducing fresh best practices?",
            "tip": "Demonstrate respect for team history, patience in understanding context before proposing changes, and proposing enhancements with data."
        })

    return {
        "technical": technical_questions,
        "behavioral": behavioral_questions,
        "gap_related": gap_questions
    }
