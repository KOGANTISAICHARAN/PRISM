"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { BackendStatus, PrismMark, TopBar } from "@/components/Shell";
import { DemoBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const STEPS = [
  { title: "Report", body: "Add a photo, location and a short description." },
  { title: "Detect", body: "PRISM structures the complaint and looks for patterns across reports." },
  { title: "Investigate", body: "Inspectors review evidence and run the investigation." },
  { title: "Prevent", body: "You get status updates as the case progresses." },
];

export default function HomePage() {
  const { user } = useAuth();
  const [openReports, setOpenReports] = useState<number | null>(null);

  useEffect(() => {
    if (!user || user.role !== "citizen") return;
    api
      .myReports()
      .then((r) => setOpenReports(r.count))
      .catch(() => setOpenReports(null));
  }, [user]);

  return (
    <main>
      <TopBar />
      <section className="mx-auto max-w-3xl px-4 pb-10 pt-6">
        <div className="rounded-3xl bg-gradient-to-b from-prism-700 to-prism-600 p-6 text-white shadow-lg">
          <PrismMark className="text-lg text-white" />
          <h1 className="mt-4 text-2xl font-bold leading-tight">AI-powered food safety early warning</h1>
          <p className="mt-1 text-sm font-medium text-prism-100">Report. Detect. Investigate. Prevent.</p>
          <p className="mt-4 text-sm leading-relaxed text-white/90">
            PRISM helps identify patterns in food-safety complaints and helps inspectors prioritise cases for
            investigation.
          </p>
          <div className="mt-6 space-y-3">
            <Link href="/report" className="btn w-full bg-white py-3.5 text-prism-800 hover:bg-prism-50">
              Report a Food Safety Issue
            </Link>
            <Link
              href="/reports"
              className="btn w-full border border-white/40 bg-white/10 text-white hover:bg-white/20"
            >
              My Reports{openReports !== null ? ` (${openReports})` : ""}
            </Link>
          </div>
        </div>

        {user?.role === "inspector" && (
          <Link href="/inspector" className="card mt-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-slate-900">Inspector dashboard</p>
              <p className="text-xs text-slate-500">Priority queue, clusters, hotspots and investigations</p>
            </div>
            <span className="text-prism-600">→</span>
          </Link>
        )}

        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {STEPS.map((s, i) => (
            <div key={s.title} className="card">
              <p className="text-xs font-bold text-prism-600">STEP {i + 1}</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">{s.title}</p>
              <p className="mt-1 text-xs leading-relaxed text-slate-600">{s.body}</p>
            </div>
          ))}
        </div>

        <div className="card mt-6">
          <div className="flex flex-wrap items-center gap-2">
            <p className="section-title">How PRISM uses AI</p>
            <DemoBadge />
          </div>
          <ul className="mt-2 space-y-1.5 text-xs leading-relaxed text-slate-600">
            <li>• AI analyses visible characteristics in your photo and structures your complaint.</li>
            <li>• AI groups similar complaints and produces a prioritisation signal for inspectors.</li>
            <li>
              • AI does <span className="font-semibold">not</span> confirm contamination, decide legal responsibility or
              diagnose illness. A human inspector makes every decision.
            </li>
          </ul>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <BackendStatus />
          <Link href="/login" className="text-xs font-semibold text-prism-700">
            Inspector / authorised reviewer sign in →
          </Link>
        </div>
      </section>
    </main>
  );
}
