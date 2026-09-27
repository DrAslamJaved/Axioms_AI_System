import json
import os

import requests
import streamlit as st

API_URL = os.getenv("AXIOMS_API_URL", "http://api:8000")

st.set_page_config(page_title="Axioms AI System", page_icon="⚙️")
st.title("Axioms AI System")
st.caption("Human-governed foundation MVP — drafts remain pending until you approve them.")

with st.expander("Create a structured lecture plan", expanded=True):
    with st.form("lecture-plan"):
        lecture_topic = st.text_input("Lecture topic", value="Spectral Graph Theory")
        lecture_level = st.selectbox("Course level", ["Undergraduate", "Graduate", "Faculty training"])
        lecture_duration = st.slider("Duration (minutes)", 30, 240, 75, step=5)
        lecture_audience = st.text_input("Learner profile", value="MS Mathematics, Year 1")
        prior_knowledge = st.text_input("Prior knowledge", value="Linear algebra and basic graph theory")
        outcomes = st.text_area(
            "Learning outcomes (one per line)",
            value="Explain the intuition behind spectral graph methods.\nApply graph matrices to a small example.\nInterpret a real-world use case.",
        )
        application = st.text_input("Application context", value="PageRank and network clustering")
        include_code = st.checkbox("Include a Python/NumPy activity", value=True)
        lecture_submitted = st.form_submit_button("Generate reviewed lecture plan")

    if lecture_submitted:
        payload = {
            "topic": lecture_topic,
            "course_level": lecture_level,
            "duration_minutes": lecture_duration,
            "audience": lecture_audience,
            "prior_knowledge": prior_knowledge,
            "learning_outcomes": [item.strip() for item in outcomes.splitlines() if item.strip()],
            "application_context": application or None,
            "include_computational_activity": include_code,
        }
        response = requests.post(f"{API_URL}/lecture-plans", json=payload, timeout=20)
        response.raise_for_status()
        st.session_state["lecture_plan"] = response.json()

plan = st.session_state.get("lecture_plan")
if plan:
    st.subheader(f"Lecture plan: {plan['request']['topic']}")
    st.caption(f"{sum(item['minutes'] for item in plan['sections'])} minutes · Review required before use")
    st.dataframe(
        [{"Minutes": item["minutes"], "Segment": item["title"], "Purpose": item["purpose"]} for item in plan["sections"]],
        hide_index=True,
        use_container_width=True,
    )
    st.markdown("**Guided practice**")
    st.write(plan["practice_activity"])
    st.markdown("**Instructor review checklist**")
    for item in plan["review_checklist"]:
        st.checkbox(item, key=f"review_{item}")

with st.expander("Create a structured writing draft", expanded=True):
    with st.form("writing-draft"):
        document_type = st.selectbox(
            "Document type",
            ["email", "report", "paper_section", "recommendation_letter", "grant_section", "public_article"],
        )
        writing_subject = st.text_input("Subject or working title", value="Research collaboration update")
        writing_audience = st.text_input("Audience", value="Academic collaborator")
        writing_purpose = st.text_area("Purpose", value="Provide a concise, evidence-backed update and agree the next step.")
        key_points = st.text_area("Key points (one per line)", value="State the current progress.\nExplain the proposed next step.")
        verified_facts = st.text_area("Verified facts (one per line)", value="The project materials have been reviewed by the author.")
        tone = st.text_input("Tone", value="clear, precise, approachable, and intellectually rigorous")
        draft_submitted = st.form_submit_button("Generate reviewed writing draft")

    if draft_submitted:
        payload = {
            "document_type": document_type,
            "subject": writing_subject,
            "audience": writing_audience,
            "purpose": writing_purpose,
            "key_points": [item.strip() for item in key_points.splitlines() if item.strip()],
            "verified_facts": [item.strip() for item in verified_facts.splitlines() if item.strip()],
            "tone": tone,
        }
        response = requests.post(f"{API_URL}/writing-drafts", json=payload, timeout=20)
        response.raise_for_status()
        st.session_state["writing_draft"] = response.json()

draft = st.session_state.get("writing_draft")
if draft:
    st.subheader(f"Writing draft: {draft['request']['subject']}")
    st.caption("Author review is required before any external delivery.")
    if draft["subject_line"]:
        st.markdown(f"**Suggested subject:** {draft['subject_line']}")
    for section in draft["sections"]:
        st.markdown(f"**{section['heading']}**")
        st.write(section["content"])
    st.markdown("**Evidence review before use**")
    for item in draft["evidence_checklist"]:
        st.checkbox(item, key=f"evidence_{item}")

with st.expander("Create an evidence-first research brief", expanded=True):
    with st.form("research-brief"):
        research_question = st.text_area(
            "Research question",
            value="How can fuzzy similarity measures support drug-drug interaction prediction?",
        )
        research_scope = st.text_area(
            "Scope",
            value="Map methods, datasets, metrics, limitations, and research gaps using author-entered source records.",
        )
        sources_json = st.text_area(
            "Evidence sources (JSON array)",
            value='''[
  {
    "source_id": "S01",
    "title": "Author-verified example record",
    "authors": ["Author"],
    "year": 2026,
    "publication_kind": "journal_article",
    "doi": "10.1000/example.doi",
    "peer_reviewed": true,
    "supported_claim": "Replace with an author-verified, source-linked claim.",
    "verification_status": "claim_verified",
    "verification_evidence": "Author checked the bibliographic metadata and claim against the source."
  }
]''',
            height=270,
        )
        research_submitted = st.form_submit_button("Build evidence-first research brief")

    if research_submitted:
        try:
            sources = json.loads(sources_json)
        except json.JSONDecodeError as error:
            st.error(f"The source JSON is invalid: {error.msg}")
        else:
            response = requests.post(
                f"{API_URL}/research-briefs",
                json={"research_question": research_question, "scope": research_scope, "sources": sources},
                timeout=20,
            )
            response.raise_for_status()
            st.session_state["research_brief"] = response.json()

brief = st.session_state.get("research_brief")
if brief:
    st.subheader("Evidence-first research brief")
    st.caption("Only claim-verified records are eligible for constrained synthesis.")
    st.dataframe(
        [
            {
                "Source": item["source_id"],
                "Verification": item["verification_status"],
                "Synthesis eligible": item["synthesis_eligible"],
                "Finding": item["finding"],
            }
            for item in brief["source_audit"]
        ],
        hide_index=True,
        use_container_width=True,
    )
    st.markdown("**Verification queue**")
    for item in brief["verification_queue"]:
        st.write(f"- {item}")

with st.expander("Create an instructor assessment blueprint", expanded=True):
    with st.form("assessment-blueprint"):
        assessment_topic = st.text_input("Assessment topic", value="Spectral Graph Theory")
        assessment_level = st.selectbox("Assessment course level", ["Undergraduate", "Graduate"])
        assessment_type = st.selectbox("Assessment type", ["quiz", "assignment", "class_activity", "midterm", "final"])
        assessment_duration = st.slider("Assessment duration (minutes)", 10, 240, 30, step=5)
        assessment_marks = st.number_input("Total marks", min_value=1, max_value=500, value=20)
        assessment_questions = st.slider("Question count", 1, 2 if assessment_type == "quiz" else 20, 2)
        outcomes = st.text_area(
            "Learning outcomes (one per line)",
            value="Explain the role of graph matrices.\nApply a spectral method to a small graph.",
        )
        source_scope = st.text_area(
            "Approved course-source scope",
            value="Instructor-approved lecture notes on graph matrices and spectral methods.",
        )
        assessment_submitted = st.form_submit_button("Build reviewed assessment blueprint")

    if assessment_submitted:
        outcome_items = [item.strip() for item in outcomes.splitlines() if item.strip()]
        payload = {
            "topic": assessment_topic,
            "course_level": assessment_level,
            "assessment_type": assessment_type,
            "duration_minutes": assessment_duration,
            "total_marks": assessment_marks,
            "question_count": assessment_questions,
            "learning_outcomes": [
                {
                    "outcome_id": f"LO{index + 1}",
                    "text": outcome,
                    "bloom_level": "understand" if index == 0 else "apply",
                }
                for index, outcome in enumerate(outcome_items)
            ],
            "approved_source_scope": source_scope,
        }
        response = requests.post(f"{API_URL}/assessment-blueprints", json=payload, timeout=20)
        response.raise_for_status()
        st.session_state["assessment_blueprint"] = response.json()

assessment = st.session_state.get("assessment_blueprint")
if assessment:
    st.subheader(f"Assessment blueprint: {assessment['request']['topic']}")
    st.caption("Instructor review is required. Student-facing materials contain no rubrics or solutions.")
    st.dataframe(
        [
            {
                "Question": item["number"],
                "Outcome": item["outcome_id"],
                "Bloom": item["bloom_level"],
                "Difficulty": item["difficulty"],
                "Marks": item["marks"],
            }
            for item in assessment["questions"]
        ],
        hide_index=True,
        use_container_width=True,
    )
    st.markdown("**AI-resilience review**")
    for item in assessment["ai_resilience_review"]:
        st.write(f"- {item}")

with st.expander("Create an educational content package", expanded=True):
    with st.form("content-package"):
        content_topic = st.text_input("Content topic", value="Spectral Graph Theory")
        content_format = st.selectbox("Content format", ["youtube_video", "course_module", "workshop"])
        content_audience = st.text_input("Content audience", value="Graduate mathematics students")
        content_duration = st.slider("Content duration (minutes)", 3, 240, 15, step=1)
        source_scope = st.text_area(
            "Approved source scope for content",
            value="Instructor-approved lecture notes on spectral graph theory.",
        )
        content_outcomes = st.text_area(
            "Content learning outcomes (one per line)",
            value="Explain the intuition behind spectral graph methods.\nInterpret a small worked example.",
        )
        language_mode = st.selectbox("Language mode", ["english", "urdu", "bilingual"])
        content_submitted = st.form_submit_button("Build reviewed content package")

    if content_submitted:
        payload = {
            "topic": content_topic,
            "format": content_format,
            "audience": content_audience,
            "duration_minutes": content_duration,
            "approved_source_scope": source_scope,
            "learning_outcomes": [item.strip() for item in content_outcomes.splitlines() if item.strip()],
            "language_mode": language_mode,
        }
        response = requests.post(f"{API_URL}/content-packages", json=payload, timeout=20)
        response.raise_for_status()
        st.session_state["content_package"] = response.json()

content = st.session_state.get("content_package")
if content:
    st.subheader(f"Content package: {content['request']['topic']}")
    st.caption("Public publication remains blocked pending author review.")
    st.markdown("**Title options**")
    for title in content["title_options"]:
        st.write(f"- {title}")
    st.dataframe(
        [{"Minutes": item["minutes"], "Segment": item["title"], "Purpose": item["purpose"]} for item in content["segments"]],
        hide_index=True,
        use_container_width=True,
    )
    st.markdown("**Accessibility checks**")
    for item in content["accessibility_checks"]:
        st.checkbox(item, key=f"access_{item}")

with st.expander("Create a reviewed social-media package", expanded=True):
    with st.form("social-media-package"):
        social_topic = st.text_input("Social-media topic", value="Spectral Graph Theory")
        social_audience = st.text_input("Social-media audience", value="Graduate mathematics students")
        social_platforms = st.multiselect(
            "Platforms",
            ["linkedin", "instagram", "x", "tiktok", "whatsapp"],
            default=["linkedin", "instagram"],
        )
        social_objective = st.selectbox("Objective", ["educate", "announce", "invite_discussion"])
        social_sources = st.text_area(
            "Approved source scope for social drafts",
            value="Instructor-approved lecture notes on spectral graph theory.",
        )
        social_facts = st.text_area(
            "Verified facts (one per line)",
            value="The material is based on instructor-approved lecture notes.",
        )
        social_weeks = st.slider("Proposed calendar length (weeks)", 1, 4, 4)
        social_submitted = st.form_submit_button("Build reviewed social-media package")

    if social_submitted:
        payload = {
            "topic": social_topic,
            "audience": social_audience,
            "platforms": social_platforms,
            "objective": social_objective,
            "approved_source_scope": social_sources,
            "verified_facts": [item.strip() for item in social_facts.splitlines() if item.strip()],
            "calendar_weeks": social_weeks,
        }
        response = requests.post(f"{API_URL}/social-media-packages", json=payload, timeout=20)
        response.raise_for_status()
        st.session_state["social_media_package"] = response.json()

social = st.session_state.get("social_media_package")
if social:
    st.subheader(f"Social-media package: {social['request']['topic']}")
    st.caption("Draft only. This app cannot schedule or publish to any social account.")
    for item in social["platform_drafts"]:
        st.markdown(f"**{item['platform'].title()} — {item['format']}**")
        st.write(item["headline"])
        st.code(item["draft_copy"], language=None)
    st.markdown("**Proposed calendar**")
    st.dataframe(
        [
            {
                "Week": item["week"],
                "Platform": item["platform"],
                "Purpose": item["purpose"],
                "Status": item["status"],
            }
            for item in social["proposed_calendar"]
        ],
        hide_index=True,
        use_container_width=True,
    )
    st.markdown("**Publication checks**")
    for item in social["publication_checks"]:
        st.checkbox(item, key=f"social_{item}")

with st.form("new-task"):
    goal = st.text_area("What would you like to prepare?")
    audience = st.text_input("Audience", value="unspecified")
    deadline = st.text_input("Deadline (optional)")
    external = st.checkbox("This would be delivered externally")
    submitted = st.form_submit_button("Create reviewed draft")

if submitted:
    response = requests.post(
        f"{API_URL}/tasks",
        json={"goal": goal, "audience": audience, "deadline": deadline or None, "external_delivery": external},
        timeout=20,
    )
    response.raise_for_status()
    st.session_state["task"] = response.json()

task = st.session_state.get("task")
if task:
    st.subheader(f"Task {task['task_id']}")
    st.info(f"Status: {task['status']}")
    for deliverable in task["deliverables"]:
        with st.expander(deliverable["title"], expanded=True):
            st.markdown(deliverable["content"])
    col1, col2 = st.columns(2)
    if col1.button("Approve drafts"):
        response = requests.post(
            f"{API_URL}/tasks/{task['task_id']}/approval",
            json={"decision": "approve", "note": "Approved by owner through review UI."},
            timeout=20,
        )
        response.raise_for_status()
        st.session_state["task"] = response.json()
        st.rerun()
    if col2.button("Reject drafts"):
        response = requests.post(
            f"{API_URL}/tasks/{task['task_id']}/approval",
            json={"decision": "reject", "note": "Rejected by owner through review UI."},
            timeout=20,
        )
        response.raise_for_status()
        st.session_state["task"] = response.json()
        st.rerun()
