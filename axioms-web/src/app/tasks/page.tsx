"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusBadge, RiskBadge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Input, Textarea } from "@/components/ui/Input";
import { useAuth } from "@/contexts/auth";
import type { TaskRecord, TaskStatus } from "@/lib/types";

const statusFilters: { label: string; value: TaskStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Pending Approval", value: "pending_approval" },
  { label: "Approved", value: "approved" },
  { label: "Running", value: "running" },
  { label: "Awaiting Review", value: "awaiting_review" },
  { label: "Completed", value: "completed" },
  { label: "Failed", value: "failed" },
];

export default function TasksPage() {
  const { api, connected } = useAuth();
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [filter, setFilter] = useState<TaskStatus | "all">("all");
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newTask, setNewTask] = useState({ goal: "", audience: "", deadline: "" });
  const [creating, setCreating] = useState(false);

  const loadTasks = () => {
    if (!connected) return;
    setLoading(true);
    const status = filter === "all" ? undefined : filter;
    api
      .listTasks(status, 50)
      .then((data) => setTasks(data.items ?? []))
      .catch(() => setTasks([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadTasks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected, filter]);

  const handleCreate = async () => {
    if (!newTask.goal.trim()) return;
    setCreating(true);
    try {
      await api.createTask({
        goal: newTask.goal,
        audience: newTask.audience || "unspecified",
        deadline: newTask.deadline || null,
      });
      setShowCreate(false);
      setNewTask({ goal: "", audience: "", deadline: "" });
      loadTasks();
    } catch {
      // Error handling
    } finally {
      setCreating(false);
    }
  };

  if (!connected) {
    return (
      <div className="pt-20 text-center text-sm text-slate-500">
        Connect to the API in Settings to view tasks.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Tasks</h1>
          <p className="mt-1 text-sm text-slate-500">
            Manage and review multi-agent tasks
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>New Task</Button>
      </div>

      {/* Status filter tabs */}
      <div className="flex gap-1 overflow-x-auto rounded-lg bg-slate-100 p-1">
        {statusFilters.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              filter === f.value
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Task list */}
      {loading ? (
        <Card>
          <p className="text-center text-sm text-slate-500">Loading tasks...</p>
        </Card>
      ) : tasks.length === 0 ? (
        <Card>
          <p className="text-center text-sm text-slate-500">
            No tasks found for this filter.
          </p>
        </Card>
      ) : (
        <Card padding={false}>
          <div className="divide-y divide-slate-100">
            {tasks.map((task) => (
              <Link
                key={task.task_id}
                href={`/tasks/${task.task_id}`}
                className="block px-6 py-4 transition-colors hover:bg-slate-50"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-900">
                      {task.request.goal}
                    </p>
                    <div className="mt-1.5 flex items-center gap-3 text-xs text-slate-500">
                      <span className="font-mono">{task.task_id}</span>
                      <span>
                        {new Date(task.created_at).toLocaleString()}
                      </span>
                      {task.request.audience !== "unspecified" && (
                        <span>Audience: {task.request.audience}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-2">
                    <RiskBadge tier={task.risk_tier} />
                    <StatusBadge status={task.status} />
                  </div>
                </div>
                {task.deliverables.length > 0 && (
                  <div className="mt-2 text-xs text-slate-500">
                    {task.deliverables.length} deliverable
                    {task.deliverables.length !== 1 ? "s" : ""}
                  </div>
                )}
              </Link>
            ))}
          </div>
        </Card>
      )}

      {/* Create Task Modal */}
      <Modal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        title="Create New Task"
      >
        <div className="space-y-4">
          <Textarea
            label="Goal"
            placeholder="Describe the task goal (min. 8 characters)..."
            value={newTask.goal}
            onChange={(e) =>
              setNewTask((t) => ({ ...t, goal: e.target.value }))
            }
          />
          <Input
            label="Audience"
            placeholder="Target audience (optional)"
            value={newTask.audience}
            onChange={(e) =>
              setNewTask((t) => ({ ...t, audience: e.target.value }))
            }
          />
          <Input
            label="Deadline"
            placeholder="e.g., 2025-03-15"
            value={newTask.deadline}
            onChange={(e) =>
              setNewTask((t) => ({ ...t, deadline: e.target.value }))
            }
          />
          <div className="flex justify-end gap-3 pt-2">
            <Button
              variant="secondary"
              onClick={() => setShowCreate(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              loading={creating}
              disabled={newTask.goal.length < 8}
            >
              Create Task
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
