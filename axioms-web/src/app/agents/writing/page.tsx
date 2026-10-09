"use client";

import { useState } from "react";
import { Input, Textarea } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { AgentPageShell } from "@/components/agents/AgentPageShell";
import { useAuth } from "@/contexts/auth";
import type { WritingDraftRequest, DocumentType } from "@/lib/types";

const documentTypes: { value: DocumentType; label: string }[] = [
  { value: "journal_article", label: "Journal Article" },
  { value: "conference_paper", label: "Conference Paper" },
  { value: "grant_proposal", label: "Grant Proposal" },
  { value: "technical_report", label: "Technical Report" },
  { value: "blog_post", label: "Blog Post" },
  { value: "course_material", label: "Course Material" },
  { value: "policy_brief", label: "Policy Brief" },
];

export default function WritingAgentPage() {
  const { api } = useAuth();
  const [form, setForm] = useState<WritingDraftRequest>({
    document_type: "journal_article",
    subject: "",
    audience: "",
    purpose: "",
    key_points: [""],
    verified_facts: [""],
    tone: "",
    references: [""],
    external_delivery: false,
  });

  const updateField = <K extends keyof WritingDraftRequest>(
    key: K,
    value: WritingDraftRequest[K]
  ) => setForm((f) => ({ ...f, [key]: value }));

  const updateArrayItem = (
    field: "key_points" | "verified_facts" | "references",
    index: number,
    value: string
  ) => {
    const arr = [...(form[field] ?? [])];
    arr[index] = value;
    setForm((f) => ({ ...f, [field]: arr }));
  };

  const addArrayItem = (field: "key_points" | "verified_facts" | "references") =>
    setForm((f) => ({ ...f, [field]: [...(f[field] ?? []), ""] }));

  const removeArrayItem = (
    field: "key_points" | "verified_facts" | "references",
    index: number
  ) =>
    setForm((f) => ({
      ...f,
      [field]: (f[field] ?? []).filter((_, i) => i !== index),
    }));

  const getPayload = (): WritingDraftRequest => ({
    ...form,
    key_points: form.key_points.filter((p) => p.trim()),
    verified_facts: form.verified_facts.filter((f) => f.trim()),
    references: (form.references ?? []).filter((r) => r.trim()),
    tone: form.tone || undefined,
  });

  return (
    <AgentPageShell
      title="Writing & Communication"
      description="Academic and professional writing drafts"
      icon="Wr"
      iconColor="bg-amber-600"
      onSubmit={() => api.createWritingDraft(getPayload())}
      onDownloadDocx={() => api.downloadWritingDraftDocx(getPayload())}
    >
      <div className="grid grid-cols-2 gap-4">
        <Select
          label="Document Type"
          options={documentTypes}
          value={form.document_type}
          onChange={(e) =>
            updateField("document_type", e.target.value as DocumentType)
          }
        />
        <Input
          label="Tone"
          placeholder="e.g., formal, conversational"
          value={form.tone ?? ""}
          onChange={(e) => updateField("tone", e.target.value)}
        />
      </div>
      <Input
        label="Subject"
        placeholder="What is this document about?"
        value={form.subject}
        onChange={(e) => updateField("subject", e.target.value)}
        required
      />
      <Input
        label="Audience"
        placeholder="Who will read this document?"
        value={form.audience}
        onChange={(e) => updateField("audience", e.target.value)}
        required
      />
      <Textarea
        label="Purpose"
        placeholder="What is the purpose of this document?"
        value={form.purpose}
        onChange={(e) => updateField("purpose", e.target.value)}
        required
        rows={2}
      />

      {/* Key Points */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-slate-700">
          Key Points
        </label>
        {form.key_points.map((point, i) => (
          <div key={i} className="flex gap-2">
            <Input
              placeholder={`Key point ${i + 1}`}
              value={point}
              onChange={(e) => updateArrayItem("key_points", i, e.target.value)}
              className="flex-1"
            />
            {form.key_points.length > 1 && (
              <button
                type="button"
                onClick={() => removeArrayItem("key_points", i)}
                className="rounded-lg px-3 text-sm text-red-500 hover:bg-red-50"
              >
                Remove
              </button>
            )}
          </div>
        ))}
        <button
          type="button"
          onClick={() => addArrayItem("key_points")}
          className="text-sm font-medium text-axiom-600 hover:text-axiom-700"
        >
          + Add key point
        </button>
      </div>

      {/* Verified Facts */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-slate-700">
          Verified Facts
        </label>
        {form.verified_facts.map((fact, i) => (
          <div key={i} className="flex gap-2">
            <Input
              placeholder={`Verified fact ${i + 1}`}
              value={fact}
              onChange={(e) =>
                updateArrayItem("verified_facts", i, e.target.value)
              }
              className="flex-1"
            />
            {form.verified_facts.length > 1 && (
              <button
                type="button"
                onClick={() => removeArrayItem("verified_facts", i)}
                className="rounded-lg px-3 text-sm text-red-500 hover:bg-red-50"
              >
                Remove
              </button>
            )}
          </div>
        ))}
        <button
          type="button"
          onClick={() => addArrayItem("verified_facts")}
          className="text-sm font-medium text-axiom-600 hover:text-axiom-700"
        >
          + Add fact
        </button>
      </div>

      {/* References */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-slate-700">
          References
        </label>
        {(form.references ?? [""]).map((ref, i) => (
          <div key={i} className="flex gap-2">
            <Input
              placeholder={`Reference ${i + 1}`}
              value={ref}
              onChange={(e) =>
                updateArrayItem("references", i, e.target.value)
              }
              className="flex-1"
            />
            {(form.references ?? []).length > 1 && (
              <button
                type="button"
                onClick={() => removeArrayItem("references", i)}
                className="rounded-lg px-3 text-sm text-red-500 hover:bg-red-50"
              >
                Remove
              </button>
            )}
          </div>
        ))}
        <button
          type="button"
          onClick={() => addArrayItem("references")}
          className="text-sm font-medium text-axiom-600 hover:text-axiom-700"
        >
          + Add reference
        </button>
      </div>

      <div className="flex items-center gap-3">
        <input
          type="checkbox"
          id="external_delivery"
          checked={form.external_delivery}
          onChange={(e) =>
            updateField("external_delivery", e.target.checked)
          }
          className="h-4 w-4 rounded border-slate-300 text-axiom-600 focus:ring-axiom-500"
        />
        <label htmlFor="external_delivery" className="text-sm text-slate-700">
          External delivery (content will be shared publicly)
        </label>
      </div>
    </AgentPageShell>
  );
}
