"use client";

import { useState } from "react";
import { Input, Textarea } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";
import { AgentPageShell } from "@/components/agents/AgentPageShell";
import { useAuth } from "@/contexts/auth";
import type {
  PortfolioPackageRequest,
  PortfolioAudience,
  RepositoryVisibility,
  DataAccessLevel,
  PortfolioEvidence,
  DatasetAsset,
} from "@/lib/types";

const audienceOptions: { value: PortfolioAudience; label: string }[] = [
  { value: "academic", label: "Academic" },
  { value: "industry", label: "Industry" },
  { value: "general", label: "General" },
];

const visibilityOptions: { value: RepositoryVisibility; label: string }[] = [
  { value: "public", label: "Public" },
  { value: "private", label: "Private" },
];

const accessLevels: { value: DataAccessLevel; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "restricted", label: "Restricted" },
  { value: "synthetic", label: "Synthetic" },
];

export default function PortfolioAgentPage() {
  const { api } = useAuth();
  const [form, setForm] = useState<PortfolioPackageRequest>({
    project_title: "",
    research_summary: "",
    target_audience: "academic",
    repository_visibility: "public",
    verified_evidence: [],
    dataset_assets: [],
    include_demo_plan: true,
    include_notebook_plan: true,
  });

  const [showEvidenceForm, setShowEvidenceForm] = useState(false);
  const [showDatasetForm, setShowDatasetForm] = useState(false);
  const [currentEvidence, setCurrentEvidence] = useState<PortfolioEvidence>({
    evidence_id: "",
    claim: "",
    source_reference: "",
    verified: false,
  });
  const [currentDataset, setCurrentDataset] = useState<DatasetAsset>({
    name: "",
    access_level: "open",
    licence_or_permission: "",
    attribution: "",
  });

  const updateField = <K extends keyof PortfolioPackageRequest>(
    key: K,
    value: PortfolioPackageRequest[K]
  ) => setForm((f) => ({ ...f, [key]: value }));

  const addEvidence = () => {
    if (!currentEvidence.claim.trim()) return;
    setForm((f) => ({
      ...f,
      verified_evidence: [
        ...f.verified_evidence,
        {
          ...currentEvidence,
          evidence_id:
            currentEvidence.evidence_id ||
            `ev_${f.verified_evidence.length + 1}`,
        },
      ],
    }));
    setCurrentEvidence({
      evidence_id: "",
      claim: "",
      source_reference: "",
      verified: false,
    });
    setShowEvidenceForm(false);
  };

  const removeEvidence = (index: number) =>
    setForm((f) => ({
      ...f,
      verified_evidence: f.verified_evidence.filter((_, i) => i !== index),
    }));

  const addDataset = () => {
    if (!currentDataset.name.trim()) return;
    setForm((f) => ({
      ...f,
      dataset_assets: [...(f.dataset_assets ?? []), currentDataset],
    }));
    setCurrentDataset({
      name: "",
      access_level: "open",
      licence_or_permission: "",
      attribution: "",
    });
    setShowDatasetForm(false);
  };

  const removeDataset = (index: number) =>
    setForm((f) => ({
      ...f,
      dataset_assets: (f.dataset_assets ?? []).filter((_, i) => i !== index),
    }));

  return (
    <AgentPageShell
      title="STEM AI Portfolio"
      description="Research portfolio packaging and showcase generation"
      icon="Pf"
      iconColor="bg-teal-600"
      onSubmit={() => api.createPortfolioPackage(form)}
      onDownloadDocx={() => api.downloadPortfolioDocx(form)}
    >
      <Input
        label="Project Title"
        placeholder="e.g., Federated Learning for Healthcare"
        value={form.project_title}
        onChange={(e) => updateField("project_title", e.target.value)}
        required
      />
      <Textarea
        label="Research Summary"
        placeholder="Summarize the research project..."
        value={form.research_summary}
        onChange={(e) => updateField("research_summary", e.target.value)}
        required
      />
      <div className="grid grid-cols-2 gap-4">
        <Select
          label="Target Audience"
          options={audienceOptions}
          value={form.target_audience}
          onChange={(e) =>
            updateField("target_audience", e.target.value as PortfolioAudience)
          }
        />
        <Select
          label="Repository Visibility"
          options={visibilityOptions}
          value={form.repository_visibility}
          onChange={(e) =>
            updateField(
              "repository_visibility",
              e.target.value as RepositoryVisibility
            )
          }
        />
      </div>

      {/* Verified Evidence */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="block text-sm font-medium text-slate-700">
            Verified Evidence ({form.verified_evidence.length})
          </label>
          <button
            type="button"
            onClick={() => setShowEvidenceForm(!showEvidenceForm)}
            className="text-sm font-medium text-axiom-600 hover:text-axiom-700"
          >
            {showEvidenceForm ? "Cancel" : "+ Add evidence"}
          </button>
        </div>
        {showEvidenceForm && (
          <div className="space-y-3 rounded-lg border border-slate-200 p-4">
            <Input
              label="Claim"
              placeholder="What is the evidence claim?"
              value={currentEvidence.claim}
              onChange={(e) =>
                setCurrentEvidence((s) => ({ ...s, claim: e.target.value }))
              }
            />
            <Input
              label="Source Reference"
              placeholder="Where does this evidence come from?"
              value={currentEvidence.source_reference}
              onChange={(e) =>
                setCurrentEvidence((s) => ({
                  ...s,
                  source_reference: e.target.value,
                }))
              }
            />
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="ev_verified"
                checked={currentEvidence.verified}
                onChange={(e) =>
                  setCurrentEvidence((s) => ({
                    ...s,
                    verified: e.target.checked,
                  }))
                }
                className="h-4 w-4 rounded border-slate-300 text-axiom-600 focus:ring-axiom-500"
              />
              <label htmlFor="ev_verified" className="text-sm text-slate-700">
                Verified
              </label>
            </div>
            <Button type="button" size="sm" onClick={addEvidence}>
              Add Evidence
            </Button>
          </div>
        )}
        {form.verified_evidence.map((ev, i) => (
          <div
            key={i}
            className="flex items-start justify-between rounded-lg border border-slate-200 px-4 py-3"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-900">{ev.claim}</p>
              <p className="text-xs text-slate-500">
                {ev.source_reference}
                {ev.verified && " · Verified"}
              </p>
            </div>
            <button
              type="button"
              onClick={() => removeEvidence(i)}
              className="ml-3 text-sm text-red-500 hover:text-red-700"
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      {/* Dataset Assets */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="block text-sm font-medium text-slate-700">
            Dataset Assets ({(form.dataset_assets ?? []).length})
          </label>
          <button
            type="button"
            onClick={() => setShowDatasetForm(!showDatasetForm)}
            className="text-sm font-medium text-axiom-600 hover:text-axiom-700"
          >
            {showDatasetForm ? "Cancel" : "+ Add dataset"}
          </button>
        </div>
        {showDatasetForm && (
          <div className="space-y-3 rounded-lg border border-slate-200 p-4">
            <Input
              label="Dataset Name"
              placeholder="Name of the dataset"
              value={currentDataset.name}
              onChange={(e) =>
                setCurrentDataset((s) => ({ ...s, name: e.target.value }))
              }
            />
            <Select
              label="Access Level"
              options={accessLevels}
              value={currentDataset.access_level}
              onChange={(e) =>
                setCurrentDataset((s) => ({
                  ...s,
                  access_level: e.target.value as DataAccessLevel,
                }))
              }
            />
            <Input
              label="Licence / Permission"
              placeholder="e.g., CC-BY-4.0, MIT"
              value={currentDataset.licence_or_permission ?? ""}
              onChange={(e) =>
                setCurrentDataset((s) => ({
                  ...s,
                  licence_or_permission: e.target.value,
                }))
              }
            />
            <Input
              label="Attribution"
              placeholder="Required attribution"
              value={currentDataset.attribution ?? ""}
              onChange={(e) =>
                setCurrentDataset((s) => ({
                  ...s,
                  attribution: e.target.value,
                }))
              }
            />
            <Button type="button" size="sm" onClick={addDataset}>
              Add Dataset
            </Button>
          </div>
        )}
        {(form.dataset_assets ?? []).map((ds, i) => (
          <div
            key={i}
            className="flex items-start justify-between rounded-lg border border-slate-200 px-4 py-3"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-900">{ds.name}</p>
              <p className="text-xs text-slate-500">
                {ds.access_level}
                {ds.licence_or_permission && ` · ${ds.licence_or_permission}`}
              </p>
            </div>
            <button
              type="button"
              onClick={() => removeDataset(i)}
              className="ml-3 text-sm text-red-500 hover:text-red-700"
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      {/* Options */}
      <div className="space-y-3 border-t border-slate-100 pt-4">
        {[
          {
            key: "include_demo_plan" as const,
            label: "Include demo plan",
          },
          {
            key: "include_notebook_plan" as const,
            label: "Include notebook plan",
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
