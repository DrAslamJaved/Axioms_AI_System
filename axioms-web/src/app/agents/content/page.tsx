"use client";

import { useState } from "react";
import { Input, Textarea } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { AgentPageShell } from "@/components/agents/AgentPageShell";
import { useAuth } from "@/contexts/auth";
import type {
  ContentPackageRequest,
  ContentFormat,
  LanguageMode,
} from "@/lib/types";

const contentFormats: { value: ContentFormat; label: string }[] = [
  { value: "video_script", label: "Video Script" },
  { value: "podcast_script", label: "Podcast Script" },
  { value: "infographic_brief", label: "Infographic Brief" },
  { value: "slide_deck", label: "Slide Deck" },
  { value: "worksheet", label: "Worksheet" },
];

const languageModes: { value: LanguageMode; label: string }[] = [
  { value: "english", label: "English" },
  { value: "urdu", label: "Urdu" },
  { value: "bilingual", label: "Bilingual" },
];

export default function ContentAgentPage() {
  const { api } = useAuth();
  const [form, setForm] = useState<ContentPackageRequest>({
    topic: "",
    format: "video_script",
    audience: "",
    duration_minutes: 15,
    approved_source_scope: "",
    learning_outcomes: [""],
    language_mode: "english",
    application_context: "",
    keywords: [""],
  });

  const updateField = <K extends keyof ContentPackageRequest>(
    key: K,
    value: ContentPackageRequest[K]
  ) => setForm((f) => ({ ...f, [key]: value }));

  const updateArrayItem = (
    field: "learning_outcomes" | "keywords",
    index: number,
    value: string
  ) => {
    const arr = [...(form[field] ?? [])];
    arr[index] = value;
    setForm((f) => ({ ...f, [field]: arr }));
  };

  const addArrayItem = (field: "learning_outcomes" | "keywords") =>
    setForm((f) => ({ ...f, [field]: [...(f[field] ?? []), ""] }));

  const removeArrayItem = (
    field: "learning_outcomes" | "keywords",
    index: number
  ) =>
    setForm((f) => ({
      ...f,
      [field]: (f[field] ?? []).filter((_, i) => i !== index),
    }));

  const getPayload = (): ContentPackageRequest => ({
    ...form,
    learning_outcomes: form.learning_outcomes.filter((o) => o.trim()),
    keywords: (form.keywords ?? []).filter((k) => k.trim()),
    application_context: form.application_context || null,
  });

  return (
    <AgentPageShell
      title="Content Creation"
      description="Educational content in multiple formats"
      icon="Cn"
      iconColor="bg-rose-600"
      onSubmit={() => api.createContentPackage(getPayload())}
      onDownloadDocx={() => api.downloadContentDocx(getPayload())}
    >
      <Input
        label="Topic"
        placeholder="e.g., Neural Network Architectures"
        value={form.topic}
        onChange={(e) => updateField("topic", e.target.value)}
        required
      />
      <div className="grid grid-cols-3 gap-4">
        <Select
          label="Format"
          options={contentFormats}
          value={form.format}
          onChange={(e) =>
            updateField("format", e.target.value as ContentFormat)
          }
        />
        <Select
          label="Language"
          options={languageModes}
          value={form.language_mode ?? "english"}
          onChange={(e) =>
            updateField("language_mode", e.target.value as LanguageMode)
          }
        />
        <Input
          label="Duration (min)"
          type="number"
          value={form.duration_minutes}
          onChange={(e) =>
            updateField("duration_minutes", parseInt(e.target.value) || 15)
          }
        />
      </div>
      <Input
        label="Audience"
        placeholder="Who is this content for?"
        value={form.audience}
        onChange={(e) => updateField("audience", e.target.value)}
        required
      />
      <Textarea
        label="Approved Source Scope"
        placeholder="Define the allowed source materials..."
        value={form.approved_source_scope}
        onChange={(e) => updateField("approved_source_scope", e.target.value)}
        required
        rows={2}
      />
      <Input
        label="Application Context"
        placeholder="e.g., Undergraduate STEM course"
        value={form.application_context ?? ""}
        onChange={(e) => updateField("application_context", e.target.value)}
      />

      {/* Learning outcomes */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-slate-700">
          Learning Outcomes
        </label>
        {form.learning_outcomes.map((outcome, i) => (
          <div key={i} className="flex gap-2">
            <Input
              placeholder={`Outcome ${i + 1}`}
              value={outcome}
              onChange={(e) =>
                updateArrayItem("learning_outcomes", i, e.target.value)
              }
              className="flex-1"
            />
            {form.learning_outcomes.length > 1 && (
              <button
                type="button"
                onClick={() => removeArrayItem("learning_outcomes", i)}
                className="rounded-lg px-3 text-sm text-red-500 hover:bg-red-50"
              >
                Remove
              </button>
            )}
          </div>
        ))}
        <button
          type="button"
          onClick={() => addArrayItem("learning_outcomes")}
          className="text-sm font-medium text-axiom-600 hover:text-axiom-700"
        >
          + Add outcome
        </button>
      </div>

      {/* Keywords */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-slate-700">
          Keywords
        </label>
        {(form.keywords ?? [""]).map((kw, i) => (
          <div key={i} className="flex gap-2">
            <Input
              placeholder={`Keyword ${i + 1}`}
              value={kw}
              onChange={(e) => updateArrayItem("keywords", i, e.target.value)}
              className="flex-1"
            />
            {(form.keywords ?? []).length > 1 && (
              <button
                type="button"
                onClick={() => removeArrayItem("keywords", i)}
                className="rounded-lg px-3 text-sm text-red-500 hover:bg-red-50"
              >
                Remove
              </button>
            )}
          </div>
        ))}
        <button
          type="button"
          onClick={() => addArrayItem("keywords")}
          className="text-sm font-medium text-axiom-600 hover:text-axiom-700"
        >
          + Add keyword
        </button>
      </div>
    </AgentPageShell>
  );
}
