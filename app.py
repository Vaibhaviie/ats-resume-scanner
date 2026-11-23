import time
import pandas as pd
import streamlit as st

from matcher.ats_checks import run_ats_checks
from matcher.bullets import analyze_bullets
from matcher.interview import generate_interview_questions
from matcher.layout_detector import detect_layout_warnings
from matcher.parser import extract_text
from matcher.scorer import calculate_match
from matcher.skills_advisor import generate_skill_advice

# Configure the Streamlit page with a responsive, modern layout
st.set_page_config(
    page_title="ATS Resume Matcher",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------
# Sidebar: Navigation, How-To-Use Guide, and Privacy Note
# ---------------------------------------------------------
with st.sidebar:
    st.title("📄 ATS Resume Matcher")
    st.caption("AI-Powered Resume Scanner & Job Matcher")

    st.markdown("---")

    # How to Use Guide
    st.subheader("📖 How to Use")
    st.markdown(
        """
        1. **Upload Resume**: Choose a `.pdf` or `.docx` file to preview what an ATS parser sees.
        2. **Enter Job Postings**: Paste up to 5 target job descriptions with titles in the tabs.
        3. **Compare & Rank**: Click **Compare & Rank Jobs** to calculate keyword and AI semantic match scores.
        4. **Review ATS Health**: Inspect layout warnings, formatting checks, and bullet point feedback.
        5. **Prep for Interviews**: Review the 8 customized interview questions generated for your target role.
        """
    )

    st.markdown("---")

    # Privacy Notice
    st.subheader("🔒 Privacy Notice")
    st.info(
        "**Your data stays private:**\n\n"
        "All resume parsing and semantic evaluations occur locally in memory within your current session. "
        "Files and text are never saved to external databases, shared, or used to train third-party models."
    )

    st.markdown("---")
    st.caption("v1.5 • Powered by Streamlit & Sentence-Transformers")

# ---------------------------------------------------------
# Main Page Header
# ---------------------------------------------------------
st.title("🎯 ATS Resume Matcher")
st.markdown(
    "Optimize your resume for Applicant Tracking Systems (ATS), compare multiple job opportunities, "
    "and discover high-impact ways to improve your application."
)

st.write("")

# ---------------------------------------------------------
# Section 1: Resume Upload & Parsing ("What the ATS sees")
# ---------------------------------------------------------
st.subheader("1. Upload Your Resume")

uploaded_resume = st.file_uploader(
    "Upload your resume in PDF or DOCX format",
    type=["pdf", "docx"],
    help="Supports standard single and multi-page resumes in PDF or Word formats."
)

resume_text = ""
if uploaded_resume:
    resume_text = extract_text(uploaded_resume)
    word_count = len(resume_text.split()) if resume_text else 0

    col_meta1, col_meta2 = st.columns(2)
    col_meta1.metric("File Name", uploaded_resume.name)
    col_meta2.metric("Parsed Word Count", f"{word_count} words")

    # "What the ATS sees" view
    with st.expander("👀 What the ATS Sees (Parsed Plain Text)", expanded=True):
        st.caption("This is the raw, unformatted text extracted by an ATS from your document:")
        st.text_area("Parsed Text Output", value=resume_text, height=180, disabled=True)

    # Layout trap warnings
    layout_warnings = detect_layout_warnings(uploaded_resume, resume_text)
    if layout_warnings:
        st.warning(f"⚠️ We detected {len(layout_warnings)} layout issue(s) that could disrupt automated ATS parsing:")
        for w in layout_warnings:
            with st.expander(f"⚠️ **{w['issue']}**"):
                st.write(f"**Why it matters:** {w['description']}")
                st.info(f"💡 **Simple Fix:** {w['fix']}")
    else:
        st.success("✅ Clean layout detected! No problematic tables, columns, floating text boxes, or header traps.")

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
            placeholder="e.g. Senior Software Engineer",
            key=f"ui_job_title_{i}"
        )
        job_desc = st.text_area(
            f"Job {i+1} Description",
            placeholder=f"Paste Job {i+1} requirements, qualifications, and responsibilities here...",
            height=160,
            key=f"ui_job_desc_{i}"
        )
        if job_desc.strip():
            jobs_data.append({
                "id": i + 1,
                "title": job_title.strip() or f"Job {i+1}",
                "description": job_desc.strip()
            })

st.write("")

# Button to trigger analysis
start_matching = st.button("🚀 Compare & Rank Jobs", type="primary", use_container_width=True)

if start_matching:
    if not uploaded_resume:
        st.error("Please upload a resume first.")
    elif not resume_text.strip() or resume_text.startswith("No readable text found"):
        st.error("The uploaded resume does not contain readable text. Please check the file.")
    elif len(jobs_data) == 0:
        st.error("Please enter at least one job description.")
    else:
        progress_slot = st.empty()
        progress_bar = st.progress(0, text="Initializing matching engine...")

        all_results = []
        total_jobs = len(jobs_data)

        for idx, job in enumerate(jobs_data, 1):
            progress_bar.progress(
                int((idx / total_jobs) * 90),
                text=f"Evaluating Job {idx}/{total_jobs}: '{job['title']}'..."
            )
            match_res = calculate_match(resume_text, job["description"])
            all_results.append({
                "id": job["id"],
                "title": job["title"],
                "description": job["description"],
                "final_score": match_res["final_score"],
                "keyword_score": match_res["keyword_score"],
                "semantic_score": match_res["semantic_score"],
                "missing_keywords": match_res["missing_keywords"]
            })

        progress_bar.progress(100, text="Finalizing rankings...")
        time.sleep(0.3)
        progress_bar.empty()
        progress_slot.empty()

        all_results.sort(key=lambda x: x["final_score"], reverse=True)
        st.session_state["comparison_results"] = all_results
        st.session_state["active_resume_text"] = resume_text

# ---------------------------------------------------------
# Section 3: Ranked Job Results & Detailed Drill-Down
# ---------------------------------------------------------
if "comparison_results" in st.session_state and st.session_state["comparison_results"]:
    results = st.session_state["comparison_results"]
    active_resume = st.session_state.get("active_resume_text", resume_text)

    st.markdown("---")
    st.subheader("3. Ranked Job Matches")
    st.caption("Roles sorted by overall compatibility so you know where your resume has the strongest match.")

    # Ranked Table
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
            "Keyword Match": f"{res['keyword_score']}%",
            "Semantic Match": semantic_val,
            "Top Missing Keywords": missing_preview,
            "Recommendation": rec
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
        format_func=lambda i: job_labels[i]
    )

    selected_job = results[selected_index]
    sel_score = selected_job["final_score"]

    # Visual Score Progress Header
    st.markdown(f"### Detailed Analysis for: **{selected_job['title']}**")

    # Match Progress Bar
    progress_color_label = "Strong Match" if sel_score >= 70 else ("Moderate Match" if sel_score >= 45 else "Needs Improvement")
    st.progress(min(1.0, max(0.0, sel_score / 100.0)), text=f"Overall Score: {sel_score}% ({progress_color_label})")

    # Score Metrics Breakdown
    if selected_job["semantic_score"] is not None:
        c1, c2, c3 = st.columns(3)
        c1.metric("Overall Match", f"{sel_score}%")
        c2.metric("Keyword Match (TF-IDF)", f"{selected_job['keyword_score']}%")
        c3.metric("Semantic Match (AI)", f"{selected_job['semantic_score']}%")
        st.caption("💡 **Keyword Match** measures exact word overlap. **Semantic Match** uses AI sentence embeddings to recognize matching experience even when phrased differently.")
    else:
        st.metric("Overall Match (Keyword Fallback)", f"{sel_score}%")
        st.info("ℹ️ Semantic AI model unavailable; score was calculated using keyword matching.")

    st.write("")

    # -----------------------------------------------------
    # ATS-Friendliness Checks
    # -----------------------------------------------------
    with st.expander("🛡️ ATS-Friendliness Checks & Action Items", expanded=True):
        ats_results = run_ats_checks(active_resume)
        passed_count = sum(1 for c in ats_results if c["passed"])
        total_checks = len(ats_results)

        # ATS Readiness Progress
        readiness_pct = int((passed_count / total_checks) * 100) if total_checks > 0 else 0
        st.progress(readiness_pct / 100.0, text=f"ATS Readiness Score: {passed_count}/{total_checks} Checks Passed ({readiness_pct}%)")

        action_items = []
        for check in ats_results:
            is_pass = check["passed"]
            icon = "✅" if is_pass else "❌"
            badge = ":green[**PASS**]" if is_pass else ":red[**FAIL**]"
            st.markdown(f"{icon} **{check['name']}** &mdash; {badge}")
            st.caption(check["tip"])
            if not is_pass:
                action_items.append((check["name"], check["tip"]))

        st.markdown("#### 📋 Prioritized Action Items:")
        if action_items:
            for idx, (name, tip) in enumerate(action_items, 1):
                st.markdown(f"**{idx}. {name}:** {tip}")
        else:
            st.success("🎉 All ATS formatting criteria passed cleanly!")

    # -----------------------------------------------------
    # Experience Bullet Points Analysis
    # -----------------------------------------------------
    with st.expander("✍️ Experience Bullet Points Analysis", expanded=True):
        bullet_data = analyze_bullets(active_resume)
        tot_b = bullet_data["total_bullets"]
        flag_b = bullet_data["flagged_count"]

        if tot_b == 0:
            st.info("No distinct experience bullet points detected in the resume.")
        else:
            col_b1, col_b2 = st.columns(2)
            col_b1.metric("Bullets Analyzed", tot_b)
            col_b2.metric("Bullets Needing Refinement", flag_b)

            if flag_b == 0:
                st.success("Great job! All analyzed bullet points start with strong action verbs and include metrics.")
            else:
                st.write("Review these flagged bullets to strengthen your achievements:")
                for item in bullet_data["results"]:
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

            # Reference Action Verbs Dictionary
            with st.expander("📖 Reference List: Strong Action Verbs"):
                st.caption("Never invent facts. Use these strong verbs to accurately describe your accomplishments:")
                for cat, verbs in bullet_data["recommended_verbs"].items():
                    title = cat.replace("_", " ").title()
                    st.markdown(f"**{title}:** " + ", ".join([f"`{v}`" for v in verbs]))

    # -----------------------------------------------------
    # Missing Skills & Placement Guidance
    # -----------------------------------------------------
    missing_keywords = selected_job["missing_keywords"]
    with st.expander(f"🔑 Missing Skills & How-to-Add Guide ({len(missing_keywords)} skills)", expanded=True):
        if missing_keywords:
            st.warning(
                "⚠️ **Resume Integrity Rule:** Only add skills you actually have! "
                "Never invent experience or list tools you cannot discuss in an interview."
            )

            # Display quick chips
            st.markdown(" ".join([f"`{k}`" for k in missing_keywords]))
            st.write("")

            skill_advice = generate_skill_advice(missing_keywords)
            for adv in skill_advice:
                with st.expander(f"📌 **{adv['skill'].title()}** — Recommended Section: *{adv['section']}*"):
                    st.markdown(f"**Where it belongs:** `{adv['section']}`")
                    st.markdown(f"**If you have this skill:** {adv['how_to_add']}")
                    st.markdown(f"**If you don't have it yet:** {adv['how_to_learn']}")
        else:
            st.success(f"No key keywords from '{selected_job['title']}' are missing in your resume!")

    # -----------------------------------------------------
    # Interview Preparation Section (8 Likely Questions)
    # -----------------------------------------------------
    with st.expander(f"🎯 Interview Preparation: {selected_job['title']} (8 Questions)", expanded=True):
        st.caption("Tailored interview questions based on job description requirements and your resume gaps.")
        interview_data = generate_interview_questions(selected_job["description"], active_resume, missing_keywords)

        tab_t, tab_b, tab_g = st.tabs([
            f"🛠️ Technical ({len(interview_data['technical'])})",
            f"🤝 Behavioral ({len(interview_data['behavioral'])})",
            f"🎯 Gap-Related ({len(interview_data['gap_related'])})"
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
