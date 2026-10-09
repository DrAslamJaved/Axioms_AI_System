"use client";

import Link from "next/link";
import { useAuth } from "@/contexts/auth";

export function Header() {
  const { approverName, connected } = useAuth();

  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6">
      <div />
      <div className="flex items-center gap-4">
        {connected && approverName && (
          <span className="text-sm text-slate-600">
            Signed in as <span className="font-medium text-slate-900">{approverName}</span>
          </span>
        )}
        <Link
          href="/settings"
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 transition-colors hover:bg-slate-50"
        >
          Settings
        </Link>
      </div>
    </header>
  );
}
