"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { TopBar } from "@/components/Shell";
import { AIDisclaimer, DemoBadge, ErrorNote, Field, Spinner, StatusBadge, Timeline, formatDateTime } from "@/components/ui";
import { api, evidenceUrl } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { ReportDetail } from "@/lib/types";

export default function ReportDetailPage() {
  const { loading: authLoading } = useRequireAuth("citizen");
  const params = useParams();
  const reportId = params?.id as string;

  const [report, setReport] = useState<ReportDetail | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // SHA-256 Integrity Verification State
  const [verifyingHash, setVerifyingHash] = useState<Record<string, boolean>>({});
  const [verifiedResults, setVerifiedResults] = useState<
    Record<string, { recorded_hash: string; recomputed_hash: string; integrity_verified: boolean }>
  >({});

  const loadReport = useCallback(async () => {
    if (!reportId) return;
    setBusy(true);
    setError(null);
    try {
      const data = await api.getReport(reportId);
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load report details");
    } finally {
      setBusy(false);
    }
  }, [reportId]);

  useEffect(() => {
    if (!authLoading && reportId) {
      loadReport();
    }
  }, [authLoading, reportId, loadReport]);

  async function handleVerifyEvidence(evidenceId: string) {
    setVerifyingHash((prev) => ({ ...prev, [evidenceId]: true }));
    try {
      const res = await api.verifyEvidence(evidenceId);
      setVerifiedResults((prev) => ({ ...prev, [evidenceId]: res }));
    } catch {
      // Ignore or set error
    } fontally: {
      setVerifyingHash((prev) => ({ ...prev, [evidenceId]: false }));
    }
  }

  if (authLoading || (busy && !report)) {
    return (
      <main className="min-h-screen bg-slate-50">
        <TopBar title="Report Details" back="/reports" />
        <div className="py-12">
          <Spinner label="Loading report details…" />
        </div>
      </main>
    );
  }

  if (error || !report) {
    return (
      <main className="min-h-screen bg-slate-50">
        <TopBar title="Report Details" back="/reports" />
        <div className="mx-auto max-w-xl px-4 py-8">
          <ErrorNote message={error || "Report not found or access denied"} onRetry={loadReport} />
          <div className="mt-4 text-center">
            <Link href="/reports" className="btn-secondary inline-block px-4 py-2 text-xs">
              ← Return to My Reports
            </Link>
          </div>
        </div>
      </main>
    );
  }

  const latestUpdate = report.updates?.[report.updates.length - 1];

  return (
    <main className="min-h-screen bg-slate-50 pb-20">
      <TopBar title={`Report ${report.reference}`} back="/reports" />

      <div className="mx-auto max-w-xl px-4 py-6 space-y-4">
        {/* Header Summary */}
        <div className="card space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xl font-bold text-slate-900">{report.reference}</span>
              {report.is_demo && <DemoBadge />}
            </div>
            <StatusBadge status={report.status} label={report.status_label} />
          </div>

          <div>
            <h1 className="text-lg font-bold text-slate-900">{report.vendor_name}</h1>
            <p className="text-xs text-slate-500">{report.issue_label}</p>
          </div>
        </div>

        {/* Status Timeline */}
        <div className="card space-y-4">
          <h2 className="text-base font-bold text-slate-900">Status Timeline</h2>

          {latestUpdate && (
            <div className="rounded-xl border border-sky-200 bg-sky-50/60 p-3 text-xs text-sky-900">
              <p className="font-semibold">Latest Update:</p>
              <p className="mt-0.5">{latestUpdate.message}</p>
              <p className="mt-1 text-[10px] text-sky-700">{formatDateTime(latestUpdate.timestamp)}</p>
            </div>
          )}

          <div className="pt-2">
            <Timeline steps={report.timeline} />
          </div>
        </div>

        {/* Report Details */}
        <div className="card space-y-3">
          <h2 className="text-base font-bold text-slate-900">Report Summary</h2>
          <Field label="Restaurant / Vendor" value={report.vendor_name} />
          <Field label="Food / Product Item" value={report.food_item} />
          <Field label="Issue Category" value={report.issue_label} />
          <Field label="Location" value={report.location_text || report.area} />
          <Field label="Incident Date & Time" value={formatDateTime(report.incident_datetime)} />
          <Field label="Description" value={report.user_description} />
          <Field label="Submitted On" value={formatDateTime(report.created_at)} />
        </div>

        {/* Evidence Vault */}
        {report.evidence && report.evidence.length > 0 && (
          <div className="card space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-slate-900">Evidence Vault</h2>
              <span className="chip bg-emerald-100 text-emerald-800 text-[11px] font-semibold">
                {report.evidence.length} File(s) Preserved
              </span>
            </div>

            <div className="space-y-4 divide-y divide-slate-100">
              {report.evidence.map((e) => {
                const verified = verifiedResults[e.id];
                const isVerifying = verifyingHash[e.id];

                return (
                  <div key={e.id} className="pt-3 first:pt-0 space-y-2">
                    {/* Media Preview if image */}
                    {e.file_type.startsWith("image/") && (
                      <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={evidenceUrl(e.file_url)}
                          alt={e.file_name}
                          className="max-h-56 w-full object-contain mx-auto"
                        />
                      </div>
                    )}

                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-800">{e.file_name}</span>
                      <span className="text-slate-400">{(e.file_size / 1024).toFixed(1)} KB</span>
                    </div>

                    {/* SHA-256 Integrity Box */}
                    <div className="rounded-xl bg-slate-100 p-2.5 space-y-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-semibold text-slate-600">SHA-256 Server Hash</span>
                        <span className="text-slate-400">Uploaded {formatDateTime(e.uploaded_at)}</span>
                      </div>
                      <p className="font-mono text-[11px] text-slate-800 break-all select-all font-medium">
                        {e.sha256_hash}
                      </p>
                    </div>

                    {/* Verification Action */}
                    <div>
                      {verified ? (
                        <div className="flex items-center gap-2 rounded-xl bg-emerald-50 border border-emerald-200 p-2.5 text-xs text-emerald-800">
                          <span className="font-bold text-emerald-600">✓ SHA-256 Verified</span>
                          <span className="text-[11px] text-emerald-700">Stored file bytes match recorded hash.</span>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleVerifyEvidence(e.id)}
                          disabled={isVerifying}
                          className="btn-secondary w-full py-2 text-xs"
                        >
                          {isVerifying ? "Recomputing SHA-256 hash…" : "Verify SHA-256 Integrity"}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* AI Assessments */}
        {report.ai_assessments && report.ai_assessments.length > 0 && (
          <div className="card space-y-3 border-prism-200 bg-gradient-to-b from-prism-50/30 to-white">
            <h2 className="text-base font-bold text-slate-900">AI Visual Signal</h2>
            {report.ai_assessments.map((a) => (
              <div key={a.id} className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-prism-700">{a.detected_issue}</span>
                  <span className="chip bg-prism-100 text-prism-800">{a.risk_level} Risk</span>
                </div>
                <p className="text-xs text-slate-600">{a.explanation}</p>
                <AIDisclaimer text={a.disclaimer} compact />
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
