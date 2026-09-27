import os

import requests
import streamlit as st

API_URL = os.getenv("AXIOMS_API_URL", "http://api:8000")

st.set_page_config(page_title="Axioms AI System", page_icon="⚙️")
st.title("Axioms AI System")
st.caption("Human-governed foundation MVP — drafts remain pending until you approve them.")

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

