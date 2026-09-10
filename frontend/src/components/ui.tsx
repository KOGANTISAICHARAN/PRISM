"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import type { RiskFactors, TimelineStep } from "@/lib/types";

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-8 text-sm text-slate-500">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-prism-600" />
      {label ?? "Loading…"}
    </div>
  );
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
      <p className="font-semibold">Something went wrong</p>
      <p className="mt-1">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn-secondary mt-3 py-2">
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
      <p className="text-base font-semibold text-slate-700">{title}</p>
      <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">{body}</p>
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function DemoBadge({ className = "" }: { className?: string }) {
  return (
    <span className={`chip bg-amber-100 text-amber-800 ${className}`} title="Synthetic data for demonstration">
      DEMO DATA
    </span>
  );
}

export function AIDisclaimer({ text, compact = false }: { text?: string; compact?: boolean }) {
  return (
    <p className={`rounded-xl bg-slate-100 p-3 text-slate-600 ${compact ? "text-[11px] leading-4" : "text-xs"}`}>
      <span className="font-semibold">AI-generated assessment. </span>
      {text ??
        "AI visual analysis is indicative only and does not confirm contamination or establish legal responsibility. Further inspection may be required. A human inspector makes all decisions."}
    </p>
  );
}

const STATUS_STYLES: Record<string, string> = {
  NEW: "bg-slate-100 text-slate-700",
  UNDER_REVIEW: "bg-sky-100 text-sky-800",
  INVESTIGATION_REQUIRED: "bg-amber-100 text-amber-800",
  VERIFIED: "bg-emerald-100 text-emerald-800",
  NOT_VERIFIED: "bg-slate-200 text-slate-700",
  ACTIONED: "bg-emerald-600 text-white",
  CLOSED: "bg-slate-800 text-white",
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return (
    <span className={`chip ${STATUS_STYLES[status] ?? "bg-slate-100 text-slate-700"}`}>
      {label ?? status.replaceAll("_", " ")}
    </span>
  );
}

export function PriorityBadge({ band }: { band: string }) {
  const styles: Record<string, string> = {
    HIGH: "bg-rose-100 text-rose-700",
    MEDIUM: "bg-amber-100 text-amber-800",
    LOW: "bg-emerald-100 text-emerald-700",
  };
  return <span className={`chip ${styles[band] ?? "bg-slate-100 text-slate-700"}`}>{band} PRIORITY</span>;
}

export function RiskMeter({ score, band, compact = false }: { score: number; band: string; compact?: boolean }) {
  const color = score >= 70 ? "bg-rose-500" : score >= 40 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div className="w-full">
      <div className="flex items-baseline justify-between">
        <span className={`font-bold ${compact ? "text-lg" : "text-3xl"}`}>
          {score}
          <span className="text-sm font-medium text-slate-400">/100</span>
        </span>
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{band} risk signal</span>
      </div>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.max(score, 3)}%` }} />
      </div>
    </div>
  );
}

export function RiskFactorList({ factors }: { factors: RiskFactors }) {
  return (
    <div className="space-y-3">
      <ul className="space-y-1 text-sm text-slate-700">
        {factors.explanations?.map((e) => (
          <li key={e} className="flex gap-2">
            <span className="text-prism-600">•</span>
            {e}
          </li>
        ))}
      </ul>
      <div className="space-y-2">
        <p className="section-title">How the score was calculated</p>
        {factors.components?.map((c) => (
          <div key={c.key} className="flex items-center gap-3 text-xs">
            <span className="w-40 shrink-0 text-slate-600">
              {c.label} <span className="text-slate-400">({c.weight_pct}%)</span>
            </span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
              <div className="h-full rounded-full bg-prism-500" style={{ width: `${c.normalised * 100}%` }} />
            </div>
            <span className="w-12 text-right font-mono text-slate-500">+{c.contribution}</span>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-slate-500">{factors.disclaimer}</p>
    </div>
  );
}

export function Timeline({ steps }: { steps: TimelineStep[] }) {
  return (
    <ol className="space-y-3">
      {steps.map((s) => (
        <li key={s.status + s.label} className="flex items-start gap-3">
          <span
            className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
              s.state === "done"
                ? "bg-emerald-500 text-white"
                : s.state === "current"
                  ? "bg-prism-600 text-white"
                  : "border border-slate-300 bg-white text-slate-400"
            }`}
          >
            {s.state === "done" ? "✓" : s.state === "current" ? "●" : "○"}
          </span>
          <span
            className={`text-sm ${
              s.state === "pending" ? "text-slate-400" : s.state === "current" ? "font-semibold text-slate-900" : "text-slate-700"
            }`}
          >
            {s.label}
          </span>
        </li>
      ))}
    </ol>
  );
}

export function StatCard({
  label,
  value,
  hint,
  tone = "default",
  href,
}: {
  label: string;
  value: number | string;
  hint?: string;
  tone?: "default" | "danger" | "warning" | "success";
  href?: string;
}) {
  const tones = {
    default: "border-slate-200",
    danger: "border-rose-200 bg-rose-50",
    warning: "border-amber-200 bg-amber-50",
    success: "border-emerald-200 bg-emerald-50",
  };
  const inner = (
    <div className={`rounded-2xl border bg-white p-4 shadow-sm transition hover:shadow ${tones[tone]}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-3xl font-bold text-slate-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

export function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <p className="label">{label}</p>
      <p className="text-sm font-medium text-slate-900">{value || <span className="text-slate-400">Not provided</span>}</p>
    </div>
  );
}

export function formatDateTime(value?: string | null) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function timeAgo(value?: string | null) {
  if (!value) return "";
  const diff = Date.now() - new Date(value).getTime();
  const mins = Math.round(diff / 60000);
  if (mins < 60) return `${Math.max(mins, 1)}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}
