"use client";

import Link from "next/link";
import { useState } from "react";

import { TopBar } from "@/components/Shell";
import { AIDisclaimer, ErrorNote, Field, Spinner, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { AssistantResult, EvidenceRecord, ReportDetail, VisionResult } from "@/lib/types";

const ISSUE_OPTIONS = [
  { value: "foreign_object", label: "Possible foreign object (plastic, metal, glass)" },
  { value: "mold_like_growth", label: "Possible mold-like growth" },
  { value: "pest_evidence", label: "Possible pest evidence (insects, rodents)" },
  { value: "spoilage_discoloration", label: "Possible spoilage / discoloration / bad smell" },
  { value: "packaging_damage", label: "Possible packaging damage / broken seal" },
  { value: "leakage", label: "Possible leakage / spillage" },
  { value: "hygiene_concern", label: "Possible hygiene / cleanliness concern" },
  { value: "other_visible_condition", label: "Other unusual visible condition" },
];

export default function ReportWizardPage() {
  const { loading: authLoading } = useRequireAuth("citizen");

  // Wizard Steps: 1 = Photo & Start, 2 = AI & Details, 3 = Review, 4 = Success
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);

  // Form State
  const [file, setFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [initialNote, setInitialNote] = useState("");

  // AI & Assistant State
  const [busy, setBusy] = useState(false);
  const [busyText, setBusyText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [visionResult, setVisionResult] = useState<VisionResult | null>(null);
  const [assistantResult, setAssistantResult] = useState<AssistantResult | null>(null);
  const [chatMessages, setChatMessages] = useState<{ role: string; content: string }[]>([]);
  const [answerInput, setAnswerInput] = useState("");

  // Slot Fields
  const [fields, setFields] = useState({
    vendor_name: "",
    food_item: "",
    issue_type: "foreign_object",
    user_description: "",
    incident_datetime: new Date().toISOString().slice(0, 16),
    location_text: "",
    area: "",
    evidence_available: "photo",
  });

  // Final Submitted Result
  const [createdReport, setCreatedReport] = useState<ReportDetail | null>(null);
  const [uploadedEvidence, setUploadedEvidence] = useState<EvidenceRecord | null>(null);
  const [copied, setCopied] = useState(false);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0];
    if (!selected) return;
    setFile(selected);
    const url = URL.createObjectURL(selected);
    setFilePreview(url);
  }

  async function handleAnalyzeAndStart() {
    setBusy(true);
    setBusyText("Analyzing image with PRISM AI…");
    setError(null);
    try {
      let vision: VisionResult | null = null;
      if (file) {
        vision = await api.analyzeImage(file, initialNote);
        setVisionResult(vision);
      }

      const initialMsgs = initialNote.trim()
        ? [{ role: "user", content: initialNote.trim() }]
        : [{ role: "user", content: "I would like to report a food safety issue." }];
      setChatMessages(initialMsgs);

      setBusyText("Structuring complaint…");
      const assistant = await api.structureComplaint({
        messages: initialMsgs,
        known_fields: vision?.issue_type ? { issue_type: vision.issue_type } : {},
        vision,
      });

      setAssistantResult(assistant);

      // Merge extracted fields into local form fields
      setFields((prev) => ({
        ...prev,
        vendor_name: (assistant.fields.vendor_name as string) || prev.vendor_name,
        food_item: (assistant.fields.food_item as string) || prev.food_item,
        issue_type: (assistant.fields.issue_type as string) || vision?.issue_type || prev.issue_type,
        user_description: initialNote.trim() || (assistant.fields.user_description as string) || prev.user_description,
        incident_datetime: (assistant.fields.incident_datetime as string) || prev.incident_datetime,
        location_text: (assistant.fields.location as string) || prev.location_text,
        area: (assistant.fields.location as string) || prev.area,
        evidence_available: file ? "photo" : "none",
      }));

      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to analyze report");
    } finally {
      setBusy(false);
    }
  }

  async function handleAnswerSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!answerInput.trim() || !assistantResult?.next_question) return;

    setBusy(true);
    setBusyText("Processing response…");
    setError(null);

    const updatedMsgs = [
      ...chatMessages,
      { role: "assistant", content: assistantResult.next_question },
      { role: "user", content: answerInput.trim() },
    ];
    setChatMessages(updatedMsgs);

    try {
      const res = await api.structureComplaint({
        messages: updatedMsgs,
        known_fields: { ...fields, ...assistantResult.fields },
        vision: visionResult,
      });

      setAssistantResult(res);
      setAnswerInput("");

      setFields((prev) => ({
        ...prev,
        vendor_name: (res.fields.vendor_name as string) || prev.vendor_name,
        food_item: (res.fields.food_item as string) || prev.food_item,
        issue_type: (res.fields.issue_type as string) || prev.issue_type,
        user_description: (res.fields.user_description as string) || prev.user_description,
        incident_datetime: (res.fields.incident_datetime as string) || prev.incident_datetime,
        location_text: (res.fields.location as string) || prev.location_text,
        area: (res.fields.location as string) || prev.area,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update response");
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmitReport() {
    setBusy(true);
    setBusyText("Submitting report to PRISM…");
    setError(null);

    try {
      // 1. Create Report
      const payload = {
        vendor_name: fields.vendor_name || "Unspecified Restaurant",
        food_item: fields.food_item || undefined,
        issue_type: fields.issue_type,
        user_description: fields.user_description || initialNote || "No additional description provided",
        incident_datetime: fields.incident_datetime || undefined,
        location_text: fields.location_text || undefined,
        area: fields.area || fields.location_text || undefined,
        evidence_available: file ? "photo" : "none",
        ai_assessment: visionResult,
      };

      const report = await api.createReport(payload);
      setCreatedReport(report);

      // 2. Upload Evidence File (SHA-256 Hashing)
      let evRecord: EvidenceRecord | null = null;
      if (file) {
        setBusyText("Uploading evidence & computing SHA-256 hash…");
        evRecord = await api.uploadEvidence(report.id, file, "citizen_photo");
        setUploadedEvidence(evRecord);
      }

      // 3. Finalize Report (Run Risk & Clustering Pass)
      setBusyText("Finalizing risk intelligence pass…");
      const finalized = await api.finalizeReport(report.id);
      setCreatedReport(finalized);

      setStep(4);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit report");
    } finally {
      setBusy(false);
    }
  }

  function copyReference() {
    if (!createdReport?.reference) return;
    navigator.clipboard.writeText(createdReport.reference);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (authLoading) return <Spinner label="Verifying session…" />;

  return (
    <main className="min-h-screen bg-slate-50 pb-16">
      <TopBar title="Report Food Safety Issue" back="/" />

      <div className="mx-auto max-w-xl px-4 py-6">
        {/* Progress Tracker */}
        <div className="mb-6 flex items-center justify-between rounded-2xl bg-white p-3.5 shadow-sm border border-slate-200">
          {[
            { stepNum: 1, label: "Photo & Note" },
            { stepNum: 2, label: "AI & Details" },
            { stepNum: 3, label: "Review" },
            { stepNum: 4, label: "Submitted" },
          ].map((s) => (
            <div key={s.stepNum} className="flex flex-col items-center gap-1">
              <span
                className={`grid h-7 w-7 place-items-center rounded-full text-xs font-bold transition-colors ${
                  step === s.stepNum
                    ? "bg-prism-600 text-white ring-4 ring-prism-100"
                    : step > s.stepNum
                      ? "bg-emerald-500 text-white"
                      : "bg-slate-100 text-slate-400"
                }`}
              >
                {step > s.stepNum ? "✓" : s.stepNum}
              </span>
              <span className={`text-[11px] font-medium ${step === s.stepNum ? "text-prism-700" : "text-slate-500"}`}>
                {s.label}
              </span>
            </div>
          ))}
        </div>

        {error && (
          <div className="mb-4">
            <ErrorNote message={error} onRetry={() => setError(null)} />
          </div>
        )}

        {/* STEP 1: PHOTO & INITIAL NOTE */}
        {step === 1 && (
          <div className="card space-y-5">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Step 1: Upload Photo & Describe Issue</h2>
              <p className="mt-1 text-xs text-slate-600">
                Upload a photo of the food item, bill, or visible issue. PRISM AI will analyze it automatically.
              </p>
            </div>

            {/* Photo Dropzone / Selector */}
            <div>
              <label className="label">Food Photo / Evidence</label>
              <div className="mt-1 flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50/50 p-6 text-center transition hover:border-prism-400">
                {filePreview ? (
                  <div className="relative w-full">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={filePreview}
                      alt="Uploaded food evidence preview"
                      className="mx-auto max-h-56 rounded-xl object-contain shadow-sm"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        setFile(null);
                        setFilePreview(null);
                      }}
                      className="mt-3 text-xs font-semibold text-rose-600 hover:underline"
                    >
                      Remove photo & choose another
                    </button>
                  </div>
                ) : (
                  <label className="cursor-pointer space-y-2">
                    <span className="grid h-12 w-12 place-items-center rounded-full bg-prism-50 text-2xl text-prism-600 mx-auto">
                      📷
                    </span>
                    <p className="text-sm font-semibold text-slate-700">Click to select or capture a photo</p>
                    <p className="text-xs text-slate-400">JPG, PNG, WEBP (Max 15MB)</p>
                    <input type="file" accept="image/*" className="hidden" onChange={handleFileChange} />
                  </label>
                )}
              </div>
            </div>

            {/* Initial Note */}
            <div>
              <label className="label" htmlFor="initialNote">
                What happened? (Short description)
              </label>
              <textarea
                id="initialNote"
                rows={3}
                className="input resize-none"
                placeholder="e.g. I found a plastic fragment in my chicken biryani ordered from ABC Restaurant in Banjara Hills"
                value={initialNote}
                onChange={(e) => setInitialNote(e.target.value)}
              />
            </div>

            <button
              type="button"
              className="btn-primary w-full py-3 text-sm"
              disabled={busy || (!file && !initialNote.trim())}
              onClick={handleAnalyzeAndStart}
            >
              {busy ? busyText : "Analyze & Continue →"}
            </button>
          </div>
        )}

        {/* STEP 2: AI ANALYSIS & DETAILS */}
        {step === 2 && (
          <div className="space-y-4">
            {/* AI Vision Observations Card */}
            {visionResult && (
              <div className="card border-prism-200 bg-gradient-to-b from-prism-50/50 to-white">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-prism-700">PRISM AI Vision Signal</span>
                  <span className="chip bg-prism-100 text-prism-800 font-semibold">{visionResult.risk_level} Risk</span>
                </div>
                <p className="mt-2 text-base font-bold text-slate-900">{visionResult.detected_issue}</p>
                <p className="mt-1 text-xs text-slate-600">{visionResult.explanation}</p>
                <div className="mt-3">
                  <AIDisclaimer text={visionResult.disclaimer} compact />
                </div>
              </div>
            )}

            {/* AI Slot Filling Assistant Q&A */}
            {assistantResult?.next_question && !assistantResult.complete && (
              <div className="card border-amber-200 bg-amber-50/40">
                <p className="text-xs font-bold text-amber-800 uppercase tracking-wide">AI Assistant Question</p>
                <p className="mt-1 text-sm font-semibold text-slate-900">{assistantResult.next_question}</p>
                {assistantResult.notice && (
                  <p className="mt-2 rounded-xl bg-amber-100 p-2.5 text-xs text-amber-900 font-medium">
                    {assistantResult.notice}
                  </p>
                )}
                <form onSubmit={handleAnswerSubmit} className="mt-3 flex gap-2">
                  <input
                    className="input text-xs"
                    placeholder="Type your answer here…"
                    value={answerInput}
                    onChange={(e) => setAnswerInput(e.target.value)}
                    disabled={busy}
                  />
                  <button type="submit" className="btn-primary py-2 px-4 text-xs shrink-0" disabled={busy || !answerInput.trim()}>
                    Answer
                  </button>
                </form>
              </div>
            )}

            {/* Editable Fields Form */}
            <div className="card space-y-4">
              <h3 className="text-base font-bold text-slate-900">Confirm Report Information</h3>
              <p className="text-xs text-slate-500">Review and refine the fields extracted by PRISM AI.</p>

              <div>
                <label className="label" htmlFor="vendor_name">
                  Restaurant / Vendor Name *
                </label>
                <input
                  id="vendor_name"
                  className="input"
                  required
                  placeholder="e.g. ABC Restaurant"
                  value={fields.vendor_name}
                  onChange={(e) => setFields({ ...fields, vendor_name: e.target.value })}
                />
              </div>

              <div>
                <label className="label" htmlFor="food_item">
                  Food / Product Item
                </label>
                <input
                  id="food_item"
                  className="input"
                  placeholder="e.g. Chicken Biryani"
                  value={fields.food_item}
                  onChange={(e) => setFields({ ...fields, food_item: e.target.value })}
                />
              </div>

              <div>
                <label className="label" htmlFor="issue_type">
                  Reported Issue Category *
                </label>
                <select
                  id="issue_type"
                  className="input bg-white"
                  value={fields.issue_type}
                  onChange={(e) => setFields({ ...fields, issue_type: e.target.value })}
                >
                  {ISSUE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="label" htmlFor="location_text">
                  Location / Area *
                </label>
                <input
                  id="location_text"
                  className="input"
                  placeholder="e.g. Banjara Hills, Hyderabad"
                  value={fields.location_text}
                  onChange={(e) => setFields({ ...fields, location_text: e.target.value, area: e.target.value })}
                />
              </div>

              <div>
                <label className="label" htmlFor="incident_datetime">
                  Incident Date & Time
                </label>
                <input
                  id="incident_datetime"
                  type="datetime-local"
                  className="input"
                  value={fields.incident_datetime}
                  onChange={(e) => setFields({ ...fields, incident_datetime: e.target.value })}
                />
              </div>

              <div>
                <label className="label" htmlFor="user_description">
                  Full Description
                </label>
                <textarea
                  id="user_description"
                  rows={3}
                  className="input resize-none"
                  value={fields.user_description}
                  onChange={(e) => setFields({ ...fields, user_description: e.target.value })}
                />
              </div>

              <div className="flex gap-2 pt-2">
                <button type="button" onClick={() => setStep(1)} className="btn-secondary flex-1 py-2.5 text-xs">
                  ← Back
                </button>
                <button
                  type="button"
                  onClick={() => setStep(3)}
                  disabled={!fields.vendor_name.trim()}
                  className="btn-primary flex-1 py-2.5 text-xs"
                >
                  Review Report →
                </button>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: REVIEW REPORT */}
        {step === 3 && (
          <div className="card space-y-5">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Step 3: Review Before Submitting</h2>
              <p className="mt-1 text-xs text-slate-500">
                Please verify your details. Once submitted, your report and evidence will be recorded in PRISM.
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50/50 p-4 space-y-3">
              <Field label="Restaurant / Vendor" value={fields.vendor_name} />
              <Field label="Food Item" value={fields.food_item} />
              <Field
                label="Issue Category"
                value={ISSUE_OPTIONS.find((o) => o.value === fields.issue_type)?.label || fields.issue_type}
              />
              <Field label="Location" value={fields.location_text || fields.area} />
              <Field label="Incident Date & Time" value={fields.incident_datetime} />
              <Field label="Description" value={fields.user_description} />

              {filePreview && (
                <div>
                  <p className="label">Attached Evidence</p>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={filePreview} alt="Attached photo" className="mt-1 max-h-40 rounded-xl object-contain" />
                </div>
              )}
            </div>

            <AIDisclaimer text="Submitting this report enters it into PRISM's early-warning triage system. AI signals prioritize human inspector review and do not establish legal liability." />

            <div className="flex gap-2">
              <button type="button" onClick={() => setStep(2)} className="btn-secondary flex-1 py-3 text-xs" disabled={busy}>
                ← Edit Details
              </button>
              <button type="button" onClick={handleSubmitReport} className="btn-primary flex-1 py-3 text-xs font-bold" disabled={busy}>
                {busy ? busyText : "Submit Report"}
              </button>
            </div>
          </div>
        )}

        {/* STEP 4: SUBMITTED CONFIRMATION */}
        {step === 4 && createdReport && (
          <div className="card space-y-6 text-center">
            <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-emerald-100 text-3xl text-emerald-600">
              ✓
            </div>

            <div>
              <span className="chip bg-emerald-100 text-emerald-800 font-semibold">Report Submitted</span>
              <h2 className="mt-2 text-2xl font-bold text-slate-900">Thank you for reporting</h2>
              <p className="mt-1 text-xs text-slate-500">Your report has been submitted to the PRISM Early Warning Platform.</p>
            </div>

            {/* Reference Number Box */}
            <div className="rounded-2xl border border-prism-200 bg-prism-50/50 p-4">
              <p className="text-xs font-semibold text-prism-700">PRISM Reference Code</p>
              <div className="mt-1 flex items-center justify-center gap-2">
                <span className="font-mono text-2xl font-bold tracking-wider text-slate-900">{createdReport.reference}</span>
                <button
                  type="button"
                  onClick={copyReference}
                  className="btn-ghost px-2 py-1 text-xs text-prism-700 font-medium"
                >
                  {copied ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>

            {/* Evidence Vault SHA-256 Confirmation */}
            {uploadedEvidence && (
              <div className="rounded-2xl border border-slate-200 bg-white p-4 text-left space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-700 uppercase tracking-wide">Evidence Vault Integrity</span>
                  <StatusBadge status={createdReport.status} />
                </div>
                <p className="text-xs text-slate-600">
                  File: <span className="font-medium text-slate-800">{uploadedEvidence.file_name}</span>
                </p>
                <div>
                  <p className="text-[11px] font-semibold text-slate-500">SHA-256 Server Hash</p>
                  <p className="font-mono text-[11px] text-slate-700 break-all bg-slate-100 p-2 rounded-lg mt-0.5">
                    {uploadedEvidence.sha256_hash}
                  </p>
                </div>
              </div>
            )}

            {/* Intelligence Signal Output */}
            {createdReport.risk && (
              <div className="rounded-2xl border border-amber-200 bg-amber-50/50 p-3.5 text-left">
                <p className="text-xs font-bold text-amber-800">Prioritization Signal</p>
                <p className="mt-0.5 text-xs text-slate-700">
                  Vendor <span className="font-semibold">{createdReport.vendor_name}</span> risk score:{" "}
                  <span className="font-bold">{createdReport.risk.score}/100 ({createdReport.risk.band})</span>.
                  {createdReport.cluster && ` Associated with cluster ${createdReport.cluster.label}.`}
                </p>
              </div>
            )}

            <div className="space-y-2 pt-2">
              <Link href="/reports" className="btn-primary w-full py-3 text-sm">
                View My Reports & Status →
              </Link>
              <button
                type="button"
                onClick={() => {
                  setStep(1);
                  setFile(null);
                  setFilePreview(null);
                  setInitialNote("");
                  setVisionResult(null);
                  setAssistantResult(null);
                  setCreatedReport(null);
                  setUploadedEvidence(null);
                }}
                className="btn-ghost w-full py-2 text-xs text-slate-500"
              >
                Submit another report
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
