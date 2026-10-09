"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusBadge, RiskBadge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Textarea } from "@/components/ui/Input";
import { useAuth } from "@/contexts/auth";
import { ApiError } from "@/lib/api";
import type { TaskRecord } from "@/lib/types";

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { api, connected, approverName } = useAuth();
  const [task, setTask] = useState<TaskRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showApproval, setShowApproval] = useState(false);
  const [approvalNote, setApprovalNote] = useState("");
  const [actionLoading, setActionLoading] = useState("");

  const loadTask = () => {
    if (!connected || !id) return;
    setLoading(true);
    api
      .getTask(id)
      .then(setTask)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load task"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadTask();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected, id]);

  const handleApproval = async (decision: "approve" | "reject") => {
    setActionLoading(decision);
    try {
      await api.approveTask(id, {
        decision,
        approved_by: approverName || "web_user",
        note: approvalNote || undefined,
      });
      setShowApproval(false);
      setApprovalNote("");
      loadTask();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Approval failed");
    } finally {
      setActionLoading("");
    }
  };

  const handleExecute = async () => {
    setActionLoading("execute");
    try {
      await api.executeTask(id);
      loadTask();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Execution failed");
    } finally {
      setActionLoading("");
    }
  };

  const handleCancel = async () => {
    setActionLoading("cancel");
    try {
      await api.cancelTask(id, approverName || "web_user");
      loadTask();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Cancellation failed");
    } finally {
      setActionLoading("");
    }
  };

  if (!connected) {
    return (
      <div className="pt-20 text-center text-sm text-slate-500">
        Connect to the API in Settings.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="pt-20 text-center text-sm text-slate-500">
        Loading task...
      </div>
    );
  }

  if (!task) {
    return (
      <div className="pt-20 text-center text-sm text-slate-500">
        {error || "Task not found"}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Back button */}
      <button
        onClick={() => router.push("/tasks")}
        className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        Back to Tasks
      </button>

      {/* Error banner */}
      {error && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Task header */}
      <Card>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-slate-900">
              {task.request.goal}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <StatusBadge status={task.status} />
              <RiskBadge tier={task.risk_tier} />
              <span className="text-xs text-slate-500 font-mono">
                {task.task_id}
              </span>
              <span className="text-xs text-slate-500">
                Created {new Date(task.created_at).toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        {/* Metadata */}
        <div className="mt-4 grid grid-cols-2 gap-4 border-t border-slate-100 pt-4 text-sm">
          <div>
            <span className="text-slate-500">Audience:</span>{" "}
            <span className="font-medium text-slate-700">{task.request.audience}</span>
          </div>
          {task.request.deadline && (
            <div>
              <span className="text-slate-500">Deadline:</span>{" "}
              <span className="font-medium text-slate-700">{task.request.deadline}</span>
            </div>
          )}
          {task.approved_by && (
            <div>
              <span className="text-slate-500">Approved by:</span>{" "}
              <span className="font-medium text-slate-700">{task.approved_by}</span>
            </div>
          )}
          {task.request.constraints.length > 0 && (
            <div className="col-span-2">
              <span className="text-slate-500">Constraints:</span>{" "}
              <span className="font-medium text-slate-700">
                {task.request.constraints.join(", ")}
              </span>
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="mt-4 flex flex-wrap gap-3 border-t border-slate-100 pt-4">
          {task.status === "pending_approval" && (
            <Button onClick={() => setShowApproval(true)}>
              Review &amp; Approve
            </Button>
          )}
          {task.status === "approved" && (
            <Button
              onClick={handleExecute}
              loading={actionLoading === "execute"}
            >
              Execute Task
            </Button>
          )}
          {["planned", "pending_approval", "approved", "running"].includes(
            task.status
          ) && (
            <Button
              variant="danger"
              onClick={handleCancel}
              loading={actionLoading === "cancel"}
            >
              Cancel
            </Button>
          )}
        </div>
      </Card>

      {/* Subtasks */}
      {task.subtasks.length > 0 && (
        <Card>
          <CardTitle>Subtasks ({task.subtasks.length})</CardTitle>
          <div className="mt-4 space-y-3">
            {task.subtasks.map((st, i) => (
              <div
                key={i}
                className="rounded-lg border border-slate-200 p-4"
              >
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-medium text-slate-900">
                    {st.title}
                  </h4>
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600">
                    {st.agent.replace(/_/g, " ")}
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-600">
                  {st.instructions}
                </p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Deliverables */}
      {task.deliverables.length > 0 && (
        <Card>
          <CardTitle>Deliverables ({task.deliverables.length})</CardTitle>
          <div className="mt-4 space-y-4">
            {task.deliverables.map((d, i) => (
              <div
                key={i}
                className="rounded-lg border border-slate-200 p-4"
              >
                <div className="mb-2 flex items-center justify-between">
                  <h4 className="text-sm font-medium text-slate-900">
                    {d.title}
                  </h4>
                  <span className="text-xs text-slate-500">
                    by {d.agent.replace(/_/g, " ")}
                  </span>
                </div>
                <div className="max-h-96 overflow-y-auto rounded-md bg-slate-50 p-4">
                  <pre className="whitespace-pre-wrap text-sm text-slate-700">
                    {d.content}
                  </pre>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Agent trace */}
      {task.agent_trace.length > 0 && (
        <Card>
          <CardTitle>Activity Timeline</CardTitle>
          <div className="mt-4">
            <ol className="relative border-l border-slate-200 ml-3">
              {task.agent_trace.map((step, i) => (
                <li key={i} className="mb-4 ml-6">
                  <div className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border-2 border-white bg-axiom-500" />
                  <div className="text-sm">
                    <span className="font-medium text-slate-900">
                      {step.kind.replace(/_/g, " ")}
                    </span>
                    {step.agent && (
                      <span className="ml-2 text-xs text-slate-500">
                        ({step.agent.replace(/_/g, " ")})
                      </span>
                    )}
                    <p className="mt-0.5 text-slate-600">{step.summary}</p>
                    <time className="mt-0.5 block text-xs text-slate-400">
                      {new Date(step.created_at).toLocaleString()}
                    </time>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </Card>
      )}

      {/* Approval Modal */}
      <Modal
        open={showApproval}
        onClose={() => setShowApproval(false)}
        title="Review Task"
      >
        <div className="space-y-4">
          <div className="rounded-lg bg-slate-50 p-4 text-sm">
            <p className="font-medium text-slate-900">Goal:</p>
            <p className="mt-1 text-slate-700">{task.request.goal}</p>
          </div>
          <Textarea
            label="Note (optional)"
            placeholder="Add a note for the approval or rejection..."
            value={approvalNote}
            onChange={(e) => setApprovalNote(e.target.value)}
          />
          <div className="flex justify-end gap-3 pt-2">
            <Button
              variant="danger"
              onClick={() => handleApproval("reject")}
              loading={actionLoading === "reject"}
            >
              Reject
            </Button>
            <Button
              onClick={() => handleApproval("approve")}
              loading={actionLoading === "approve"}
            >
              Approve
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
