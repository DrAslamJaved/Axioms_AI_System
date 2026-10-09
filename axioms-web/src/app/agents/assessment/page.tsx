"use client";

import { useState } from "react";
import { Input, Textarea } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";
import { AgentPageShell } from "@/components/agents/AgentPageShell";
import { useAuth } from "@/contexts/auth";
import type {
  AssessmentBlueprintRequest,
  LearningOutcome,
  AssessmentType,
  BloomLevel,
} from "@/lib/types";

const assessmentTypes: { value: AssessmentType; label: string }[] = [
  { value: "exam", label: "Exam" },
  { value: "quiz", label: "Quiz" },
  { value: "assignment", label: "Assignment" },
  { value: "project", label: "Project" },
  { value: "lab_report", label: "Lab Report" },
];

const bloomLevels: { value: BloomLevel; label: string }[] = [
  { value: "remember", label: "Remember" },
  { value: "understand", label: "Understand" },
  { value: "apply", label: "Apply" },
  { value: "analyze", label: "Analyze" },
  { value: "evaluate", label: "Evaluate" },
  { value: "create", label: "Create" },
];

const courseLevels = [
  { value: "introductory", label: "Introductory" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
  { value: "graduate", label: "Graduate" },
];

const difficulties = [
  { value: "easy", label: "Easy" },
  { value: "moderate", label: "Moderate" },
  { value: "hard", label: "Hard" },
  { value: "expert", label: "Expert" },
];

const emptyOutcome: LearningOutcome = {
  outcome_id: "",
  text: "",
  bloom_level: "understand",
};

export default function AssessmentAgentPage() {
  const { api } = useAuth();
  const [form, setForm] = useState<AssessmentBlueprintRequest>({
    topic: "",
    course_level: "introductory",
    assessment_type: "exam",
    duration_minutes: 90,
    total_marks: 100,
    question_count: 10,
    learning_outcomes: [{ ...emptyOutcome, outcome_id: "lo_1" }],
    approved_source_scope: "",
    difficulties: ["moderate"],
    require_handwritten_work: false,
    require_reflection: false,
    include_personalised_context: false,
  });
  const [selectedDifficulties, setSelectedDifficulties] = useState<string[]>([
    "moderate",
  ]);

  const updateField = <K extends keyof AssessmentBlueprintRequest>(
    key: K,
    value: AssessmentBlueprintRequest[K]
  ) => setForm((f) => ({ ...f, [key]: value }));

  const updateOutcome = (
    index: number,
    field: keyof LearningOutcome,
    value: string
  ) => {
    const outcomes = [...form.learning_outcomes];
    outcomes[index] = { ...outcomes[index], [field]: value };
    setForm((f) => ({ ...f, learning_outcomes: outcomes }));
  };

  const addOutcome = () =>
    setForm((f) => ({
      ...f,
      learning_outcomes: [
        ...f.learning_outcomes,
        {
          ...emptyOutcome,
          outcome_id: `lo_${f.learning_outcomes.length + 1}`,
        },
      ],
    }));

  const removeOutcome = (index: number) =>
    setForm((f) => ({
      ...f,
      learning_outcomes: f.learning_outcomes.filter((_, i) => i !== index),
    }));

  const toggleDifficulty = (d: string) => {
    setSelectedDifficulties((prev) => {
      const next = prev.includes(d)
        ? prev.filter((x) => x !== d)
        : [...prev, d];
      setForm((f) => ({ ...f, difficulties: next as AssessmentBlueprintRequest["difficulties"] }));
      return next;
    });
  };

  const getPayload = (): AssessmentBlueprintRequest => ({
    ...form,
    learning_outcomes: form.learning_outcomes.filter((o) => o.text.trim()),
    difficulties: selectedDifficulties as AssessmentBlueprintRequest["difficulties"],
  });

  return (
    <AgentPageShell
      title="Assessment Design"
      description="Generate Bloom-aligned assessment blueprints and exam papers"
      icon="As"
      iconColor="bg-violet-600"
      onSubmit={() => api.createAssessmentBlueprint(getPayload())}
      onDownloadDocx={() => api.downloadStudentDocx(getPayload())}
      docxLabel="Student DOCX"
    >
      <Input
        label="Topic"
        placeholder="e.g., Data Structures and Algorithms"
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
        <Select
          label="Assessment Type"
          options={assessmentTypes}
          value={form.assessment_type}
          onChange={(e) =>
            updateField("assessment_type", e.target.value as AssessmentType)
          }
        />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <Input
          label="Duration (min)"
          type="number"
          value={form.duration_minutes}
          onChange={(e) =>
            updateField("duration_minutes", parseInt(e.target.value) || 90)
          }
        />
        <Input
          label="Total Marks"
          type="number"
          value={form.total_marks}
          onChange={(e) =>
            updateField("total_marks", parseInt(e.target.value) || 100)
          }
        />
        <Input
          label="Questions"
          type="number"
          value={form.question_count}
          onChange={(e) =>
            updateField("question_count", parseInt(e.target.value) || 10)
          }
        />
      </div>
      <Textarea
        label="Approved Source Scope"
        placeholder="Define the allowed source materials for this assessment..."
        value={form.approved_source_scope}
        onChange={(e) => updateField("approved_source_scope", e.target.value)}
        required
        rows={2}
      />

      {/* Difficulty selection */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-slate-700">
          Difficulty Levels
        </label>
        <div className="flex flex-wrap gap-2">
          {difficulties.map((d) => (
            <button
              key={d.value}
              type="button"
              onClick={() => toggleDifficulty(d.value)}
              className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
                selectedDifficulties.includes(d.value)
                  ? "bg-axiom-100 text-axiom-700 ring-1 ring-axiom-300"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {d.label}
            </button>
          ))}
        </div>
      </div>

      {/* Learning outcomes */}
      <div className="space-y-3">
        <label className="block text-sm font-medium text-slate-700">
          Learning Outcomes
        </label>
        {form.learning_outcomes.map((outcome, i) => (
          <div
            key={i}
            className="space-y-2 rounded-lg border border-slate-200 p-3"
          >
            <div className="flex gap-2">
              <Input
                placeholder="Describe the learning outcome..."
                value={outcome.text}
                onChange={(e) => updateOutcome(i, "text", e.target.value)}
                className="flex-1"
              />
              <Select
                options={bloomLevels}
                value={outcome.bloom_level}
                onChange={(e) =>
                  updateOutcome(i, "bloom_level", e.target.value)
                }
                className="w-40"
              />
            </div>
            {form.learning_outcomes.length > 1 && (
              <button
                type="button"
                onClick={() => removeOutcome(i)}
                className="text-xs text-red-500 hover:text-red-700"
              >
                Remove outcome
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

      {/* Options */}
      <div className="space-y-3 border-t border-slate-100 pt-4">
        {[
          {
            key: "require_handwritten_work" as const,
            label: "Require handwritten work",
          },
          {
            key: "require_reflection" as const,
            label: "Include reflection questions",
          },
          {
            key: "include_personalised_context" as const,
            label: "Include personalised context",
          },
        ].map(({ key, label }) => (
          <div key={key} className="flex items-center gap-3">
            <input
              type="checkbox"
              id={key}
              checked={!!form[key]}
              onChange={(e) => updateField(key, e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-axiom-600 focus:ring-axiom-500"
            />
            <label htmlFor={key} className="text-sm text-slate-700">
              {label}
            </label>
          </div>
        ))}
      </div>
    </AgentPageShell>
  );
}
