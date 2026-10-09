"use client";

import { useState } from "react";
import { Card, CardTitle, CardDescription } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/contexts/auth";
import { ApiError } from "@/lib/api";

interface MemoryEntry {
  memory_id: string;
  task_id: string;
  summary: string;
  created_at: string;
  approved_at?: string;
  retention_days: number;
}

export default function MemoryPage() {
  const { api, connected, approverName } = useAuth();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState("");

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    try {
      const data = await api.searchMemory(query, 10);
      setResults(data as unknown as MemoryEntry[]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await api.deleteMemory(id, approverName || "web_user", "Deleted from web UI");
      setResults((prev) => prev.filter((m) => m.memory_id !== id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    } finally {
      setDeletingId("");
    }
  };

  if (!connected) {
    return (
      <div className="pt-20 text-center text-sm text-slate-500">
        Connect to the API in Settings to search episodic memory.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Episodic Memory</h1>
        <p className="mt-1 text-sm text-slate-500">
          Search and manage the system&apos;s episodic memory entries
        </p>
      </div>

      {/* Search */}
      <Card>
        <div className="flex gap-3">
          <div className="flex-1">
            <Input
              placeholder="Search memory entries..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
          </div>
          <Button onClick={handleSearch} loading={loading}>
            Search
          </Button>
        </div>
      </Card>

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <Card>
          <CardTitle>Results ({results.length})</CardTitle>
          <div className="mt-4 space-y-3">
            {results.map((entry) => (
              <div
                key={entry.memory_id}
                className="rounded-lg border border-slate-200 p-4"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-slate-900">{entry.summary}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-500">
                      <span className="font-mono">{entry.memory_id}</span>
                      <span>Task: {entry.task_id}</span>
                      <span>
                        Created: {new Date(entry.created_at).toLocaleString()}
                      </span>
                      <span>Retention: {entry.retention_days} days</span>
                      {entry.approved_at && (
                        <span className="text-emerald-600">
                          Approved: {new Date(entry.approved_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => handleDelete(entry.memory_id)}
                    loading={deletingId === entry.memory_id}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Empty state after search */}
      {results.length === 0 && query && !loading && !error && (
        <Card>
          <p className="text-center text-sm text-slate-500">
            No memory entries found for &ldquo;{query}&rdquo;
          </p>
        </Card>
      )}
    </div>
  );
}
