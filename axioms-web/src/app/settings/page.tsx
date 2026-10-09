"use client";

import { useState } from "react";
import { Card, CardTitle, CardDescription } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/contexts/auth";

export default function SettingsPage() {
  const {
    apiKey,
    setApiKey,
    approverName,
    setApproverName,
    allowExternalProvider,
    setAllowExternalProvider,
    connected,
  } = useAuth();

  const [keyInput, setKeyInput] = useState(apiKey);
  const [nameInput, setNameInput] = useState(approverName);
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setApiKey(keyInput);
    setApproverName(nameInput);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
        <p className="mt-1 text-sm text-slate-500">
          Configure your connection to the Axioms API backend
        </p>
      </div>

      {/* Connection status */}
      <Card>
        <div className="flex items-center gap-3">
          <div
            className={`h-3 w-3 rounded-full ${
              connected ? "bg-emerald-500" : "bg-red-400"
            }`}
          />
          <div>
            <p className="text-sm font-medium text-slate-900">
              {connected ? "Connected" : "Not connected"}
            </p>
            <p className="text-xs text-slate-500">
              {connected
                ? "API backend is reachable and authenticated"
                : "Enter your API key below to connect"}
            </p>
          </div>
        </div>
      </Card>

      {/* API Configuration */}
      <Card>
        <CardTitle>API Configuration</CardTitle>
        <CardDescription>
          Your API key authenticates requests to the Axioms backend. It is stored
          locally in your browser.
        </CardDescription>
        <div className="mt-4 space-y-4">
          <Input
            label="API Key"
            type="password"
            placeholder="Enter your Axioms API key"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            hint="Sent as X-API-Key header with every request"
          />
          <Input
            label="Approver Name"
            placeholder="Your name (used for approvals)"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            hint="Identifies you when approving or rejecting tasks"
          />
          <div className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-slate-900">
                Allow External LLM Provider
              </p>
              <p className="text-xs text-slate-500">
                When enabled, agents may use external AI providers (e.g., OpenAI)
                alongside the primary model
              </p>
            </div>
            <button
              role="switch"
              aria-checked={allowExternalProvider}
              onClick={() => setAllowExternalProvider(!allowExternalProvider)}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-axiom-500 focus:ring-offset-2 ${
                allowExternalProvider ? "bg-axiom-600" : "bg-slate-200"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                  allowExternalProvider ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
          <div className="flex items-center gap-3 pt-2">
            <Button onClick={handleSave}>Save Settings</Button>
            {saved && (
              <span className="text-sm text-emerald-600">Settings saved</span>
            )}
          </div>
        </div>
      </Card>

      {/* Backend Info */}
      <Card>
        <CardTitle>Backend URL</CardTitle>
        <CardDescription>
          The API backend URL is configured via the NEXT_PUBLIC_API_URL
          environment variable. Current value:
        </CardDescription>
        <div className="mt-3 rounded-md bg-slate-50 px-4 py-2">
          <code className="text-sm text-slate-700">
            {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}
          </code>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          To change the backend URL, update the NEXT_PUBLIC_API_URL environment
          variable and restart the application.
        </p>
      </Card>
    </div>
  );
}
