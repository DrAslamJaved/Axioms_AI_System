"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardTitle, CardDescription } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/Badge";
import { useAuth } from "@/contexts/auth";
import {
  AGENT_DESCRIPTIONS,
  AGENT_DISPLAY_NAMES,
  type AgentName,
  type OperationsSummary,
  type TaskRecord,
  type TaskStatus,
} from "@/lib/types";

const agentCards: { key: AgentName; href: string }[] = [
  { key: "lecture_design", href: "/agents/lecture" },
  { key: "research", href: "/agents/research" },
  { key: "assessment_design", href: "/agents/assessment" },
  { key: "writing_communication", href: "/agents/writing" },
  { key: "content_creation", href: "/agents/content" },
  { key: "social_media", href: "/agents/social-media" },
  { key: "stem_ai_portfolio", href: "/agents/portfolio" },
  { key: "autoeval", href: "/agents/autoeval" },
];

const agentIcons: Record<string, string> = {
  lecture_design: "Lc",
  research: "Rs",
  assessment_design: "As",
  writing_communication: "Wr",
  content_creation: "Cn",
  social_media: "Sm",
  stem_ai_portfolio: "Pf",
  autoeval: "Ev",
};

const agentColors: Record<string, string> = {
  lecture_design: "bg-blue-600",
  research: "bg-emerald-600",
  assessment_design: "bg-violet-600",
  writing_communication: "bg-amber-600",
  content_creation: "bg-rose-600",
  social_media: "bg-sky-600",
  stem_ai_portfolio: "bg-teal-600",
  autoeval: "bg-orange-600",
};

export default function DashboardPage() {
  const { api, connected, apiKey } = useAuth();
  const [ops, setOps] = useState<OperationsSummary | null>(null);
  const [recentTasks, setRecentTasks] = useState<TaskRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!connected || !apiKey) {
      setLoading(false);
      return;
    }
    Promise.all([
      api.operationsSummary().catch(() => null),
      api.listTasks(undefined, 5).catch(() => ({ items: [] })),
    ]).then(([opsData, tasksData]) => {
      setOps(opsData as OperationsSummary | null);
      setRecentTasks((tasksData as { items: TaskRecord[] }).items ?? []);
      setLoading(false);
    });
  }, [api, connected, apiKey]);

  if (!connected) {
    return (
      <div className="mx-auto max-w-2xl pt-20 text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-axiom-100">
          <span className="text-2xl font-bold text-axiom-600">Ax</span>
        </div>
        <h1 className="text-2xl font-bold text-slate-900">
          Welcome to Axioms AI System
        </h1>
        <p className="mt-3 text-slate-600">
          Connect to your Axioms API to get started. Go to{" "}
          <Link
            href="/settings"
            className="font-medium text-axiom-600 hover:text-axiom-700"
          >
            Settings
          </Link>{" "}
          to configure your API key and backend URL.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          Overview of your Axioms AI multi-agent workspace
        </p>
      </div>

      {/* Stats row */}
      {ops && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            { label: "Total Tasks", value: ops.total_tasks, color: "text-slate-900" },
            {
              label: "Pending Approval",
              value: ops.by_status?.pending_approval ?? 0,
              color: "text-amber-600",
            },
            {
              label: "Running",
              value: ops.by_status?.running ?? 0,
              color: "text-indigo-600",
            },
            {
              label: "Completed",
              value: ops.by_status?.completed ?? 0,
              color: "text-emerald-600",
            },
          ].map((stat) => (
            <Card key={stat.label}>
              <p className="text-sm text-slate-500">{stat.label}</p>
              <p className={`mt-1 text-3xl font-bold ${stat.color}`}>
                {loading ? "-" : stat.value}
              </p>
            </Card>
          ))}
        </div>
      )}

      {/* Agent grid */}
      <div>
        <h2 className="mb-4 text-lg font-semibold text-slate-900">
          AI Agents
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {agentCards.map(({ key, href }) => (
            <Link key={key} href={href}>
              <Card className="group cursor-pointer transition-shadow hover:shadow-md">
                <div className="flex items-start gap-3">
                  <div
                    className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg text-sm font-bold text-white ${agentColors[key]}`}
                  >
                    {agentIcons[key]}
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold text-slate-900 group-hover:text-axiom-600">
                      {AGENT_DISPLAY_NAMES[key]}
                    </h3>
                    <p className="mt-0.5 text-xs text-slate-500 line-clamp-2">
                      {AGENT_DESCRIPTIONS[key]}
                    </p>
                  </div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      </div>

      {/* Recent tasks */}
      <div>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">
            Recent Tasks
          </h2>
          <Link
            href="/tasks"
            className="text-sm font-medium text-axiom-600 hover:text-axiom-700"
          >
            View all
          </Link>
        </div>
        {recentTasks.length === 0 ? (
          <Card>
            <p className="text-center text-sm text-slate-500">
              {loading ? "Loading tasks..." : "No tasks yet. Create one from an agent page."}
            </p>
          </Card>
        ) : (
          <Card padding={false}>
            <div className="divide-y divide-slate-100">
              {recentTasks.map((task) => (
                <Link
                  key={task.task_id}
                  href={`/tasks/${task.task_id}`}
                  className="flex items-center justify-between px-6 py-4 transition-colors hover:bg-slate-50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {task.request.goal}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {task.task_id} &middot;{" "}
                      {new Date(task.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <StatusBadge
                    status={task.status as TaskStatus}
                    className="ml-4 flex-shrink-0"
                  />
                </Link>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
