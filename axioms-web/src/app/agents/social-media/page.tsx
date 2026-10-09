"use client";

import { useState } from "react";
import { Input, Textarea } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { AgentPageShell } from "@/components/agents/AgentPageShell";
import { useAuth } from "@/contexts/auth";
import type {
  SocialMediaPackageRequest,
  SocialPlatform,
  SocialObjective,
} from "@/lib/types";

const platformOptions: { value: SocialPlatform; label: string }[] = [
  { value: "twitter", label: "Twitter / X" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "youtube", label: "YouTube" },
  { value: "instagram", label: "Instagram" },
  { value: "facebook", label: "Facebook" },
];

const objectiveOptions: { value: SocialObjective; label: string }[] = [
  { value: "educate", label: "Educate" },
  { value: "engage", label: "Engage" },
  { value: "promote", label: "Promote" },
  { value: "recruit", label: "Recruit" },
];

export default function SocialMediaAgentPage() {
  const { api } = useAuth();
  const [form, setForm] = useState<SocialMediaPackageRequest>({
    topic: "",
    audience: "",
    platforms: ["linkedin"],
    objective: "educate",
    approved_source_scope: "",
    verified_facts: [""],
    brand_voice: "",
    call_to_action: "",
    calendar_weeks: 4,
  });
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([
    "linkedin",
  ]);

  const updateField = <K extends keyof SocialMediaPackageRequest>(
    key: K,
    value: SocialMediaPackageRequest[K]
  ) => setForm((f) => ({ ...f, [key]: value }));

  const togglePlatform = (platform: string) => {
    setSelectedPlatforms((prev) => {
      const next = prev.includes(platform)
        ? prev.filter((p) => p !== platform)
        : [...prev, platform];
      if (next.length === 0) return prev;
      setForm((f) => ({ ...f, platforms: next as SocialPlatform[] }));
      return next;
    });
  };

  const updateFact = (index: number, value: string) => {
    const facts = [...form.verified_facts];
    facts[index] = value;
    setForm((f) => ({ ...f, verified_facts: facts }));
  };

  const addFact = () =>
    setForm((f) => ({ ...f, verified_facts: [...f.verified_facts, ""] }));

  const removeFact = (index: number) =>
    setForm((f) => ({
      ...f,
      verified_facts: f.verified_facts.filter((_, i) => i !== index),
    }));

  const getPayload = (): SocialMediaPackageRequest => ({
    ...form,
    platforms: selectedPlatforms as SocialPlatform[],
    verified_facts: form.verified_facts.filter((f) => f.trim()),
    brand_voice: form.brand_voice || undefined,
    call_to_action: form.call_to_action || null,
  });

  return (
    <AgentPageShell
      title="Social Media"
      description="Platform-specific social media content calendars"
      icon="Sm"
      iconColor="bg-sky-600"
      onSubmit={() => api.createSocialMediaPackage(getPayload())}
      onDownloadDocx={() => api.downloadSocialMediaDocx(getPayload())}
    >
      <Input
        label="Topic"
        placeholder="e.g., AI in Education — Weekly Series"
        value={form.topic}
        onChange={(e) => updateField("topic", e.target.value)}
        required
      />
      <Input
        label="Audience"
        placeholder="e.g., STEM educators, researchers"
        value={form.audience}
        onChange={(e) => updateField("audience", e.target.value)}
        required
      />

      {/* Platforms */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-slate-700">
          Platforms
        </label>
        <div className="flex flex-wrap gap-2">
          {platformOptions.map((p) => (
            <button
              key={p.value}
              type="button"
              onClick={() => togglePlatform(p.value)}
              className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
                selectedPlatforms.includes(p.value)
                  ? "bg-axiom-100 text-axiom-700 ring-1 ring-axiom-300"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Select
          label="Objective"
          options={objectiveOptions}
          value={form.objective ?? "educate"}
          onChange={(e) =>
            updateField("objective", e.target.value as SocialObjective)
          }
        />
        <Input
          label="Calendar Weeks"
          type="number"
          value={form.calendar_weeks ?? 4}
          onChange={(e) =>
            updateField("calendar_weeks", parseInt(e.target.value) || 4)
          }
        />
      </div>

      <Textarea
        label="Approved Source Scope"
        placeholder="Define the allowed source materials..."
        value={form.approved_source_scope}
        onChange={(e) => updateField("approved_source_scope", e.target.value)}
        required
        rows={2}
      />
      <Input
        label="Brand Voice"
        placeholder="e.g., Professional, approachable, data-driven"
        value={form.brand_voice ?? ""}
        onChange={(e) => updateField("brand_voice", e.target.value)}
      />
      <Input
        label="Call to Action"
        placeholder="e.g., Visit our lab website, Register for workshop"
        value={form.call_to_action ?? ""}
        onChange={(e) => updateField("call_to_action", e.target.value)}
      />

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
              onChange={(e) => updateFact(i, e.target.value)}
              className="flex-1"
            />
            {form.verified_facts.length > 1 && (
              <button
                type="button"
                onClick={() => removeFact(i)}
                className="rounded-lg px-3 text-sm text-red-500 hover:bg-red-50"
              >
                Remove
              </button>
            )}
          </div>
        ))}
        <button
          type="button"
          onClick={addFact}
          className="text-sm font-medium text-axiom-600 hover:text-axiom-700"
        >
          + Add fact
        </button>
      </div>
    </AgentPageShell>
  );
}
