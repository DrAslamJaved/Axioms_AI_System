"use client";

import { useState, type ReactNode, type FormEvent } from "react";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/contexts/auth";
import { ApiError } from "@/lib/api";

interface AgentPageShellProps {
  title: string;
  description: string;
  icon: string;
  iconColor: string;
  children: ReactNode;
  onSubmit: () => Promise<Record<string, unknown>>;
  onDownloadDocx?: () => Promise<Blob>;
  docxLabel?: string;
}

export function AgentPageShell({
  title,
  description,
  icon,
  iconColor,
  children,
  onSubmit,
  onDownloadDocx,
  docxLabel = "Download DOCX",
}: AgentPageShellProps) {
  const { connected } = useAuth();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const data = await onSubmit();
      setResult(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const handleDocx = async () => {
    if (!onDownloadDocx) return;
    setDownloading(true);
    try {
      const blob = await onDownloadDocx();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${title.toLowerCase().replace(/\s+/g, "_")}.docx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  };

  if (!connected) {
    return (
      <div className="pt-20 text-center text-sm text-slate-500">
        Connect to the API in Settings to use this agent.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div
          className={`flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl text-base font-bold text-white ${iconColor}`}
        >
          {icon}
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
          <p className="mt-0.5 text-sm text-slate-500">{description}</p>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Form */}
      <Card>
        <form onSubmit={handleSubmit} className="space-y-4">
          {children}
          <div className="flex flex-wrap gap-3 border-t border-slate-100 pt-4">
            <Button type="submit" loading={loading}>
              Generate
            </Button>
            {onDownloadDocx && (
              <Button
                type="button"
                variant="secondary"
                onClick={handleDocx}
                loading={downloading}
              >
                {docxLabel}
              </Button>
            )}
          </div>
        </form>
      </Card>

      {/* Result */}
      {result && (
        <Card>
          <CardTitle>Result</CardTitle>
          <div className="mt-4 max-h-[600px] overflow-y-auto rounded-md bg-slate-50 p-4">
            <pre className="whitespace-pre-wrap text-sm text-slate-700">
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        </Card>
      )}
    </div>
  );
}
