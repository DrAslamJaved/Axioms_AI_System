import json
import os
from urllib.parse import urlencode

import requests
import streamlit as st

API_URL = os.getenv("AXIOMS_API_URL", "http://api:8000")

st.set_page_config(page_title="Axioms AI System", page_icon="⚙️")
st.title("Axioms AI System")
st.caption("Human-governed agentic research and teaching assistant.")

# --- Sidebar: authentication and system posture ---

with st.sidebar:
    st.header("Authentication")
    api_key = st.text_input("API key", type="password", help="Set AXIOMS_API_KEY or AXIOMS_API_KEYS on the server.")
    approver_name = st.text_input(
        "Approver name",
        value="Dr Aslam",
        help="Used for approval identity in single-key mode. In named-key mode this is derived from the key.",
    )
    st.divider()
    st.caption("System posture")
    try:
        health = requests.get(f"{API_URL}/health", timeout=10).json()
        st.write(f"Auth: **{health.get('auth', 'unknown')}**")
        st.write(f"LLM: **{health.get('llm_provider', 'unknown')}**")
        st.write(f"Approval: **{health.get('approval_mode', 'unknown')}**")
    except Exception:  # noqa: BLE001
        st.warning("Cannot reach the API server.")


def _headers() -> dict[str, str]:
    """Build request headers, including the API key when configured."""
    if api_key:
        return {"X-API-Key": api_key}
    return {}


def _post(url: str, payload: dict, *, timeout: int = 30) -> requests.Response:
    return requests.post(url, json=payload, headers=_headers(), timeout=timeout)


def _get(url: str, *, timeout: int = 20) -> requests.Response:
    return requests.get(url, headers=_headers(), timeout=timeout)


def _task_queue_url(*, status: str, limit: int, cursor: str | None = None) -> str:
    """Build a bounded read-only work-queue request from non-content metadata."""
    parameters: dict[str, str | int] = {"limit": limit}
    if status != "all":
        parameters["status"] = status
    if cursor is not None:
        parameters["cursor"] = cursor
    return f"{API_URL}/tasks?{urlencode(parameters)}"


# --- System readiness ---

with st.expander("System integration readiness", expanded=False):
    try:
        readiness_response = _get(f"{API_URL}/system/readiness")
        readiness_response.raise_for_status()
        readiness = readiness_response.json()
        st.write(f"Implemented specialist agents: {readiness['specialist_agent_count']}")
        st.dataframe(
            [
                {"Component": item["name"], "State": item["state"], "Detail": item["detail"]}
                for item in readiness["components"]
            ],
            hide_index=True,
            use_container_width=True,
        )
    except Exception as error:  # noqa: BLE001
        st.error(f"Could not load readiness report: {error}")

# --- Manual task status inspector ---

with st.expander("Local operations snapshot", expanded=False):
    st.caption(
        "Manual, aggregate-only local health view. It does not poll, list individual jobs, execute work, "
        "or perform external actions."
    )
    if st.button("Refresh local operations snapshot"):
        response = _get(f"{API_URL}/operations/summary")
        if response.ok:
            st.session_state["operations_snapshot"] = response.json()
        else:
            st.session_state.pop("operations_snapshot", None)
            st.error(f"Error {response.status_code}: {response.text}")
    operations_snapshot = st.session_state.get("operations_snapshot")
    if operations_snapshot:
        task_counts = operations_snapshot["tasks"]
        dispatch = operations_snapshot["dispatch"]
        dispatch_counts = dispatch["status_counts"]
        summary_columns = st.columns(3)
        summary_columns[0].metric("Tracked tasks", sum(task_counts.values()))
        summary_columns[1].metric("Local dispatch jobs", sum(dispatch_counts.values()))
        summary_columns[2].metric("Active leases", dispatch["active_lease_count"])
        task_counts_column, dispatch_counts_column = st.columns(2)
        with task_counts_column:
            st.caption("Task lifecycle counts")
            st.dataframe(
                [{"Lifecycle": status, "Tasks": count} for status, count in task_counts.items()],
                hide_index=True,
                use_container_width=True,
            )
        with dispatch_counts_column:
            st.caption("Local dispatch counts")
            st.dataframe(
                [{"Lifecycle": status, "Jobs": count} for status, count in dispatch_counts.items()],
                hide_index=True,
                use_container_width=True,
            )
        st.caption(f"Observed locally at {dispatch['observed_at']}.")
        if dispatch["expired_lease_count"] or dispatch["missing_lease_count"]:
            st.warning(
                "A local worker lease needs human review. This snapshot does not reclaim work or modify dispatch state."
            )
        st.caption("External actions remain disabled; final human review remains required.")

# --- Manual task status inspector ---

with st.expander("Task status inspector", expanded=False):
    st.caption(
        "Manual, metadata-only lookup. It does not start work, refresh automatically, or show task content."
    )
    with st.form("task-status-inspector"):
        status_task_id = st.text_input("Task ID", placeholder="task_…")
        status_submitted = st.form_submit_button("Refresh task status")
    if status_submitted:
        if not status_task_id.strip():
            st.warning("Enter a task ID to inspect its status.")
        else:
            response = _get(f"{API_URL}/tasks/{status_task_id.strip()}/status")
            if response.ok:
                st.session_state["task_status"] = response.json()
            else:
                st.session_state.pop("task_status", None)
                st.error(f"Error {response.status_code}: {response.text}")
    task_status = st.session_state.get("task_status")
    if task_status:
        status_columns = st.columns(3)
        status_columns[0].metric("Lifecycle", task_status["status"])
        status_columns[1].metric("Risk tier", task_status["risk_tier"] or "unknown")
        status_columns[2].metric("Drafts ready", task_status["deliverable_count"])
        if task_status["final_review_required"]:
            st.warning("Final human review is required before any release or external delivery.")
        else:
            st.caption("No final-review action is available from this inspector.")

# --- Manual agent trace inspector ---

with st.expander("Agent trace inspector (approver)", expanded=False):
    st.caption(
        "Manual, review-only lifecycle trace. Named-key deployments require an approver or administrator key; "
        "events exclude task goals, draft text, document metadata, preference values, reviewer notes, and summaries."
    )
    with st.form("agent-trace-inspector"):
        trace_task_id = st.text_input("Task ID", placeholder="task_…", key="agent-trace-task-id")
        trace_submitted = st.form_submit_button("Refresh agent trace")
    if trace_submitted:
        if not trace_task_id.strip():
            st.warning("Enter a task ID to inspect its lifecycle trace.")
        else:
            response = _get(f"{API_URL}/tasks/{trace_task_id.strip()}/trace")
            if response.ok:
                st.session_state["agent_trace"] = response.json()
            else:
                st.session_state.pop("agent_trace", None)
                st.error(f"Error {response.status_code}: {response.text}")
    agent_trace = st.session_state.get("agent_trace")
    if agent_trace:
        trace_columns = st.columns(3)
        trace_columns[0].metric("Lifecycle", agent_trace["status"])
        trace_columns[1].metric("Risk tier", agent_trace["risk_tier"] or "unknown")
        trace_columns[2].metric("Recorded events", len(agent_trace["events"]))
        st.dataframe(
            [
                {
                    "Recorded at": event["created_at"],
                    "Event": event["kind"],
                    "Agent": event["agent"] or "Axioms Core",
                }
                for event in agent_trace["events"]
            ],
            hide_index=True,
            use_container_width=True,
        )
        st.caption("This inspector is read-only and provides no approval, execution, scheduling, or release controls.")

# --- Manual provider usage summary ---

with st.expander("Local provider usage summary", expanded=False):
    st.caption(
        "Manual, aggregate-only lookup. Counts are provider-reported tokens, not cost or billing estimates."
    )
    if st.button("Refresh local usage summary"):
        response = _get(f"{API_URL}/usage/summary")
        if response.ok:
            st.session_state["usage_summary"] = response.json()
        else:
            st.session_state.pop("usage_summary", None)
            st.error(f"Error {response.status_code}: {response.text}")
    usage_summary = st.session_state.get("usage_summary")
    if usage_summary:
        usage_columns = st.columns(3)
        usage_columns[0].metric("Recorded completions", usage_summary["request_count"])
        usage_columns[1].metric("Input tokens", usage_summary["input_tokens"])
        usage_columns[2].metric("Output tokens", usage_summary["output_tokens"])
        if usage_summary["by_provider"]:
            st.dataframe(
                [
                    {
                        "Provider": item["provider"],
                        "Model": item["model"],
                        "Completions": item["request_count"],
                        "Input tokens": item["input_tokens"],
                        "Output tokens": item["output_tokens"],
                    }
                    for item in usage_summary["by_provider"]
                ],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("No provider-reported token metadata has been recorded locally.")

# --- Manual task work queue ---

with st.expander("Task work queue", expanded=False):
    st.caption(
        "Manual, metadata-only queue. It does not refresh automatically or reveal task goals, drafts, "
        "preferences, document metadata, or reviewer notes."
    )
    with st.form("task-work-queue"):
        queue_status = st.selectbox(
            "Lifecycle filter",
            [
                "all",
                "planned",
                "pending_approval",
                "approved",
                "running",
                "cancellation_requested",
                "cancelled",
                "awaiting_review",
                "completed",
                "failed",
                "rejected",
            ],
        )
        queue_limit = st.selectbox("Maximum tasks", [10, 25, 50, 100], index=1)
        queue_submitted = st.form_submit_button("Refresh task work queue")
    if queue_submitted:
        response = _get(_task_queue_url(status=queue_status, limit=queue_limit))
        if response.ok:
            task_work_queue = response.json()
            st.session_state["task_work_queue"] = task_work_queue
            st.session_state["task_work_queue_pages"] = [task_work_queue]
            st.session_state["task_work_queue_filters"] = {
                "status": queue_status,
                "limit": queue_limit,
            }
            st.session_state["task_work_queue_page"] = 1
        else:
            st.session_state.pop("task_work_queue", None)
            st.error(f"Error {response.status_code}: {response.text}")
    task_work_queue = st.session_state.get("task_work_queue")
    if task_work_queue:
        task_work_queue_pages = st.session_state.get("task_work_queue_pages", [task_work_queue])
        task_work_queue_page = st.session_state.get("task_work_queue_page", 1)
        previous_page, next_page = st.columns(2)
        if previous_page.button(
            "Show previous queue page",
            key="task-work-queue-previous",
            disabled=task_work_queue_page == 1,
        ):
            task_work_queue_page -= 1
            task_work_queue = task_work_queue_pages[task_work_queue_page - 1]
            st.session_state["task_work_queue"] = task_work_queue
            st.session_state["task_work_queue_page"] = task_work_queue_page
        can_show_cached_page = task_work_queue_page < len(task_work_queue_pages)
        can_request_next_page = task_work_queue["next_cursor"] is not None
        if next_page.button(
            "Load next queue page",
            key="task-work-queue-next",
            disabled=not can_show_cached_page and not can_request_next_page,
        ):
            if can_show_cached_page:
                task_work_queue_page += 1
                task_work_queue = task_work_queue_pages[task_work_queue_page - 1]
                st.session_state["task_work_queue"] = task_work_queue
                st.session_state["task_work_queue_page"] = task_work_queue_page
            else:
                queue_filters = st.session_state.get("task_work_queue_filters")
                if not queue_filters:
                    st.error("Refresh the task work queue before requesting another page.")
                else:
                    response = _get(
                        _task_queue_url(
                            status=queue_filters["status"],
                            limit=queue_filters["limit"],
                            cursor=task_work_queue["next_cursor"],
                        )
                    )
                    if response.ok:
                        task_work_queue = response.json()
                        task_work_queue_pages.append(task_work_queue)
                        task_work_queue_page += 1
                        st.session_state["task_work_queue"] = task_work_queue
                        st.session_state["task_work_queue_pages"] = task_work_queue_pages
                        st.session_state["task_work_queue_page"] = task_work_queue_page
                    else:
                        st.error(f"Error {response.status_code}: {response.text}")
        queue_items = task_work_queue["items"]
        st.caption(
            f"Page {task_work_queue_page} of {len(task_work_queue_pages)} viewed locally — "
            "all navigation is loaded only on request."
        )
        if queue_items:
            st.dataframe(
                [
                    {
                        "Task ID": item["task_id"],
                        "Created": item["created_at"],
                        "Lifecycle": item["status"],
                        "Risk": item["risk_tier"] or "unknown",
                        "Graph": item["graph_version"] or "unknown",
                        "Revision of": item["revision_of"] or "—",
                        "Drafts": item["deliverable_count"],
                        "References": item["reference_document_count"],
                        "Preference scopes": ", ".join(item["preference_context_agents"]) or "—",
                    }
                    for item in queue_items
                ],
                hide_index=True,
                use_container_width=True,
            )
            if task_work_queue["next_cursor"]:
                st.caption("Another metadata-only page is available. Select “Load next queue page” to request it.")
        else:
            st.info("No tasks match the selected lifecycle filter.")

# --- Personal Knowledge Base governance ---

with st.expander("Personal Knowledge Base governance", expanded=False):
    st.caption("Feedback is recorded separately. Preferences become active only after explicit approval.")
    with st.form("personal-kb-proposal"):
        kb_category = st.selectbox(
            "Preference category",
            ["teaching_style", "research_voice", "content_brand", "recurring_template"],
        )
        kb_key = st.text_input("Preference key", value="explanation_sequence")
        kb_value = st.text_input("Preference value", value="intuition → formal development → application")
        kb_rationale = st.text_area("Rationale", value="Proposed explicitly by the owner for future drafts.")
        kb_submitted = st.form_submit_button("Create approval-required KB proposal")
    if kb_submitted:
        response = _post(
            f"{API_URL}/personal-kb/proposals",
            {
                "category": kb_category,
                "preference_key": kb_key,
                "preference_value": kb_value,
                "rationale": kb_rationale,
            },
        )
        if response.ok:
            st.session_state["kb_proposal"] = response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")
    proposal = st.session_state.get("kb_proposal")
    if proposal:
        st.info(f"Proposal {proposal['proposal_id']} is pending your approval.")
        approve, reject = st.columns(2)
        if approve.button("Approve KB proposal"):
            response = _post(
                f"{API_URL}/personal-kb/proposals/{proposal['proposal_id']}/decision",
                {"decision": "approve", "note": f"Approved by {approver_name} through review UI."},
            )
            if response.ok:
                st.session_state["kb_proposal"] = response.json()
                st.rerun()
            else:
                st.error(f"Error {response.status_code}: {response.text}")
        if reject.button("Reject KB proposal"):
            response = _post(
                f"{API_URL}/personal-kb/proposals/{proposal['proposal_id']}/decision",
                {"decision": "reject", "note": f"Rejected by {approver_name} through review UI."},
            )
            if response.ok:
                st.session_state["kb_proposal"] = response.json()
                st.rerun()
            else:
                st.error(f"Error {response.status_code}: {response.text}")

# --- Lecture plan ---

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
        response = _post(f"{API_URL}/lecture-plans", payload)
        if response.ok:
            st.session_state["lecture_plan"] = response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")

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

# --- Writing draft ---

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
        response = _post(f"{API_URL}/writing-drafts", payload)
        if response.ok:
            st.session_state["writing_draft"] = response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")

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

# --- Research brief (deterministic) ---

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
            response = _post(
                f"{API_URL}/research-briefs",
                {"research_question": research_question, "scope": research_scope, "sources": sources},
            )
            if response.ok:
                st.session_state["research_brief"] = response.json()
            else:
                st.error(f"Error {response.status_code}: {response.text}")

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

# --- Agentic research brief (NEW) ---

with st.expander("Run the agentic research agent", expanded=True):
    st.caption(
        "Tool-using agent: verifies DOIs against Crossref, synthesises verified claims "
        "through a constrained LLM prompt, and runs an AutoEval guardrail. Works with "
        "or without an LLM configured (synthesis is skipped when disabled)."
    )
    with st.form("agentic-research"):
        ag_question = st.text_area(
            "Research question",
            value="How can fuzzy similarity measures support drug-drug interaction prediction?",
        )
        ag_scope = st.text_area(
            "Scope",
            value="Map methods, datasets, metrics, and limitations using verified source records.",
        )
        ag_sources_json = st.text_area(
            "Evidence sources (JSON array — same format as the deterministic brief)",
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
    "verification_evidence": "Author confirmed the metadata and claim."
  }
]''',
            height=250,
        )
        ag_submitted = st.form_submit_button("Run agentic research brief")

    if ag_submitted:
        try:
            ag_sources = json.loads(ag_sources_json)
        except json.JSONDecodeError as error:
            st.error(f"The source JSON is invalid: {error.msg}")
        else:
            with st.spinner("Running agentic research loop (Crossref + optional synthesis)..."):
                response = _post(
                    f"{API_URL}/research-briefs/agentic",
                    {"research_question": ag_question, "scope": ag_scope, "sources": ag_sources},
                    timeout=60,
                )
            if response.ok:
                st.session_state["agentic_result"] = response.json()
            else:
                st.error(f"Error {response.status_code}: {response.text}")

agentic = st.session_state.get("agentic_result")
if agentic:
    st.subheader("Agentic research result")
    st.caption("Draft for human review — not a published conclusion.")

    if agentic.get("discrepancies"):
        st.warning("**Discrepancies detected**")
        for item in agentic["discrepancies"]:
            st.write(f"⚠️ {item}")

    if agentic.get("synthesis"):
        st.markdown("**Constrained synthesis**")
        st.write(agentic["synthesis"])
    else:
        st.info("No synthesis produced (LLM may be disabled, or no claim-verified sources).")

    if agentic.get("autoeval"):
        ae = agentic["autoeval"]
        st.metric("AutoEval grounding", f"{ae['quality_signal_percent']}%")
        if ae.get("missing_required_elements"):
            st.warning(f"Uncited verified sources: {', '.join(ae['missing_required_elements'])}")

    st.markdown("**Agent trace**")
    st.dataframe(
        [
            {"Step": item["kind"], "Summary": item["summary"], "Detail": item["detail"]}
            for item in agentic.get("agent_trace", [])
        ],
        hide_index=True,
        use_container_width=True,
    )

    st.markdown("**Source audit (from deterministic brief)**")
    if agentic.get("brief", {}).get("source_audit"):
        st.dataframe(
            [
                {
                    "Source": item["source_id"],
                    "Verification": item["verification_status"],
                    "Eligible": item["synthesis_eligible"],
                    "Finding": item["finding"],
                }
                for item in agentic["brief"]["source_audit"]
            ],
            hide_index=True,
            use_container_width=True,
        )

# --- Assessment blueprint ---

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
        response = _post(f"{API_URL}/assessment-blueprints", payload)
        if response.ok:
            st.session_state["assessment_blueprint"] = response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")

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

# --- Content package ---

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
        response = _post(f"{API_URL}/content-packages", payload)
        if response.ok:
            st.session_state["content_package"] = response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")

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

# --- Social media package ---

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
        response = _post(f"{API_URL}/social-media-packages", payload)
        if response.ok:
            st.session_state["social_media_package"] = response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")

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

# --- Portfolio package ---

with st.expander("Create a STEM AI portfolio package", expanded=True):
    with st.form("portfolio-package"):
        portfolio_title = st.text_input(
            "Portfolio project title", value="Agentic Spectral Graph Theory Learning Toolkit"
        )
        portfolio_summary = st.text_area(
            "Research summary",
            value="A reproducible educational toolkit that demonstrates spectral graph theory concepts.",
        )
        portfolio_audience = st.selectbox(
            "Portfolio audience", ["academic", "industry", "academic_and_industry"]
        )
        portfolio_visibility = st.selectbox("Proposed repository visibility", ["private", "public"])
        portfolio_evidence = st.text_area(
            "Verified evidence (one claim | source reference per line)",
            value="The project uses instructor-approved lecture notes. | Internal course-material review record",
        )
        portfolio_submitted = st.form_submit_button("Build reviewed portfolio package")

    if portfolio_submitted:
        evidence_items = []
        for index, line in enumerate(portfolio_evidence.splitlines(), start=1):
            claim, separator, source = line.partition("|")
            if claim.strip() and separator and source.strip():
                evidence_items.append(
                    {
                        "evidence_id": f"E{index:02d}",
                        "claim": claim.strip(),
                        "source_reference": source.strip(),
                        "verified": True,
                    }
                )
        payload = {
            "project_title": portfolio_title,
            "research_summary": portfolio_summary,
            "target_audience": portfolio_audience,
            "repository_visibility": portfolio_visibility,
            "verified_evidence": evidence_items,
        }
        response = _post(f"{API_URL}/portfolio-packages", payload)
        if response.ok:
            st.session_state["portfolio_package"] = response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")

portfolio = st.session_state.get("portfolio_package")
if portfolio:
    st.subheader(f"Portfolio package: {portfolio['request']['project_title']}")
    st.caption("Review only. This app cannot create, change, push to, or publish a GitHub repository.")
    st.markdown("**Repository structure**")
    st.dataframe(
        [{"Path": item["path"], "Purpose": item["purpose"]} for item in portfolio["repository_structure"]],
        hide_index=True,
        use_container_width=True,
    )
    st.markdown("**Reproducibility checklist**")
    for item in portfolio["reproducibility_checklist"]:
        st.checkbox(item, key=f"portfolio_{item}")

# --- AutoEval report ---

with st.expander("Create an AutoEval review report", expanded=True):
    with st.form("autoeval-report"):
        evaluated_agent = st.selectbox(
            "Evaluated agent",
            [
                "lecture_design",
                "writing_communication",
                "research",
                "assessment_design",
                "content_creation",
                "social_media",
                "stem_ai_portfolio",
            ],
        )
        evaluation_title = st.text_input("Deliverable title", value="Spectral Graph Theory lecture plan")
        evaluation_artifact = st.text_area(
            "Artifact text to check",
            value="This lecture plan includes intuition, a formal definition, and a worked example.",
        )
        required_elements = st.text_area(
            "Required text markers (one per line)",
            value="intuition\nformal definition\nworked example",
        )
        evidence_markers = st.text_area("Evidence markers (one per line, optional)")
        public_facing = st.checkbox("This deliverable is public-facing")
        sensitive_data = st.checkbox("Sensitive data is declared in the artifact")
        autoeval_submitted = st.form_submit_button("Run deterministic review checks")

    if autoeval_submitted:
        payload = {
            "evaluated_agent": evaluated_agent,
            "deliverable_title": evaluation_title,
            "artifact_text": evaluation_artifact,
            "required_elements": [item.strip() for item in required_elements.splitlines() if item.strip()],
            "evidence_markers": [item.strip() for item in evidence_markers.splitlines() if item.strip()],
            "public_facing": public_facing,
            "declared_sensitive_data": sensitive_data,
        }
        response = _post(f"{API_URL}/autoeval-reports", payload)
        if response.ok:
            st.session_state["autoeval_report"] = response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")

autoeval = st.session_state.get("autoeval_report")
if autoeval:
    st.subheader(f"AutoEval report: {autoeval['request']['deliverable_title']}")
    st.caption("Deterministic review signals only; human review remains mandatory.")
    st.metric("Quality signal", f"{autoeval['quality_signal_percent']}%")
    st.dataframe(
        [
            {"Check": item["name"], "Status": item["status"], "Detail": item["detail"]}
            for item in autoeval["checks"]
        ],
        hide_index=True,
        use_container_width=True,
    )
    st.warning(autoeval["review_boundary"])

# --- Task creation and approval ---

with st.form("new-task"):
    goal = st.text_area("What would you like to prepare?")
    audience = st.text_input("Audience", value="unspecified")
    deadline = st.text_input("Deadline (optional)")
    external = st.checkbox("This would be delivered externally")
    submitted = st.form_submit_button("Create task plan")

if submitted:
    response = _post(
        f"{API_URL}/tasks",
        {"goal": goal, "audience": audience, "deadline": deadline or None, "external_delivery": external},
    )
    if response.ok:
        st.session_state["task"] = response.json()
    else:
        st.error(f"Error {response.status_code}: {response.text}")

task = st.session_state.get("task")
if task:
    st.subheader(f"Task {task['task_id']}")
    risk = task.get("risk_tier", "low")
    if risk == "high":
        st.error(f"Status: {task['status']} · Risk: **{risk.upper()}** (blocking)")
    elif risk == "elevated":
        st.warning(f"Status: {task['status']} · Risk: **{risk.upper()}**")
    else:
        st.info(f"Status: {task['status']} · Risk: {risk}")
    if task.get("policy_reason"):
        st.caption(task["policy_reason"])
    for deliverable in task["deliverables"]:
        with st.expander(deliverable["title"], expanded=True):
            st.markdown(deliverable["content"])
    if task.get("agent_trace"):
        with st.expander("Auditable agent trace"):
            st.dataframe(task["agent_trace"], hide_index=True, use_container_width=True)
    col1, col2, col3 = st.columns(3)
    override = False
    if risk == "high":
        override = st.checkbox(
            "I acknowledge the data-governance risk and override the block",
            key="override_blocking",
        )
    if task["status"] in {"planned", "pending_approval"} and col1.button("Approve execution"):
        response = _post(
            f"{API_URL}/tasks/{task['task_id']}/approval",
            {
                "decision": "approve",
                "approved_by": approver_name,
                "note": f"Execution approved by {approver_name} through review UI.",
                "override_blocking": override,
            },
        )
        if response.ok:
            st.session_state["task"] = response.json()
            st.rerun()
        else:
            st.error(f"Error {response.status_code}: {response.text}")
    if task["status"] == "approved" and col2.button("Run approved task"):
        response = _post(f"{API_URL}/tasks/{task['task_id']}/execute", {})
        if response.ok:
            st.session_state["task"] = response.json()
            st.rerun()
        else:
            st.error(f"Error {response.status_code}: {response.text}")
    if task["status"] == "awaiting_review" and col1.button("Accept reviewed drafts"):
        response = _post(
            f"{API_URL}/tasks/{task['task_id']}/approval",
            {
                "decision": "approve",
                "approved_by": approver_name,
                "note": f"Final review accepted by {approver_name} through review UI.",
            },
        )
        if response.ok:
            st.session_state["task"] = response.json()
            st.rerun()
        else:
            st.error(f"Error {response.status_code}: {response.text}")
    if task["status"] in {"planned", "pending_approval", "awaiting_review"} and col3.button("Reject task/drafts"):
        response = _post(
            f"{API_URL}/tasks/{task['task_id']}/approval",
            {
                "decision": "reject",
                "approved_by": approver_name,
                "note": f"Rejected by {approver_name} through review UI.",
            },
        )
        if response.ok:
            st.session_state["task"] = response.json()
            st.rerun()
        else:
            st.error(f"Error {response.status_code}: {response.text}")
