"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { TopBar } from "@/components/Shell";
import { DemoBadge, EmptyState, ErrorNote, Spinner, StatusBadge, formatDateTime, timeAgo } from "@/components/ui";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { ReportSummary } from "@/lib/types";

export default function MyReportsPage() {
  const { loading: authLoading } = useRequireAuth("citizen");
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadReports = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await api.myReports();
      setReports(data.reports);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load your reports");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading) {
      loadReports();
    }
  }, [authLoading, loadReports]);

  if (authLoading || (busy && reports.length === 0)) {
    return (
      <main className="min-h-screen bg-slate-50">
        <TopBar title="My Reports" back="/" />
        <div className="py-12">
          <Spinner label="Loading your reports…" />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 pb-20">
      <TopBar title="My Reports" back="/" />

      <div className="mx-auto max-w-xl px-4 py-6">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900">Submitted Reports</h1>
            <p className="text-xs text-slate-500">Track status updates and inspection progress in real time.</p>
          </div>
          <Link href="/report" className="btn-primary px-3 py-2 text-xs">
            ＋ New Report
          </Link>
        </div>

        {error && (
          <div className="mb-4">
            <ErrorNote message={error} onRetry={loadReports} />
          </div>
        )}

        {!busy && reports.length === 0 && !error && (
          <EmptyState
            title="No reports submitted yet"
            body="When you report a food safety issue, it will appear here so you can track its status and review evidence integrity."
            action={
              <Link href="/report" className="btn-primary px-4 py-2.5 text-xs">
                Report a Food Safety Issue
              </Link>
            }
          />
        )}

        <div className="space-y-3">
          {reports.map((r) => (
            <Link
              key={r.id}
              href={`/reports/${r.reference || r.id}`}
              className="card block space-y-2 transition hover:shadow-md hover:border-prism-300"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-bold text-slate-900">{r.reference}</span>
                  {r.is_demo && <DemoBadge />}
                </div>
                <StatusBadge status={r.status} label={r.status_label} />
              </div>

              <div>
                <p className="text-sm font-semibold text-slate-900">{r.vendor_name}</p>
                <p className="text-xs text-slate-500">
                  {r.food_item ? `${r.food_item} • ` : ""}
                  {r.issue_label}
                </p>
              </div>

              {r.description_preview && (
                <p className="text-xs leading-relaxed text-slate-600 line-clamp-2">{r.description_preview}</p>
              )}

              <div className="flex items-center justify-between pt-1 text-[11px] text-slate-400">
                <span>{r.location_text || r.area || "Location not specified"}</span>
                <span>{r.incident_datetime ? formatDateTime(r.incident_datetime) : timeAgo(r.created_at)}</span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
