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
