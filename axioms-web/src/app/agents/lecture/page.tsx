"use client";

import { useState } from "react";
import { Input, Textarea } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { AgentPageShell } from "@/components/agents/AgentPageShell";
import { useAuth } from "@/contexts/auth";
import type { LecturePlanRequest } from "@/lib/types";

const courseLevels = [
  { value: "introductory", label: "Introductory" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
  { value: "graduate", label: "Graduate" },
  { value: "professional", label: "Professional" },
];

export default function LectureAgentPage() {
  const { api } = useAuth();
  const [form, setForm] = useState<LecturePlanRequest>({
    topic: "",
    course_level: "introductory",
    duration_minutes: 60,
    audience: "",
    prior_knowledge: "",
    learning_outcomes: [""],
    application_context: "",
    include_computational_activity: false,
  });

  const updateField = <K extends keyof LecturePlanRequest>(
    key: K,
    value: LecturePlanRequest[K]
  ) => setForm((f) => ({ ...f, [key]: value }));

  const updateOutcome = (index: number, value: string) => {
    const outcomes = [...form.learning_outcomes];
    outcomes[index] = value;
    setForm((f) => ({ ...f, learning_outcomes: outcomes }));
  };

  const addOutcome = () =>
    setForm((f) => ({
      ...f,
      learning_outcomes: [...f.learning_outcomes, ""],
    }));

  const removeOutcome = (index: number) =>
    setForm((f) => ({
      ...f,
      learning_outcomes: f.learning_outcomes.filter((_, i) => i !== index),
    }));

  const getPayload = (): LecturePlanRequest => ({
    ...form,
    learning_outcomes: form.learning_outcomes.filter((o) => o.trim()),
    application_context: form.application_context || null,
    prior_knowledge: form.prior_knowledge || undefined,
  });

  return (
    <AgentPageShell
      title="Lecture Design"
      description="Generate structured lecture plans with learning outcomes and activities"
      icon="Lc"
      iconColor="bg-blue-600"
      onSubmit={() => api.createLecturePlan(getPayload())}
      onDownloadDocx={() => api.downloadLecturePlanDocx(getPayload())}
    >
      <Input
        label="Topic"
        placeholder="e.g., Introduction to Machine Learning"
        value={form.topic}
        onChange={(e) => updateField("topic", e.target.value)}
        required
      />
      <div className="grid grid-cols-2 gap-4">
        <Select
          label="Course Level"
          options={courseLevels}
          value={form.course_level}
          onChange={(e) => updateField("course_level", e.target.value)}
        />
        <Input
          label="Duration (minutes)"
          type="number"
          value={form.duration_minutes}
          onChange={(e) =>
            updateField("duration_minutes", parseInt(e.target.value) || 60)
          }
        />
      </div>
      <Input
        label="Audience"
        placeholder="e.g., Undergraduate CS students"
        value={form.audience}
        onChange={(e) => updateField("audience", e.target.value)}
        required
      />
      <Textarea
        label="Prior Knowledge"
        placeholder="What should students already know?"
        value={form.prior_knowledge}
        onChange={(e) => updateField("prior_knowledge", e.target.value)}
        rows={2}
      />
      <div className="space-y-2">
        <label className="block text-sm font-medium text-slate-700">
          Learning Outcomes
        </label>
        {form.learning_outcomes.map((outcome, i) => (
          <div key={i} className="flex gap-2">
            <Input
              placeholder={`Outcome ${i + 1}`}
              value={outcome}
              onChange={(e) => updateOutcome(i, e.target.value)}
              className="flex-1"
            />
            {form.learning_outcomes.length > 1 && (
              <button
                type="button"
                onClick={() => removeOutcome(i)}
                className="rounded-lg px-3 text-sm text-red-500 hover:bg-red-50"
              >
                Remove
              </button>
            )}
          </div>
        ))}
        <button
          type="button"
          onClick={addOutcome}
          className="text-sm font-medium text-axiom-600 hover:text-axiom-700"
        >
          + Add outcome
        </button>
      </div>
      <Input
        label="Application Context"
        placeholder="e.g., STEM education, industry training"
        value={form.application_context ?? ""}
        onChange={(e) => updateField("application_context", e.target.value)}
      />
      <div className="flex items-center gap-3">
        <input
          type="checkbox"
          id="computational"
          checked={form.include_computational_activity}
          onChange={(e) =>
            updateField("include_computational_activity", e.target.checked)
          }
          className="h-4 w-4 rounded border-slate-300 text-axiom-600 focus:ring-axiom-500"
        />
        <label htmlFor="computational" className="text-sm text-slate-700">
          Include computational activity (code demos, exercises)
        </label>
      </div>
    </AgentPageShell>
  );
}
