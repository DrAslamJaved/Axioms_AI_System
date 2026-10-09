"use client";

import { clsx } from "clsx";
import { STATUS_COLORS, type TaskStatus } from "@/lib/types";

interface BadgeProps {
  status: TaskStatus;
  className?: string;
}

export function StatusBadge({ status, className }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
        STATUS_COLORS[status],
        className
      )}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

interface RiskBadgeProps {
  tier: string;
  className?: string;
}

const riskColors: Record<string, string> = {
  low: "bg-green-100 text-green-800",
  elevated: "bg-yellow-100 text-yellow-800",
  high: "bg-red-100 text-red-800",
};

export function RiskBadge({ tier, className }: RiskBadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
        riskColors[tier] ?? "bg-slate-100 text-slate-700",
        className
      )}
    >
      {tier} risk
    </span>
  );
}
