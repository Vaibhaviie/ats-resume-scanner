import hashlib
import re
import time
import pandas as pd
import streamlit as st

from matcher.ats_checks import run_ats_checks
from matcher.bullets import analyze_bullets
from matcher.interview import generate_interview_questions
from matcher.layout_detector import detect_layout_warnings
from matcher.parser import parse_resume
from matcher.scorer import calculate_match
from matcher.skills_advisor import find_missing_skills

# Configure the Streamlit page with a responsive layout for desktop and mobile
st.set_page_config(
    page_title="ATS Resume Matcher",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="auto",
)

# Subtle responsive CSS for clean mobile & desktop rendering
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2.5rem;
    }
    .stMarkdown code {
        white-space: normal;
        word-break: break-word;
    }
    @media (max-width: 768px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
            padding-top: 1rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _is_mostly_non_english(text: str) -> bool:
    """Detect whether alphabetic characters are predominantly non-ASCII/non-English."""
    alpha_chars = [ch for ch in text if ch.isalpha()]
    if len(alpha_chars) < 20:
        return False
    ascii_alpha = sum(1 for ch in alpha_chars if "a" <= ch.lower() <= "z")
    return (ascii_alpha / len(alpha_chars)) < 0.5


def _build_prioritized_actions(
    layout_warnings: list,
    ats_results: list,
    bullet_data: dict,
    missing_skills: list,
) -> list:
    """Create a concise, non-repetitive prioritized list of next steps."""
    actions = []

    if layout_warnings:
        issue_names = ", ".join(w["issue"] for w in layout_warnings[:3])
        actions.append(
            f"**Fix Layout Traps ({issue_names}):** Switch to a clean single-column layout without tables, floating text boxes, or header/footer contact details."
        )

    failed_ats = [c for c in ats_results if not c["passed"]]
    for check in failed_ats:
        name = check["name"]
        if name == "Standard Section Headings":
            actions.append("**Add Missing Section Headings:** Include clear standalone titles (Summary, Skills, Experience/Projects, Education).")
        elif name == "Contact Information":
            actions.append("**Complete Contact Info:** Place both a standard email address and 10-digit phone number in the main body.")
        elif name == "Resume Length":
            actions.append("**Adjust Resume Length:** Aim for 60–900 words (1–2 concise pages) focused on relevant impact.")
        elif name == "ATS-Friendly Characters":
            actions.append("**Clean Up Special Symbols:** Replace icons, emojis, or unrecognized glyphs with plain text and standard bullets.")

    flagged_bullets = bullet_data.get("flagged_count", 0)
    total_bullets = bullet_data.get("total_bullets", 0)
    if total_bullets > 0 and flagged_bullets > 0:
        actions.append(
            f"**Strengthen Experience Bullets:** Refine the {flagged_bullets} flagged bullet(s) with strong action verbs and genuine metrics."
        )

    req_missing = [s["skill"] for s in missing_skills if s.get("level") == "Required"]
    if req_missing:
        top_req = ", ".join(req_missing[:4])
        actions.append(
            f"**Address Required Skill Gaps:** If you genuinely have experience with {top_req}, highlight them clearly in your Skills or Experience section."
        )

    return actions


# ---------------------------------------------------------
# Sidebar: How-To-Use Guide & Privacy Note
# ---------------------------------------------------------
with st.sidebar:
    st.title("📄 ATS Resume Matcher")
    st.caption("Free Resume Scanner & Job Match Analyzer")

    st.markdown("---")
    st.subheader("📖 How to Use")
    st.markdown(
        """
        1. **Upload Resume**: Choose a text-based `.pdf` or `.docx` file (under 10 MB).
        2. **Paste Job Descriptions**: Add up to 5 target roles in the tabs.
        3. **Compare & Rank**: Click **Compare & Rank Jobs** to see keyword & AI semantic scores.
        4. **Review Health & Skills**: Fix layout traps, bullet phrasing, and genuine skill gaps.
        5. **Practice Interviews**: Prepare with 8 role-specific questions.
        """
    )

    st.markdown("---")
    st.subheader("🔒 Privacy Notice")
    st.info(
        "**Your resume is not stored.**\n\n"
        "All parsing and matching happen temporarily in memory during your session. "
        "Files and text are never saved to a database, shared, or used to train models."
    )

    st.markdown("---")
    st.caption("Guidance tool only • Always represent your experience truthfully.")


# ---------------------------------------------------------
# Main Page Header + Visible Privacy & Quick Guide Strip
# ---------------------------------------------------------
st.title("🎯 ATS Resume Matcher")
st.markdown(
    "Check how well your resume matches target job descriptions, uncover ATS formatting issues, "
    "and spot genuine skill gaps — free for every job seeker."
)

info_col1, info_col2 = st.columns(2)
with info_col1:
    st.info(
        "🔒 **Privacy:** Your resume is not stored. Everything runs in memory for this session only "
        "and disappears when you close or refresh the page."
    )
with info_col2:
    st.success(
        "🧭 **Quick Guide:** Upload your PDF/DOCX resume below, paste 1–5 job postings, "
        "and click **Compare & Rank Jobs**. *Note: Automated scores are guidance only.*"
    )


# ---------------------------------------------------------
# Section 1: Resume Upload & Parsing ("What the ATS sees")
# ---------------------------------------------------------
st.subheader("1. Upload Your Resume")

uploaded_resume = st.file_uploader(
    "Upload your resume in PDF or DOCX format (max 10 MB)",
    type=["pdf", "docx"],
    help="Supports standard text-based single or multi-page resumes in PDF or Word (.docx) format.",
)

resume_text = ""
layout_warnings = []
resume_valid = False

if uploaded_resume is not None:
    try:
        file_bytes_sig = f"{uploaded_resume.name}:{getattr(uploaded_resume, 'size', 0)}"
        file_sig = hashlib.sha256(file_bytes_sig.encode("utf-8", errors="ignore")).hexdigest()
    except Exception:
        file_sig = getattr(uploaded_resume, "name", "uploaded")

    # Clear stale results if a different resume is uploaded
    if st.session_state.get("uploaded_file_sig") != file_sig:
        st.session_state["uploaded_file_sig"] = file_sig
        st.session_state.pop("comparison_results", None)
        st.session_state.pop("active_resume_text", None)
        st.session_state.pop("active_layout_warnings", None)

    try:
        parsed = parse_resume(uploaded_resume)
    except Exception:
        parsed = {
            "text": "",
            "error": "We couldn't read this file. Please try re-exporting it as a standard PDF or DOCX.",
            "warning": None,
        }

    if parsed.get("error"):
        st.error(parsed["error"])
    else:
        resume_text = parsed["text"]
        resume_valid = True

        if parsed.get("warning"):
            st.warning(parsed["warning"])

        word_count = len(resume_text.split())
        col_meta1, col_meta2 = st.columns(2)
        col_meta1.metric("File Name", uploaded_resume.name)
        col_meta2.metric("Parsed Word Count", f"{word_count} words")

        if word_count < 30:
            st.info(
                "ℹ️ Your parsed resume has very few words. Match scores and ATS checks work best with a full resume."
            )
        if _is_mostly_non_english(resume_text):
            st.info(
                "ℹ️ Non-English text detected. Keyword and skill matching is designed for English resumes, "
                "though semantic scoring will still run."
            )

        with st.expander("👀 What the ATS Sees (Parsed Plain Text)", expanded=False):
            st.caption("Raw plain text extracted from your document:")
            st.text_area("Parsed Text Output", value=resume_text, height=180, disabled=True)

        try:
            layout_warnings = detect_layout_warnings(uploaded_resume, resume_text)
        except Exception:
            layout_warnings = []

        if layout_warnings:
            st.warning(
                f"⚠️ Detected {len(layout_warnings)} layout issue(s) that could affect automated ATS parsing:"
            )
            for w in layout_warnings:
                with st.expander(f"⚠️ **{w['issue']}**"):
                    st.write(f"**Why it matters:** {w['description']}")
                    st.info(f"💡 **Simple Fix:** {w['fix']}")
        else:
            st.success(
                "✅ Clean layout detected! No tables, multi-column traps, floating text boxes, or header/footer risks found."
            )
else:
    # Clear stale results if the user removes the uploaded file
    if "uploaded_file_sig" in st.session_state:
        st.session_state.pop("uploaded_file_sig", None)
        st.session_state.pop("comparison_results", None)
        st.session_state.pop("active_resume_text", None)
        st.session_state.pop("active_layout_warnings", None)

st.markdown("---")


# ---------------------------------------------------------
# Section 2: Target Job Descriptions (Up to 5)
# ---------------------------------------------------------
st.subheader("2. Target Job Descriptions")
st.caption("Paste up to 5 job descriptions below to compare and rank your compatibility across positions.")

job_tabs = st.tabs([f"📋 Job {i+1}" for i in range(5)])
jobs_data = []

for i, tab in enumerate(job_tabs):
    with tab:
        default_title = f"Target Role {i+1}" if i == 0 else ""
        job_title = st.text_input(
            f"Job {i+1} Title",
            value=default_title,
            placeholder="e.g. Senior Software Engineer, Math Teacher, Account Executive",
            max_chars=120,
            key=f"ui_job_title_{i}",
        )
        job_desc = st.text_area(
            f"Job {i+1} Description",
            placeholder=f"Paste Job {i+1} requirements, qualifications, and responsibilities here...",
            height=160,
            max_chars=25000,
            key=f"ui_job_desc_{i}",
        )
        if job_desc and job_desc.strip():
            jobs_data.append({
                "id": i + 1,
                "title": (job_title or "").strip() or f"Job {i+1}",
                "description": job_desc.strip(),
            })

st.write("")

start_matching = st.button("🚀 Compare & Rank Jobs", type="primary", use_container_width=True)

if start_matching:
    if uploaded_resume is None:
        st.error("Please upload your resume first (PDF or DOCX).")
    elif not resume_valid or not resume_text.strip():
        st.error("Please upload a valid, readable resume before running the comparison.")
    elif len(jobs_data) == 0:
        st.error("Please paste at least one job description to compare against.")
    else:
        short_jds = [j["title"] for j in jobs_data if len(j["description"].split()) < 10]
        if short_jds:
            st.info(
                f"ℹ️ Very short job description(s) detected ({', '.join(short_jds)}). "
                "Adding full requirements gives much more accurate results."
            )

        progress_bar = st.progress(0, text="Initializing matching engine...")
        all_results = []
        total_jobs = len(jobs_data)
        had_error = False

        try:
            for idx, job in enumerate(jobs_data, 1):
                progress_bar.progress(
                    int((idx / total_jobs) * 90),
                    text=f"Evaluating Job {idx}/{total_jobs}: '{job['title']}'...",
                )
                match_res = calculate_match(resume_text, job["description"])
                all_results.append({
                    "id": job["id"],
                    "title": job["title"],
                    "description": job["description"],
                    "final_score": match_res["final_score"],
                    "keyword_score": match_res["keyword_score"],
                    "semantic_score": match_res["semantic_score"],
                    "missing_keywords": match_res["missing_keywords"],
                    "missing_skills": match_res.get("missing_skills", []),
                })

            progress_bar.progress(100, text="Finalizing rankings...")
            time.sleep(0.2)
        except Exception:
            had_error = True
            st.error(
                "Something went wrong while analyzing your match. Please check your inputs and try again."
            )
        finally:
            progress_bar.empty()

        if not had_error and all_results:
            all_results.sort(key=lambda x: x["final_score"], reverse=True)
            st.session_state["comparison_results"] = all_results
            st.session_state["active_resume_text"] = resume_text
            st.session_state["active_layout_warnings"] = layout_warnings


# ---------------------------------------------------------
# Section 3: Ranked Job Results & Detailed Drill-Down
# ---------------------------------------------------------
if st.session_state.get("comparison_results"):
    results = st.session_state["comparison_results"]
    active_resume = st.session_state.get("active_resume_text", resume_text)
    active_layout_warnings = st.session_state.get("active_layout_warnings", layout_warnings)

    st.markdown("---")
    st.subheader("3. Ranked Job Matches")
    st.caption("Roles sorted by overall compatibility so you know where your resume is strongest.")

    table_rows = []
    for rank, res in enumerate(results, 1):
        score = res["final_score"]
        if score >= 70:
            rec = "🟢 Strong Match — Apply First"
        elif score >= 45:
            rec = "🟡 Moderate Match — Address Gaps"
        else:
            rec = "🔴 Low Match — Tailoring Needed"

        semantic_val = f"{res['semantic_score']}%" if res["semantic_score"] is not None else "N/A"
        missing_preview = ", ".join(res["missing_keywords"][:3]) if res["missing_keywords"] else "None"

        table_rows.append({
            "Rank": f"#{rank}",
            "Job Title": res["title"],
            "Overall Score": f"{score}%",
            "Keyword & Skill Match": f"{res['keyword_score']}%",
            "Semantic Match": semantic_val,
            "Top Missing Skills": missing_preview,
            "Recommendation": rec,
        })

    df = pd.DataFrame(table_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Detailed Job Drill-Down Selector
    st.markdown("---")
    st.subheader("4. Detailed Job Report & Gap Analysis")
    job_labels = [f"#{rank} {r['title']} ({r['final_score']}%)" for rank, r in enumerate(results, 1)]

    selected_index = st.selectbox(
        "Choose a job to view its full breakdown, resume health checks, and interview prep:",
        options=range(len(results)),
        format_func=lambda i: job_labels[i],
    )

    selected_job = results[selected_index]
    sel_score = selected_job["final_score"]

    st.markdown(f"### Detailed Analysis for: **{selected_job['title']}**")

    if _is_mostly_non_english(selected_job["description"]):
        st.info(
            "ℹ️ This job description contains mostly non-English text. Skill extraction is tuned for English postings."
        )

    progress_color_label = (
        "Strong Match" if sel_score >= 70 else ("Moderate Match" if sel_score >= 45 else "Needs Improvement")
    )
    st.progress(
        min(1.0, max(0.0, sel_score / 100.0)),
        text=f"Overall Score: {sel_score}% ({progress_color_label})",
    )

    if selected_job["semantic_score"] is not None:
        c1, c2, c3 = st.columns(3)
        c1.metric("Overall Match", f"{sel_score}%")
        c2.metric("Keyword & Skill Match", f"{selected_job['keyword_score']}%")
        c3.metric("Semantic Match (AI)", f"{selected_job['semantic_score']}%")
        st.caption(
            "💡 **Keyword & Skill Match** measures direct terminology and required skill overlap. "
            "**Semantic Match** uses AI sentence embeddings to recognize related experience even with different wording."
        )
    else:
        st.metric("Overall Match (Keyword Fallback)", f"{sel_score}%")
        st.info("ℹ️ Semantic AI model is temporarily unavailable; score was calculated using keyword and skill matching.")

    st.write("")

    # Precompute skills, ATS checks, and bullets safely
    missing_skills = selected_job.get("missing_skills", [])
    if not missing_skills:
        try:
            missing_skills = find_missing_skills(active_resume, selected_job["description"], max_skills=8)
        except Exception:
            missing_skills = []

    try:
        ats_results = run_ats_checks(active_resume)
    except Exception:
        ats_results = []

    try:
        bullet_data = analyze_bullets(active_resume)
    except Exception:
        bullet_data = {"total_bullets": 0, "flagged_count": 0, "results": [], "recommended_verbs": {}}

    # -----------------------------------------------------
    # ATS-Friendliness Checks & Non-Repetitive Action Items
    # -----------------------------------------------------
    with st.expander("🛡️ ATS-Friendliness Checks & Prioritized Action Items", expanded=True):
        if ats_results:
            passed_count = sum(1 for c in ats_results if c["passed"])
            total_checks = len(ats_results)
            readiness_pct = int((passed_count / total_checks) * 100) if total_checks > 0 else 0
            st.progress(
                readiness_pct / 100.0,
                text=f"ATS Readiness Score: {passed_count}/{total_checks} Checks Passed ({readiness_pct}%)",
            )

            for check in ats_results:
                is_pass = check["passed"]
                icon = "✅" if is_pass else "❌"
                badge = ":green[**PASS**]" if is_pass else ":red[**FAIL**]"
                st.markdown(f"{icon} **{check['name']}** &mdash; {badge}")
                st.caption(check["tip"])
        else:
            st.info("ATS formatting checks could not be completed for this text.")

        st.markdown("#### 📋 Prioritized Action Items")
        actions = _build_prioritized_actions(
            active_layout_warnings, ats_results, bullet_data, missing_skills
        )
        if actions:
            for idx, action_text in enumerate(actions, 1):
                st.markdown(f"{idx}. {action_text}")
        else:
            st.success("🎉 Great shape! All ATS formatting, bullet strength, and required skill checks look solid.")

    # -----------------------------------------------------
    # Experience Bullet Points Analysis
    # -----------------------------------------------------
    with st.expander("✍️ Experience Bullet Points Analysis", expanded=True):
        tot_b = bullet_data.get("total_bullets", 0)
        flag_b = bullet_data.get("flagged_count", 0)

        if tot_b == 0:
            st.info(
                "No distinct experience or project bullet points were detected. "
                "Using standard bullet points (`•` or `-`) helps both recruiters and ATS parsers scan achievements."
            )
        else:
            col_b1, col_b2 = st.columns(2)
            col_b1.metric("Bullets Analyzed", tot_b)
            col_b2.metric("Bullets Needing Refinement", flag_b)

            if flag_b == 0:
                st.success("Great job! All analyzed bullet points start with strong action verbs and include metrics.")
            else:
                st.write("Review these flagged bullets to strengthen your impact:")
                for item in bullet_data.get("results", []):
                    if not item["passed"]:
                        preview = item["bullet"][:70] + ("..." if len(item["bullet"]) > 70 else "")
                        with st.expander(f"⚠️ {preview}"):
                            st.write(f"**Bullet:** \"{item['bullet']}\"")
                            st.write("**Issues found:**")
                            for iss in item["issues"]:
                                st.markdown(f"- ❌ **{iss}**")
                            st.write("**Suggestions:**")
                            for sug in item["suggestions"]:
                                st.markdown(f"- 💡 {sug}")

            with st.expander("📖 Reference List: Strong Action Verbs"):
                st.caption("Never invent facts. Use these strong verbs to accurately describe your real accomplishments:")
                for cat, verbs in bullet_data.get("recommended_verbs", {}).items():
                    title = cat.replace("_", " ").title()
                    st.markdown(f"**{title}:** " + ", ".join([f"`{v}`" for v in verbs]))

    # -----------------------------------------------------
    # Missing Skills & How-to-Add Guide (Compact Table)
    # -----------------------------------------------------
    st.subheader(f"🔑 Missing Skills ({len(missing_skills)})")

    if missing_skills:
        st.markdown("⚠️ *Integrity Rule: Only add skills you genuinely have.*")
        st.markdown(" ".join([f"`{item['skill']}`" for item in missing_skills]))
        st.write("")

        table_records = [
            {
                "Skill": item["skill"],
                "Required or Preferred": item["level"],
                "Best section to add it": item["best_section"],
            }
            for item in missing_skills
        ]
        df_skills = pd.DataFrame(table_records)
        st.dataframe(df_skills, use_container_width=True, hide_index=True)
    else:
        st.success("🎉 Excellent match! No key skills from this job description are missing from your resume.")

    st.write("")

    # -----------------------------------------------------
    # Interview Preparation Section (8 Likely Questions)
    # -----------------------------------------------------
    with st.expander(f"🎯 Interview Preparation: {selected_job['title']} (8 Questions)", expanded=True):
        st.caption("Tailored interview questions based on the job field, requirements, and your resume gaps.")
        try:
            missing_kw_list = [item["skill"] for item in missing_skills]
            interview_data = generate_interview_questions(
                selected_job["description"], active_resume, missing_kw_list
            )

            tab_t, tab_b, tab_g = st.tabs([
                f"🛠️ Role-Specific ({len(interview_data['technical'])})",
                f"🤝 Behavioral ({len(interview_data['behavioral'])})",
                f"🎯 Gap-Related ({len(interview_data['gap_related'])})",
            ])

            with tab_t:
                for idx, q in enumerate(interview_data["technical"], 1):
                    st.markdown(f"**{idx}. {q['question']}**")
                    st.caption(f"💡 *Strategy Tip:* {q['tip']}")
                    st.write("")

            with tab_b:
                for idx, q in enumerate(interview_data["behavioral"], 1):
                    st.markdown(f"**{idx}. {q['question']}**")
                    st.caption(f"💡 *Strategy Tip:* {q['tip']}")
                    st.write("")

            with tab_g:
                for idx, q in enumerate(interview_data["gap_related"], 1):
                    st.markdown(f"**{idx}. {q['question']}**")
                    st.caption(f"💡 *Strategy Tip:* {q['tip']}")
                    st.write("")
        except Exception:
            st.info("Interview questions could not be generated for this job posting. Try adding more detail to the job description.")
