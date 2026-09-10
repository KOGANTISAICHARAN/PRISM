"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { TopBar } from "@/components/Shell";
import {
  AIDisclaimer,
  DemoBadge,
  ErrorNote,
  Field,
  PriorityBadge,
  RiskFactorList,
  RiskMeter,
  Spinner,
  StatusBadge,
  formatDateTime,
  timeAgo,
} from "@/components/ui";
import { api, evidenceUrl } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { CaseDetail, EvidenceRecord, InvestigationRecord, RiskFactors } from "@/lib/types";

const CHECKLIST_LABELS: Record<string, string> = {
  visit_establishment: "Visit Establishment Site",
  verify_licence_details: "Verify Business / FSSAI Licence Details",
  inspect_kitchen_hygiene: "Inspect Kitchen & Preparation Hygiene",
  inspect_storage_conditions: "Inspect Food Storage & Temperature Logs",
  inspect_food_handling: "Inspect Staff Food Handling Practices",
  record_observations: "Record Inspector Observations & Findings",
  collect_inspection_evidence: "Collect & Upload Inspection Evidence",
  determine_further_investigation: "Determine Administrative / Compliance Action",
};

const DECISION_OPTIONS = [
  { value: "VERIFIED", label: "Verified (Reported issue confirmed during inspection)" },
  { value: "NOT_VERIFIED", label: "Not Verified (Issue not confirmed during inspection)" },
  { value: "ACTIONED", label: "Actioned (Formal notice / corrective action recorded)" },
  { value: "CLOSED", label: "Closed (Case closed without further action)" },
];

export default function InspectorCaseDetailPage() {
  const { loading: authLoading } = useRequireAuth("inspector");
  const params = useParams();
  const caseId = params?.id as string;

  const [caseData, setCaseData] = useState<CaseDetail | null>(null);
  const [busy, setBusy] = useState(true);
  const [actionBusy, setActionBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Verification Hash State
  const [verifyingHash, setVerifyingHash] = useState<Record<string, boolean>>({});
  const [verifiedResults, setVerifiedResults] = useState<
    Record<string, { recorded_hash: string; recomputed_hash: string; integrity_verified: boolean }>
  >({});

  // Investigation & Decision State
  const [activeInvestigation, setActiveInvestigation] = useState<InvestigationRecord | null>(null);
  const [inspectorNotes, setInspectorNotes] = useState("");
  const [findingsInput, setFindingsInput] = useState("");
  const [decisionStatus, setDecisionStatus] = useState("VERIFIED");
  const [decisionNoteInput, setDecisionNoteInput] = useState("");
  const [inspectionFile, setInspectionFile] = useState<File | null>(null);
  const [showDecisionConfirm, setShowDecisionConfirm] = useState(false);

  const loadCaseData = useCallback(async () => {
    if (!caseId) return;
    setBusy(true);
    setError(null);
    try {
      const data = await api.inspectorCase(caseId);
      setCaseData(data);

      // Auto mark under review if status is NEW
      if (data.report.status === "NEW") {
        await api.markUnderReview(data.report.id);
        const refreshed = await api.inspectorCase(caseId);
        setCaseData(refreshed);
      }

      // Check active investigation
      const invs = data.investigations || [];
      if (invs.length > 0) {
        const latestInv = invs[invs.length - 1];
        setActiveInvestigation(latestInv);
        setInspectorNotes(latestInv.notes || "");
        setFindingsInput(latestInv.findings || "");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load case details");
    } finally {
      setBusy(false);
    }
  }, [caseId]);

  useEffect(() => {
    if (!authLoading && caseId) {
      loadCaseData();
    }
  }, [authLoading, caseId, loadCaseData]);

  async function handleVerifyEvidence(evidenceId: string) {
    setVerifyingHash((prev) => ({ ...prev, [evidenceId]: true }));
    try {
      const res = await api.verifyEvidence(evidenceId);
      setVerifiedResults((prev) => ({ ...prev, [evidenceId]: res }));
    } catch {
      // Ignore
    } finally {
      setVerifyingHash((prev) => ({ ...prev, [evidenceId]: false }));
    }
  }

  async function handleStartInvestigation() {
    if (!caseData) return;
    setActionBusy(true);
    setError(null);
    try {
      const inv = await api.startInvestigation(caseData.report.id, "Site inspection initiated.");
      setActiveInvestigation(inv);
      setInspectorNotes(inv.notes || "");
      setActionSuccess("Investigation initiated successfully.");
      const refreshed = await api.inspectorCase(caseId);
      setCaseData(refreshed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to initiate investigation");
    } finally {
      setActionBusy(false);
    }
  }

  async function handleToggleChecklist(itemKey: string, currentVal: boolean) {
    if (!activeInvestigation) return;
    setActionBusy(true);
    setError(null);
    try {
      const updated = await api.updateInvestigation(activeInvestigation.id, {
        checklist: { [itemKey]: !currentVal },
      });
      setActiveInvestigation(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update checklist");
    } finally {
      setActionBusy(false);
    }
  }

  async function handleSaveNotes() {
    if (!activeInvestigation) return;
    setActionBusy(true);
    setError(null);
    setActionSuccess(null);
    try {
      const updated = await api.updateInvestigation(activeInvestigation.id, {
        notes: inspectorNotes,
        findings: findingsInput,
      });
      setActiveInvestigation(updated);
      setActionSuccess("Investigator notes and findings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save notes");
    } finally {
      setActionBusy(false);
    }
  }

  async function handleUploadInspectionEvidence(e: React.FormEvent) {
    e.preventDefault();
    if (!activeInvestigation || !inspectionFile) return;

    setActionBusy(true);
    setError(null);
    setActionSuccess(null);
    try {
      await api.uploadInspectionEvidence(activeInvestigation.id, inspectionFile, "inspection_photo");
      setInspectionFile(null);
      setActionSuccess("Inspection evidence uploaded & SHA-256 hash recorded.");
      const refreshed = await api.inspectorCase(caseId);
      setCaseData(refreshed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload inspection evidence");
    } finally {
      setActionBusy(false);
    }
  }

  async function handleRecordDecisionSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!activeInvestigation || !decisionNoteInput.trim()) return;

    setActionBusy(true);
    setError(null);
    setActionSuccess(null);
    try {
      await api.recordDecision(activeInvestigation.id, {
        status: decisionStatus,
        decision_note: decisionNoteInput.trim(),
        findings: findingsInput.trim() || undefined,
      });

      setShowDecisionConfirm(false);
      setActionSuccess(`Case decision recorded: ${decisionStatus}. Case updated.`);
      const refreshed = await api.inspectorCase(caseId);
      setCaseData(refreshed);
      if (refreshed.investigations?.length) {
        setActiveInvestigation(refreshed.investigations[refreshed.investigations.length - 1]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record decision");
    } finally {
      setActionBusy(false);
    }
  }

  if (authLoading || (busy && !caseData)) {
    return (
      <main className="min-h-screen bg-slate-100">
        <TopBar title="Case Investigation" back="/inspector" />
        <div className="py-16">
          <Spinner label="Loading case investigation workspace…" />
        </div>
      </main>
    );
  }

  if (error && !caseData) {
    return (
      <main className="min-h-screen bg-slate-100">
        <TopBar title="Case Investigation" back="/inspector" />
        <div className="mx-auto max-w-xl px-4 py-8">
          <ErrorNote message={error || "Case not found"} onRetry={loadCaseData} />
          <div className="mt-4 text-center">
            <Link href="/inspector" className="btn-secondary inline-block px-4 py-2 text-xs">
              ← Back to Inspector Dashboard
            </Link>
          </div>
        </div>
      </main>
    );
  }

  const { report, vendor, risk, vendor_reports, cluster, similar_reports, hotspots } = caseData!;
  const priorityBand = risk?.band || "LOW";
  const priorityScore = risk?.score || 0;

  return (
    <main className="min-h-screen bg-slate-100 pb-20">
      <TopBar title={`Case ${report.reference}`} back="/inspector" />

      <div className="mx-auto max-w-5xl px-4 py-6 space-y-6">
        {/* Banner Alert Feedback */}
        {actionSuccess && (
          <div className="rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-xs font-semibold text-emerald-800 flex justify-between items-center">
            <span>✓ {actionSuccess}</span>
            <button type="button" onClick={() => setActionSuccess(null)} className="text-emerald-600 hover:underline">
              Dismiss
            </button>
          </div>
        )}

        {error && <ErrorNote message={error} onRetry={loadCaseData} />}

        {/* Case Header Card */}
        <div className="card space-y-4 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xl font-bold text-slate-900">{report.reference}</span>
                <PriorityBadge band={priorityBand} />
                <StatusBadge status={report.status} label={report.status_label} />
                {report.is_demo && <DemoBadge />}
              </div>
              <h1 className="mt-1 text-lg font-bold text-slate-900">{report.vendor_name}</h1>
              <p className="text-xs text-slate-500">
                Category: <span className="font-semibold text-slate-800">{report.issue_label}</span> • Area:{" "}
                <span className="font-semibold text-slate-800">{report.area || report.location_text || "Unspecified"}</span>
              </p>
            </div>

            <div className="w-full sm:w-56">
              <RiskMeter score={priorityScore} band={priorityBand} compact />
            </div>
          </div>

          <AIDisclaimer text="PRISM decision-support workspace. Risk scores and visual signals prioritize cases for inspection. Human inspectors remain responsible for all findings, evidence validation, and official enforcement decisions." />
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* LEFT 2 COLUMNS: Case Summary, Evidence, AI, Risk, Cluster */}
          <div className="lg:col-span-2 space-y-6">
            {/* Section 1: Case Summary */}
            <div className="card space-y-3 bg-white">
              <h2 className="text-base font-bold text-slate-900">1. Case & Establishment Profile</h2>

              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Establishment / Vendor" value={vendor?.name || report.vendor_name} />
                <Field label="Licence Reference" value={vendor?.licence_ref || "Unverified / Demo Licence"} />
                <Field label="Address / Area" value={vendor?.address || report.location_text || report.area} />
                <Field label="Food Item" value={report.food_item} />
                <Field label="Issue Category" value={report.issue_label} />
                <Field label="Incident Datetime" value={formatDateTime(report.incident_datetime)} />
                <Field label="Submitted On" value={formatDateTime(report.created_at)} />
                {report.reporter && (
                  <Field label="Reporter (Authorised Access)" value={`${report.reporter.name} (${report.reporter.email})`} />
                )}
              </div>

              <div>
                <p className="label">Citizen Description Narrative</p>
                <p className="rounded-xl bg-slate-50 p-3 text-xs leading-relaxed text-slate-700 font-medium">
                  &quot;{report.user_description || "No description provided."}&quot;
                </p>
              </div>

              {vendor_reports && vendor_reports.length > 1 && (
                <div className="pt-2 border-t border-slate-100">
                  <p className="text-xs font-bold text-slate-700">
                    Establishment Complaint History ({vendor_reports.length} total reports associated)
                  </p>
                  <p className="text-[11px] text-slate-500">
                    {vendor_reports.filter((r) => r.status === "VERIFIED" || r.status === "ACTIONED").length} verified or actioned in past history.
                  </p>
                </div>
              )}
            </div>

            {/* Section 2: Evidence Vault */}
            <div className="card space-y-4 bg-white">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-bold text-slate-900">2. Evidence Vault & Integrity Records</h2>
                <span className="chip bg-emerald-100 text-emerald-800 text-[11px] font-semibold">
                  {report.evidence?.length || 0} File(s) Preserved
                </span>
              </div>

              {(!report.evidence || report.evidence.length === 0) ? (
                <p className="text-xs text-slate-500">No evidence files attached to this case yet.</p>
              ) : (
                <div className="space-y-4 divide-y divide-slate-100">
                  {report.evidence.map((e: EvidenceRecord) => {
                    const verified = verifiedResults[e.id];
                    const isVerifying = verifyingHash[e.id];

                    return (
                      <div key={e.id} className="pt-4 first:pt-0 space-y-3">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-bold text-slate-800">
                            [{e.kind.replaceAll("_", " ").toUpperCase()}] {e.file_name}
                          </span>
                          <span className="text-slate-400">
                            Uploaded by {e.uploader_role} • {(e.file_size / 1024).toFixed(1)} KB
                          </span>
                        </div>

                        {/* Image Preview */}
                        {e.file_type.startsWith("image/") || e.file_type.includes("image") ? (
                          <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={evidenceUrl(e.file_url)}
                              alt={e.file_name}
                              className="max-h-64 w-full object-contain mx-auto"
                            />
                          </div>
                        ) : null}

                        {/* SHA-256 Hash Digest */}
                        <div className="rounded-xl bg-slate-900 p-3 text-white space-y-1">
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="font-semibold text-slate-400">SHA-256 Immutable Hash</span>
                            <span className="text-slate-400">{formatDateTime(e.uploaded_at)}</span>
                          </div>
                          <p className="font-mono text-[11px] text-emerald-400 break-all select-all">{e.sha256_hash}</p>
                        </div>

                        {/* Verification Button */}
                        <div>
                          {verified ? (
                            <div className="flex items-center gap-2 rounded-xl bg-emerald-50 border border-emerald-200 p-2.5 text-xs text-emerald-800">
                              <span className="font-bold text-emerald-600">✓ SHA-256 Verified</span>
                              <span className="text-[11px] text-emerald-700">
                                Recomputed bytes match recorded hash. Recorded: {verified.recorded_hash.slice(0, 12)}…
                              </span>
                            </div>
                          ) : (
                            <button
                              type="button"
                              onClick={() => handleVerifyEvidence(e.id)}
                              disabled={isVerifying}
                              className="btn-secondary w-full py-2 text-xs"
                            >
                              {isVerifying ? "Recomputing SHA-256 digest…" : "Verify SHA-256 Integrity"}
                            </button>
                          )}
                        </div>

                        {/* Audit Log Events */}
                        {e.audit_log && e.audit_log.length > 0 && (
                          <div className="rounded-xl bg-slate-50 p-2.5 text-[11px] space-y-1">
                            <p className="font-semibold text-slate-600">Append-Only Audit Trail</p>
                            {e.audit_log.map((a) => (
                              <div key={a.id} className="flex items-center justify-between text-slate-500">
                                <span>
                                  • <strong className="text-slate-700">{a.action}</strong> by {a.actor}
                                </span>
                                <span>{timeAgo(a.timestamp)}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Section 3: AI Analysis */}
            {report.ai_assessments && report.ai_assessments.length > 0 && (
              <div className="card space-y-3 bg-gradient-to-b from-prism-50/50 to-white border-prism-200">
                <h2 className="text-base font-bold text-slate-900">3. AI Visual Analysis Signal</h2>
                {report.ai_assessments.map((a) => (
                  <div key={a.id} className="space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-prism-800">{a.detected_issue}</span>
                      <span className="chip bg-prism-100 text-prism-800">
                        {a.risk_level} Risk ({(a.confidence * 100).toFixed(0)}% confidence)
                      </span>
                    </div>
                    <p className="text-xs leading-relaxed text-slate-700">{a.explanation}</p>
                    <p className="text-[11px] text-slate-400">Model: {a.model}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Section 4: Risk Analysis */}
            {risk && (
              <div className="card space-y-4 bg-white">
                <h2 className="text-base font-bold text-slate-900">4. Explainable Risk Engine Signal</h2>
                <RiskMeter score={risk.score} band={risk.band} />
                <RiskFactorList factors={risk.factors as RiskFactors} />
              </div>
            )}

            {/* Section 5: Complaint Clusters & Similar Reports */}
            <div className="card space-y-4 bg-white">
              <h2 className="text-base font-bold text-slate-900">5. Related Complaints & Semantic Cluster</h2>

              {cluster ? (
                <div className="rounded-xl border border-sky-200 bg-sky-50/50 p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm font-bold text-sky-800">Cluster {cluster.label}</span>
                    <span className="chip bg-sky-100 text-sky-800 font-semibold">{cluster.report_count} Related Reports</span>
                  </div>
                  <p className="text-xs font-bold text-slate-900">{cluster.theme}</p>
                  <p className="text-[11px] text-slate-600">
                    Clustering identifies potentially related reports using DBSCAN cosine distance over complaint embeddings.
                  </p>
                </div>
              ) : (
                <p className="text-xs text-slate-500">No related complaint cluster identified for this report.</p>
              )}

              {/* Similar Reports List */}
              {similar_reports && similar_reports.length > 0 && (
                <div className="space-y-2 pt-2">
                  <p className="text-xs font-bold text-slate-800">
                    Semantically Similar Reports ({similar_reports.length})
                  </p>
                  <div className="space-y-2">
                    {similar_reports.map((sr) => (
                      <Link
                        key={sr.id}
                        href={`/inspector/cases/${sr.id}`}
                        className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs transition hover:bg-slate-100"
                      >
                        <div>
                          <p className="font-mono font-bold text-slate-900">{sr.reference}</p>
                          <p className="text-slate-600">{sr.vendor_name} • {sr.issue_label}</p>
                        </div>
                        <span className="chip bg-prism-100 text-prism-800 font-semibold">
                          {(sr.similarity! * 100).toFixed(0)}% Similar →
                        </span>
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              {/* Nearby Hotspot Warnings */}
              {hotspots && hotspots.length > 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 space-y-1">
                  <p className="font-bold">⚠️ Nearby Geo-Cell Hotspot Alert</p>
                  <p>
                    Area <span className="font-semibold">{hotspots[0].area}</span> is currently an active {hotspots[0].level} cell with {hotspots[0].report_count} reports.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* RIGHT 1 COLUMN: Investigation Workspace & Human Decision */}
          <div className="space-y-6">
            {/* Section 6: Investigation Workspace */}
            <div className="card space-y-4 bg-white border-l-4 border-l-prism-600">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-bold text-slate-900">6. Investigation Workspace</h2>
                <StatusBadge status={report.status} />
              </div>

              {!activeInvestigation ? (
                <div className="space-y-3">
                  <p className="text-xs text-slate-600">
                    No active inspection record initiated yet. Start an investigation to begin site checklist verification.
                  </p>
                  <button
                    type="button"
                    onClick={handleStartInvestigation}
                    disabled={actionBusy}
                    className="btn-primary w-full py-2.5 text-xs font-bold"
                  >
                    {actionBusy ? "Initiating Inspection…" : "Start Inspection"}
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Inspection Info */}
                  <div className="rounded-xl bg-slate-50 p-3 text-xs space-y-1">
                    <p className="font-bold text-slate-800">Inspector: {activeInvestigation.inspector_name}</p>
                    <p className="text-slate-500">Status: {activeInvestigation.status}</p>
                    <p className="text-slate-500">Initiated: {formatDateTime(activeInvestigation.created_at)}</p>
                  </div>

                  {/* 8-Item Inspection Checklist */}
                  <div className="space-y-2">
                    <p className="text-xs font-bold text-slate-800">8-Item Inspection Checklist</p>
                    <div className="space-y-1.5">
                      {Object.keys(CHECKLIST_LABELS).map((key) => {
                        const isChecked = Boolean(activeInvestigation.checklist?.[key]);

                        return (
                          <label
                            key={key}
                            className={`flex items-start gap-2.5 rounded-xl border p-2.5 text-xs cursor-pointer transition ${
                              isChecked
                                ? "border-emerald-300 bg-emerald-50/60 text-emerald-900 font-semibold"
                                : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={isChecked}
                              disabled={actionBusy}
                              onChange={() => handleToggleChecklist(key, isChecked)}
                              className="mt-0.5 h-4 w-4 rounded border-slate-300 text-prism-600 focus:ring-prism-500"
                            />
                            <span>{CHECKLIST_LABELS[key]}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>

                  {/* Inspector Notes Editor */}
                  <div className="space-y-2">
                    <label className="label" htmlFor="inspectorNotes">
                      Investigator Notes & Observations
                    </label>
                    <textarea
                      id="inspectorNotes"
                      rows={4}
                      className="input text-xs resize-none"
                      placeholder="Record site visit observations, storage temperatures, hygiene findings, or licence checks…"
                      value={inspectorNotes}
                      onChange={(e) => setInspectorNotes(e.target.value)}
                    />

                    <label className="label" htmlFor="findingsInput">
                      Formal Inspection Findings
                    </label>
                    <textarea
                      id="findingsInput"
                      rows={2}
                      className="input text-xs resize-none"
                      placeholder="Summary of official findings…"
                      value={findingsInput}
                      onChange={(e) => setFindingsInput(e.target.value)}
                    />

                    <button
                      type="button"
                      onClick={handleSaveNotes}
                      disabled={actionBusy}
                      className="btn-secondary w-full py-2 text-xs"
                    >
                      {actionBusy ? "Saving…" : "Save Notes & Findings"}
                    </button>
                  </div>

                  {/* Section 7: Upload Inspection Evidence */}
                  <form onSubmit={handleUploadInspectionEvidence} className="space-y-2 border-t border-slate-100 pt-3">
                    <label className="label">Upload Inspection Evidence</label>
                    <p className="text-[11px] text-slate-500">Attach site photos, inspection checklists, or official notices.</p>
                    <input
                      type="file"
                      accept="image/*,application/pdf"
                      onChange={(e) => setInspectionFile(e.target.files?.[0] || null)}
                      className="input py-1 text-xs"
                    />
                    <button
                      type="submit"
                      disabled={actionBusy || !inspectionFile}
                      className="btn-secondary w-full py-2 text-xs"
                    >
                      {actionBusy ? "Uploading…" : "Upload Inspection File & Hash"}
                    </button>
                  </form>
                </div>
              )}
            </div>

            {/* Section 8: Human Decision & Case Resolution */}
            {activeInvestigation && (
              <div className="card space-y-4 bg-white border-l-4 border-l-emerald-600">
                <h2 className="text-base font-bold text-slate-900">7. Record Human Case Decision</h2>
                <p className="text-xs text-slate-500">
                  Record the final human decision. AI signals do not establish guilt or set official case statuses.
                </p>

                <form onSubmit={handleRecordDecisionSubmit} className="space-y-3">
                  <div>
                    <label className="label" htmlFor="decisionStatus">
                      Select Final Status *
                    </label>
                    <select
                      id="decisionStatus"
                      className="input bg-white text-xs font-semibold"
                      value={decisionStatus}
                      onChange={(e) => setDecisionStatus(e.target.value)}
                    >
                      {DECISION_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="label" htmlFor="decisionNoteInput">
                      Decision Note / Rationale *
                    </label>
                    <textarea
                      id="decisionNoteInput"
                      rows={3}
                      className="input text-xs resize-none"
                      required
                      placeholder="Provide explanation for this official decision…"
                      value={decisionNoteInput}
                      onChange={(e) => setDecisionNoteInput(e.target.value)}
                    />
                  </div>

                  {!showDecisionConfirm ? (
                    <button
                      type="button"
                      onClick={() => setShowDecisionConfirm(true)}
                      disabled={!decisionNoteInput.trim()}
                      className="btn-primary w-full py-2.5 text-xs font-bold bg-emerald-600 hover:bg-emerald-700"
                    >
                      Record Final Decision →
                    </button>
                  ) : (
                    <div className="rounded-xl border border-rose-300 bg-rose-50 p-3 space-y-2 text-xs text-rose-900">
                      <p className="font-bold">Confirm Human Inspector Decision</p>
                      <p>
                        Are you sure you want to mark this case as <strong className="uppercase">{decisionStatus}</strong>? This decision will update the citizen timeline.
                      </p>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setShowDecisionConfirm(false)}
                          className="btn-secondary flex-1 py-1.5 text-xs"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          disabled={actionBusy}
                          className="btn-primary flex-1 py-1.5 text-xs bg-rose-600 hover:bg-rose-700 font-bold"
                        >
                          {actionBusy ? "Submitting…" : "Confirm Decision"}
                        </button>
                      </div>
                    </div>
                  )}
                </form>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
