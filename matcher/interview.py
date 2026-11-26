import re
from typing import Dict, List
from matcher.skills_advisor import extract_all_skills, get_generic_words

_DOMAIN_KEYWORDS = {
    "teaching": {
        "teacher", "educator", "curriculum", "classroom", "students", "lesson",
        "pedagogy", "iep", "school", "faculty", "grading", "tutoring", "edtech",
        "differentiated instruction", "google classroom", "canvas lms", "esl"
    },
    "sales": {
        "sales", "quota", "pipeline", "prospecting", "cold calling", "b2b", "b2c",
        "account executive", "salesforce", "hubspot", "crm", "closing", "arr",
        "upselling", "lead generation", "territory", "outreach", "revenue"
    },
    "finance": {
        "finance", "financial", "fp&a", "accounting", "gaap", "ifrs", "audit",
        "auditing", "budgeting", "forecasting", "valuation", "dcf", "variance",
        "taxation", "reconciliation", "quickbooks", "sap", "portfolio", "bookkeeping"
    },
    "it": {
        "software", "engineer", "developer", "python", "java", "javascript", "sql",
        "react", "docker", "kubernetes", "aws", "api", "rest apis", "fastapi",
        "django", "git", "linux", "ci/cd", "microservices", "machine learning"
    },
}


def detect_domain(job_description: str, resume_text: str) -> str:
    """Infer the primary career field from JD and resume vocabulary."""
    combined = f"{job_description or ''} {resume_text or ''}".lower()
    scores: Dict[str, int] = {}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        scores[domain] = sum(
            1 for kw in keywords if re.search(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", combined)
        )

    best_domain = max(scores, key=lambda d: scores[d])
    return best_domain if scores[best_domain] > 0 else "general"


def extract_key_technologies(text: str) -> List[str]:
    """Return genuine domain skills found in text while preserving exact casing."""
    if not text:
        return []
    return extract_all_skills(text)


def generate_interview_questions(
    job_description: str,
    resume_text: str,
    missing_keywords: List[str]
) -> Dict[str, List[Dict[str, str]]]:
    """Generate exactly 8 domain-appropriate interview questions:

    - Technical / Role-Specific (3)
    - Behavioral (2)
    - Gap-Related (3)
    """
    clean_jd = job_description.strip() if job_description else ""
    clean_resume = resume_text.strip() if resume_text else ""

    jd_skills = extract_key_technologies(clean_jd)
    resume_skills = extract_key_technologies(clean_resume)
    domain = detect_domain(clean_jd, clean_resume)

    # 1. Role-Specific / Technical Questions (3)
    if domain == "teaching":
        s1 = jd_skills[0] if len(jd_skills) > 0 else "Curriculum Development"
        s2 = jd_skills[1] if len(jd_skills) > 1 else "Classroom Management"
        s3 = jd_skills[2] if len(jd_skills) > 2 else "Student Assessment"
        technical_questions = [
            {
                "question": f"How have you applied {s1} to improve student comprehension and engagement across diverse learning levels?",
                "tip": f"Share a concrete lesson or unit example showing how {s1} led to measurable student progress.",
            },
            {
                "question": f"Describe your approach to {s2} when handling disruptive behavior or varying academic readiness in the classroom.",
                "tip": "Explain proactive routines, clear expectations, and positive reinforcement strategies.",
            },
            {
                "question": f"How do you use {s3} data to adjust instruction and support struggling learners?",
                "tip": "Walk through formative vs. summative checks and how feedback loops guide your next lesson.",
            },
        ]
    elif domain == "sales":
        s1 = jd_skills[0] if len(jd_skills) > 0 else "Pipeline Management"
        s2 = jd_skills[1] if len(jd_skills) > 1 else "Prospecting"
        s3 = jd_skills[2] if len(jd_skills) > 2 else "Negotiation"
        technical_questions = [
            {
                "question": f"Walk me through how you manage {s1} from initial outreach to closed-won deals.",
                "tip": f"Highlight your qualification criteria, conversion metrics, and how you keep {s1} accurate.",
            },
            {
                "question": f"What is your playbook for {s2} and overcoming early buyer objections in a competitive market?",
                "tip": "Describe research, personalization, discovery questions, and follow-up cadence with real numbers.",
            },
            {
                "question": f"Tell me about a complex {s3} situation where a prospect pushed back on price or terms. How did you protect value and close?",
                "tip": "Focus on anchoring to business ROI, understanding decision-maker priorities, and win-win trade-offs.",
            },
        ]
    elif domain == "finance":
        s1 = jd_skills[0] if len(jd_skills) > 0 else "Financial Modeling"
        s2 = jd_skills[1] if len(jd_skills) > 1 else "Forecasting"
        s3 = jd_skills[2] if len(jd_skills) > 2 else "Variance Analysis"
        technical_questions = [
            {
                "question": f"Walk me through a {s1} deliverable you built from scratch. How did you structure assumptions and validate accuracy?",
                "tip": f"Explain driver-based inputs, sensitivity checks, error controls, and how stakeholders used your {s1} work.",
            },
            {
                "question": f"How do you approach {s2} when business conditions shift mid-quarter or historical data is incomplete?",
                "tip": "Discuss scenario modeling (base/upside/downside), cross-functional input, and communicating uncertainty.",
            },
            {
                "question": f"When conducting {s3} during month-end or quarter-end close, how do you investigate discrepancies and present insights to leadership?",
                "tip": "Emphasize materiality thresholds, root-cause drill-down, and clear executive storytelling.",
            },
        ]
    elif domain == "it":
        s1 = jd_skills[0] if len(jd_skills) > 0 else "core system architecture"
        s2 = jd_skills[1] if len(jd_skills) > 1 else (resume_skills[0] if resume_skills else "debugging and reliability")
        s3 = jd_skills[2] if len(jd_skills) > 2 else "testing and maintainability"
        technical_questions = [
            {
                "question": f"How have you designed, implemented, and maintained solutions using {s1} in production or project work?",
                "tip": f"Describe real architecture decisions, trade-offs, and measurable outcomes involving {s1}.",
            },
            {
                "question": f"When troubleshooting complex bugs or performance bottlenecks involving {s2}, what diagnostic process do you follow?",
                "tip": "Walk through your debugging steps: reproducing issues, checking logs/metrics, isolating root cause, and verifying the fix.",
            },
            {
                "question": f"How do you ensure maintainability, reliability, and quality when working with {s3}?",
                "tip": "Mention automated testing, peer reviews, clear documentation, and modular design.",
            },
        ]
    else:
        s1 = jd_skills[0] if len(jd_skills) > 0 else "core job workflows"
        s2 = jd_skills[1] if len(jd_skills) > 1 else (resume_skills[0] if resume_skills else "problem solving")
        s3 = jd_skills[2] if len(jd_skills) > 2 else "quality and execution"
        technical_questions = [
            {
                "question": f"Can you share a concrete example of how you applied {s1} to deliver measurable results?",
                "tip": f"Explain the context, your specific actions with {s1}, and the final outcome.",
            },
            {
                "question": f"When an issue or bottleneck arises around {s2}, what step-by-step process do you use to resolve it?",
                "tip": "Show structured thinking: gathering facts, evaluating options, communicating updates, and preventing recurrence.",
            },
            {
                "question": f"How do you maintain high standards of accuracy and consistency in {s3} under tight deadlines?",
                "tip": "Highlight checklists, prioritization habits, and stakeholder alignment.",
            },
        ]

    # 2. Behavioral Questions (2)
    if domain == "teaching":
        behavioral_questions = [
            {
                "question": "Tell me about a time a lesson or teaching strategy did not land as planned. How did you adapt in real time?",
                "tip": "Use STAR (Situation, Task, Action, Result) and emphasize flexibility and student outcomes.",
            },
            {
                "question": "Describe a situation where you collaborated with parents, counselors, or fellow teachers to support a struggling student.",
                "tip": "Highlight empathy, clear communication, and follow-through.",
            },
        ]
    elif domain == "sales":
        behavioral_questions = [
            {
                "question": "Tell me about a quarter where you were behind on target. What actions did you take to turn the pipeline around?",
                "tip": "Use STAR and focus on activity discipline, coaching feedback, and measurable recovery.",
            },
            {
                "question": "Describe a time you had to align internal stakeholders (product, legal, or customer success) to save or close a key account.",
                "tip": "Demonstrate ownership, persuasive communication, and focus on long-term client value.",
            },
        ]
    elif domain == "finance":
        behavioral_questions = [
            {
                "question": "Describe a time you uncovered a significant financial discrepancy or risk. How did you escalate and resolve it?",
                "tip": "Use STAR and emphasize analytical rigor, integrity, and clear documentation.",
            },
            {
                "question": "Tell me about a time non-finance stakeholders pushed back on your budget recommendations. How did you align on a decision?",
                "tip": "Show how you translated numbers into operational trade-offs without jargon.",
            },
        ]
    else:
        behavioral_questions = [
            {
                "question": "Describe a challenging project or assignment where priorities shifted unexpectedly. How did you re-prioritize and keep stakeholders aligned?",
                "tip": "Use the STAR framework (Situation, Task, Action, Result) and highlight proactive communication.",
            },
            {
                "question": "Tell me about a time you disagreed with a teammate or manager on how to handle a task. How did you resolve it constructively?",
                "tip": "Focus on objective evidence, active listening, and shared goals.",
            },
        ]

    # 3. Gap-Related Questions (3) — preserve exact skill casing and filter generic words
    generic_words = get_generic_words()
    clean_gaps = [
        w.strip()
        for w in missing_keywords
        if w and len(w.strip()) > 1 and w.strip().lower() not in generic_words and not w.strip().isdigit()
    ]

    gap_1 = clean_gaps[0] if len(clean_gaps) > 0 else None
    gap_2 = clean_gaps[1] if len(clean_gaps) > 1 else None
    gap_3 = clean_gaps[2] if len(clean_gaps) > 2 else None

    adjacent_context = resume_skills[0] if resume_skills else "your existing experience"
    gap_questions: List[Dict[str, str]] = []

    if gap_1:
        gap_questions.append({
            "question": f"The job description highlights {gap_1}, which is not emphasized on your resume. What is your current familiarity with {gap_1}, and how would you ramp up quickly?",
            "tip": f"Be honest about your level with {gap_1}, connect it to related skills you have, and share a concrete 30-day learning plan.",
        })
    else:
        gap_questions.append({
            "question": "Your background aligns well with the posted requirements. Which aspect of this role are you most eager to grow in over your first 90 days?",
            "tip": "Pick a meaningful responsibility from the job posting and explain how you plan to add value early.",
        })

    if gap_2:
        gap_questions.append({
            "question": f"We noticed {gap_2} is important for this role. How does your experience with {adjacent_context} help you get up to speed on {gap_2}?",
            "tip": f"Draw parallels between {adjacent_context} and {gap_2} to show transferable fundamentals.",
        })
    else:
        gap_questions.append({
            "question": "Tell me about a time you had to learn a new tool, process, or subject area quickly on the job. How did you become productive?",
            "tip": "Walk through how you structured your learning, sought feedback, and delivered results on schedule.",
        })

    if gap_3:
        gap_questions.append({
            "question": f"If asked to contribute to work involving {gap_3} in your first month, how would you validate accuracy and avoid common mistakes?",
            "tip": f"Mention reviewing team standards, shadowing peers, using checklists/tests, and consulting official {gap_3} resources.",
        })
    else:
        gap_questions.append({
            "question": "When joining a new team with established workflows, how do you balance learning their current process with suggesting improvements?",
            "tip": "Show respect for existing context, ask thoughtful questions first, and back suggestions with clear evidence.",
        })

    return {
        "technical": technical_questions,
        "behavioral": behavioral_questions,
        "gap_related": gap_questions,
    }
