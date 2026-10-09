"use client";

import { useState } from "react";
import { Input, Textarea } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { AgentPageShell } from "@/components/agents/AgentPageShell";
import { useAuth } from "@/contexts/auth";
import type { AutoEvalReportRequest, EvaluatedAgent } from "@/lib/types";

const evaluatedAgents: { value: EvaluatedAgent; label: string }[] = [
  { value: "research", label: "Research Agent" },
  { value: "lecture_design", label: "Lecture Agent" },
  { value: "assessment_design", label: "Assessment Agent" },
  { value: "content_creation", label: "Content Agent" },
  { value: "writing_communication", label: "Writing Agent" },
  { value: "social_media", label: "Social Media Agent" },
  { value: "stem_ai_portfolio", label: "Portfolio Agent" },
];

export default function AutoEvalAgentPage() {
  const { api } = useAuth();
  const [form, setForm] = useState<AutoEvalReportRequest>({
    evaluated_agent: "research",
    deliverable_title: "",
    artifact_text: "",
    required_elements: [""],
    evidence_markers: [""],
    public_facing: false,
    declared_sensitive_data: false,
  });

  const updateField = <K extends keyof AutoEvalReportRequest>(
    key: K,
    value: AutoEvalReportRequest[K]
  ) => setForm((f) => ({ ...f, [key]: value }));

  const updateArrayItem = (
    field: "required_elements" | "evidence_markers",
    index: number,
    value: string
  ) => {
    const arr = [...(form[field] ?? [])];
    arr[index] = value;
    setForm((f) => ({ ...f, [field]: arr }));
  };

  const addArrayItem = (field: "required_elements" | "evidence_markers") =>
    setForm((f) => ({ ...f, [field]: [...(f[field] ?? []), ""] }));

  const removeArrayItem = (
    field: "required_elements" | "evidence_markers",
    index: number
  ) =>
    setForm((f) => ({
      ...f,
      [field]: (f[field] ?? []).filter((_, i) => i !== index),
    }));

  const getPayload = (): AutoEvalReportRequest => ({
    ...form,
    required_elements: form.required_elements.filter((e) => e.trim()),
    evidence_markers: (form.evidence_markers ?? []).filter((m) => m.trim()),
  });

  return (
    <AgentPageShell
      title="AutoEval"
      description="Automated quality evaluation of agent deliverables"
      icon="Ev"
      iconColor="bg-orange-600"
      onSubmit={() => api.createAutoEvalReport(getPayload())}
      onDownloadDocx={() => api.downloadAutoEvalDocx(getPayload())}
    >
      <Select
        label="Agent to Evaluate"
        options={evaluatedAgents}
        value={form.evaluated_agent}
        onChange={(e) =>
          updateField("evaluated_agent", e.target.value as EvaluatedAgent)
        }
      />
      <Input
        label="Deliverable Title"
        placeholder="Title of the deliverable being evaluated"
        value={form.deliverable_title}
        onChange={(e) => updateField("deliverable_title", e.target.value)}
        required
      />
      <Textarea
        label="Artifact Text"
        placeholder="Paste the full text of the deliverable to evaluate..."
        value={form.artifact_text}
        onChange={(e) => updateField("artifact_text", e.target.value)}
        required
        rows={8}
      />

      {/* Required Elements */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-slate-700">
          Required Elements
        </label>
        {form.required_elements.map((elem, i) => (
          <div key={i} className="flex gap-2">
            <Input
              placeholder={`Required element ${i + 1}`}
              value={elem}
              onChange={(e) =>
                updateArrayItem("required_elements", i, e.target.value)
              }
              className="flex-1"
            />
            {form.required_elements.length > 1 && (
              <button
                type="button"
                onClick={() => removeArrayItem("required_elements", i)}
                className="rounded-lg px-3 text-sm text-red-500 hover:bg-red-50"
              >
                Remove
              </button>
            )}
          </div>
        ))}
        <button
          type="button"
          onClick={() => addArrayItem("required_elements")}
          className="text-sm font-medium text-axiom-600 hover:text-axiom-700"
        >
          + Add element
        </button>
      </div>

      {/* Evidence Markers */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-slate-700">
          Evidence Markers
        </label>
        {(form.evidence_markers ?? [""]).map((marker, i) => (
          <div key={i} className="flex gap-2">
            <Input
              placeholder={`Evidence marker ${i + 1}`}
              value={marker}
              onChange={(e) =>
                updateArrayItem("evidence_markers", i, e.target.value)
              }
              className="flex-1"
            />
            {(form.evidence_markers ?? []).length > 1 && (
              <button
                type="button"
                onClick={() => removeArrayItem("evidence_markers", i)}
                className="rounded-lg px-3 text-sm text-red-500 hover:bg-red-50"
              >
                Remove
              </button>
            )}
          </div>
        ))}
        <button
          type="button"
          onClick={() => addArrayItem("evidence_markers")}
          className="text-sm font-medium text-axiom-600 hover:text-axiom-700"
        >
          + Add marker
        </button>
      </div>

      {/* Options */}
      <div className="space-y-3 border-t border-slate-100 pt-4">
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="public_facing"
            checked={form.public_facing}
            onChange={(e) => updateField("public_facing", e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-axiom-600 focus:ring-axiom-500"
          />
          <label htmlFor="public_facing" className="text-sm text-slate-700">
            Public-facing deliverable (stricter evaluation)
          </label>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="sensitive_data"
            checked={form.declared_sensitive_data}
            onChange={(e) =>
              updateField("declared_sensitive_data", e.target.checked)
            }
            className="h-4 w-4 rounded border-slate-300 text-axiom-600 focus:ring-axiom-500"
          />
          <label htmlFor="sensitive_data" className="text-sm text-slate-700">
            Contains declared sensitive data
          </label>
        </div>
      </div>
    </AgentPageShell>
  );
}
