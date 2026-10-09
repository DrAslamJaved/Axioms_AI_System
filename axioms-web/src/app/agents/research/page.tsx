"use client";

import { useState } from "react";
import { Input, Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { AgentPageShell } from "@/components/agents/AgentPageShell";
import { useAuth } from "@/contexts/auth";
import type { ResearchBriefRequest, EvidenceSource } from "@/lib/types";

const emptySource: EvidenceSource = {
  source_id: "",
  title: "",
  authors: [],
  year: new Date().getFullYear(),
  publication_kind: "journal_article",
  doi: "",
  peer_reviewed: true,
  supported_claim: "",
  verification_status: "unverified",
};

export default function ResearchAgentPage() {
  const { api } = useAuth();
  const [form, setForm] = useState<ResearchBriefRequest>({
    research_question: "",
    scope: "",
    sources: [],
    analysis_dimensions: [""],
    target_venue: "",
  });
  const [showSourceForm, setShowSourceForm] = useState(false);
  const [currentSource, setCurrentSource] =
    useState<EvidenceSource>(emptySource);

  const updateField = <K extends keyof ResearchBriefRequest>(
    key: K,
    value: ResearchBriefRequest[K]
  ) => setForm((f) => ({ ...f, [key]: value }));

  const updateDimension = (index: number, value: string) => {
    const dims = [...(form.analysis_dimensions ?? [""])];
    dims[index] = value;
    setForm((f) => ({ ...f, analysis_dimensions: dims }));
  };

  const addDimension = () =>
    setForm((f) => ({
      ...f,
      analysis_dimensions: [...(f.analysis_dimensions ?? []), ""],
    }));

  const removeDimension = (index: number) =>
    setForm((f) => ({
      ...f,
      analysis_dimensions: (f.analysis_dimensions ?? []).filter(
        (_, i) => i !== index
      ),
    }));

  const addSource = () => {
    if (!currentSource.title.trim()) return;
    setForm((f) => ({
      ...f,
      sources: [
        ...f.sources,
        {
          ...currentSource,
          source_id:
            currentSource.source_id || `src_${f.sources.length + 1}`,
          authors:
            typeof currentSource.authors === "string"
              ? (currentSource.authors as unknown as string)
                  .split(",")
                  .map((a: string) => a.trim())
              : currentSource.authors,
        },
      ],
    }));
    setCurrentSource(emptySource);
    setShowSourceForm(false);
  };

  const removeSource = (index: number) =>
    setForm((f) => ({
      ...f,
      sources: f.sources.filter((_, i) => i !== index),
    }));

  const getPayload = (): ResearchBriefRequest => ({
    ...form,
    analysis_dimensions: (form.analysis_dimensions ?? []).filter((d) =>
      d.trim()
    ),
    target_venue: form.target_venue || null,
  });

  return (
    <AgentPageShell
      title="Research Agent"
      description="Literature review, evidence synthesis, and research briefs"
      icon="Rs"
      iconColor="bg-emerald-600"
      onSubmit={() => api.createResearchBrief(getPayload())}
      onDownloadDocx={() => api.downloadResearchBriefDocx(getPayload())}
    >
      <Textarea
        label="Research Question"
        placeholder="What is the primary research question to investigate?"
        value={form.research_question}
        onChange={(e) => updateField("research_question", e.target.value)}
        required
      />
      <Textarea
        label="Scope"
        placeholder="Define the scope and boundaries of the research..."
        value={form.scope}
        onChange={(e) => updateField("scope", e.target.value)}
        required
        rows={3}
      />
      <Input
        label="Target Venue"
        placeholder="e.g., Nature Machine Intelligence, ICML 2025"
        value={form.target_venue ?? ""}
        onChange={(e) => updateField("target_venue", e.target.value)}
      />

      {/* Analysis dimensions */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-slate-700">
          Analysis Dimensions
        </label>
        {(form.analysis_dimensions ?? [""]).map((dim, i) => (
          <div key={i} className="flex gap-2">
            <Input
              placeholder={`Dimension ${i + 1} (e.g., methodology, impact)`}
              value={dim}
              onChange={(e) => updateDimension(i, e.target.value)}
              className="flex-1"
            />
            {(form.analysis_dimensions ?? []).length > 1 && (
              <button
                type="button"
                onClick={() => removeDimension(i)}
                className="rounded-lg px-3 text-sm text-red-500 hover:bg-red-50"
              >
                Remove
              </button>
            )}
          </div>
        ))}
        <button
          type="button"
          onClick={addDimension}
          className="text-sm font-medium text-axiom-600 hover:text-axiom-700"
        >
          + Add dimension
        </button>
      </div>

      {/* Sources */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="block text-sm font-medium text-slate-700">
            Evidence Sources ({form.sources.length})
          </label>
          <button
            type="button"
            onClick={() => setShowSourceForm(!showSourceForm)}
            className="text-sm font-medium text-axiom-600 hover:text-axiom-700"
          >
            {showSourceForm ? "Cancel" : "+ Add source"}
          </button>
        </div>
        {showSourceForm && (
          <div className="space-y-3 rounded-lg border border-slate-200 p-4">
            <Input
              label="Title"
              placeholder="Paper title"
              value={currentSource.title}
              onChange={(e) =>
                setCurrentSource((s) => ({ ...s, title: e.target.value }))
              }
            />
            <Input
              label="Authors (comma-separated)"
              placeholder="Jane Doe, John Smith"
              value={
                Array.isArray(currentSource.authors)
                  ? currentSource.authors.join(", ")
                  : currentSource.authors
              }
              onChange={(e) =>
                setCurrentSource((s) => ({
                  ...s,
                  authors: e.target.value.split(",").map((a) => a.trim()),
                }))
              }
            />
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Year"
                type="number"
                value={currentSource.year}
                onChange={(e) =>
                  setCurrentSource((s) => ({
                    ...s,
                    year: parseInt(e.target.value) || new Date().getFullYear(),
                  }))
                }
              />
              <Input
                label="DOI"
                placeholder="10.xxxx/xxxxx"
                value={currentSource.doi ?? ""}
                onChange={(e) =>
                  setCurrentSource((s) => ({ ...s, doi: e.target.value }))
                }
              />
            </div>
            <Input
              label="Supported Claim"
              placeholder="What claim does this source support?"
              value={currentSource.supported_claim ?? ""}
              onChange={(e) =>
                setCurrentSource((s) => ({
                  ...s,
                  supported_claim: e.target.value,
                }))
              }
            />
            <Button type="button" size="sm" onClick={addSource}>
              Add Source
            </Button>
          </div>
        )}
        {form.sources.map((src, i) => (
          <div
            key={i}
            className="flex items-start justify-between rounded-lg border border-slate-200 px-4 py-3"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-900">{src.title}</p>
              <p className="text-xs text-slate-500">
                {src.authors.join(", ")} ({src.year})
                {src.doi && ` · DOI: ${src.doi}`}
              </p>
            </div>
            <button
              type="button"
              onClick={() => removeSource(i)}
              className="ml-3 text-sm text-red-500 hover:text-red-700"
            >
              Remove
            </button>
          </div>
        ))}
      </div>
    </AgentPageShell>
  );
}
