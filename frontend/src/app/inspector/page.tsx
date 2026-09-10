"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { TopBar } from "@/components/Shell";
import {
  AIDisclaimer,
  DemoBadge,
  EmptyState,
  ErrorNote,
  PriorityBadge,
  RiskFactorList,
  RiskMeter,
  Spinner,
  StatCard,
  StatusBadge,
  formatDateTime,
  timeAgo,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth, useRequireAuth } from "@/lib/auth";
import type { CaseListItem, ClusterRecord, Hotspot, InspectorSummary } from "@/lib/types";

export default function InspectorDashboardPage() {
  const { user, loading: authLoading } = useRequireAuth("inspector");
  const { logout } = useAuth();

  const [summary, setSummary] = useState<InspectorSummary | null>(null);
  const [cases, setCases] = useState<CaseListItem[]>([]);
  const [clusters, setClusters] = useState<ClusterRecord[]>([]);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);

  const [busy, setBusy] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters & Tabs
  const [activeTab, setActiveTab] = useState<"queue" | "clusters" | "hotspots">("queue");
  const [priorityFilter, setPriorityFilter] = useState<"ALL" | "HIGH" | "MEDIUM" | "LOW">("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedRiskId, setExpandedRiskId] = useState<string | null>(null);

  const loadDashboardData = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [sumRes, caseRes, clusterRes, spotRes] = await Promise.all([
        api.inspectorSummary(),
        api.inspectorCases(),
        api.clusters(),
        api.hotspots(),
      ]);

      setSummary(sumRes);
      setCases(caseRes.cases);
      setClusters(clusterRes.clusters);
      setHotspots(spotRes.hotspots);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load inspector dashboard");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading) {
      loadDashboardData();
    }
  }, [authLoading, loadDashboardData]);

  async function handleRecompute() {
    setRecomputing(true);
    try {
      await api.recomputeIntel();
      await loadDashboardData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Recomputation failed");
    } finally {
      setRecomputing(false);
    }
  }

  // Filter cases
  const filteredCases = cases.filter((c) => {
    if (priorityFilter !== "ALL" && c.priority_band !== priorityFilter) return false;
    if (statusFilter !== "ALL" && c.status !== statusFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchVendor = c.vendor_name.toLowerCase().includes(q);
      const matchRef = c.reference.toLowerCase().includes(q);
      const matchArea = (c.area || "").toLowerCase().includes(q);
      const matchIssue = c.issue_label.toLowerCase().includes(q);
      if (!matchVendor && !matchRef && !matchArea && !matchIssue) return false;
    }
    return true;
  });

  if (authLoading || (busy && !summary)) {
    return (
      <main className="min-h-screen bg-slate-100">
        <TopBar title="Inspector Dashboard" />
        <div className="py-16">
          <Spinner label="Loading PRISM Intelligence Workspace…" />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-100 pb-20">
      {/* Header Bar */}
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-slate-900 text-white shadow-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-prism-600 font-bold text-white text-sm">
              P
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold tracking-tight text-white">PRISM Inspector Command Center</h1>
                {summary?.demo_data && <DemoBadge />}
              </div>
              <p className="text-[11px] text-slate-400">Food Safety Early-Warning & Prioritized Investigation Workspace</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {user && (
              <div className="hidden text-right text-xs md:block">
                <p className="font-semibold text-slate-200">{user.name}</p>
                <p className="text-[10px] text-slate-400">Food Safety Inspector</p>
              </div>
            )}
            <button
              type="button"
              onClick={handleRecompute}
              disabled={recomputing}
              className="btn-secondary py-1.5 px-3 text-xs bg-slate-800 border-slate-700 text-slate-200 hover:bg-slate-700"
              title="Recalculate complaint clusters & risk scores"
            >
              {recomputing ? "Recomputing…" : "🔄 Refresh Intel"}
            </button>
            <button
              type="button"
              onClick={logout}
              className="btn-ghost px-3 py-1.5 text-xs text-slate-300 hover:text-white"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-4 py-6 space-y-6">
        {error && <ErrorNote message={error} onRetry={loadDashboardData} />}

        {/* Top Summary Metrics */}
        {summary && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard label="Total Reports" value={summary.total_reports} hint={`${summary.new_reports} new intake`} />
            <StatCard
              label="High Priority"
              value={summary.high_priority}
              hint="Requires urgent inspection"
              tone="danger"
            />
            <StatCard
              label="Medium Priority"
              value={summary.medium_priority}
              hint="Under review / monitoring"
              tone="warning"
            />
            <StatCard
              label="Active Investigations"
              value={summary.active_investigations}
              hint="In-field inspections"
              tone="success"
            />
            <StatCard
              label="Hotspots & Clusters"
              value={`${summary.potential_hotspots} / ${summary.total_clusters}`}
              hint={`${summary.potential_hotspots} red cells, ${summary.total_clusters} clusters`}
              tone={summary.potential_hotspots > 0 ? "danger" : "default"}
            />
          </div>
        )}

        {/* Positioning & Disclaimer Alert */}
        <AIDisclaimer text="PRISM is a decision-support platform. Risk scores, clustering, and hotspot cells represent triage prioritization signals for human review only and do not establish legal liability or confirm contamination. The food inspector performs human investigation and makes all official decisions." />

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-200 bg-white px-4 rounded-xl shadow-sm">
          {[
            { id: "queue", label: `Priority Queue (${cases.length})` },
            { id: "clusters", label: `Complaint Clusters (${clusters.length})` },
            { id: "hotspots", label: `Hotspot Signals (${hotspots.length})` },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setActiveTab(t.id as "queue" | "clusters" | "hotspots")}
              className={`border-b-2 py-3 px-4 text-xs font-semibold transition ${
                activeTab === t.id
                  ? "border-prism-600 text-prism-700 font-bold"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* TAB 1: PRIORITY CASE QUEUE */}
        {activeTab === "queue" && (
          <div className="space-y-4">
            {/* Filter & Search Bar */}
            <div className="card flex flex-wrap items-center justify-between gap-3 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-bold text-slate-700">Priority Filter:</span>
                {(["ALL", "HIGH", "MEDIUM", "LOW"] as const).map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPriorityFilter(p)}
                    className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
                      priorityFilter === p
                        ? "bg-slate-900 text-white"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {p}
                  </button>
                ))}

                <span className="ml-3 text-xs font-bold text-slate-700">Status:</span>
                <select
                  className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <option value="ALL">All Statuses</option>
                  <option value="NEW">NEW</option>
                  <option value="UNDER_REVIEW">UNDER_REVIEW</option>
                  <option value="INVESTIGATION_REQUIRED">INVESTIGATION_REQUIRED</option>
                  <option value="VERIFIED">VERIFIED</option>
                  <option value="ACTIONED">ACTIONED</option>
                  <option value="CLOSED">CLOSED</option>
                </select>
              </div>

              <input
                type="search"
                placeholder="Search vendor, ref code, or area…"
                className="input max-w-xs text-xs"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            {filteredCases.length === 0 ? (
              <EmptyState
                title="No cases match your filters"
                body="Try adjusting your priority filter, status filter, or search query."
              />
            ) : (
              <div className="space-y-3">
                {filteredCases.map((c) => {
                  const isRiskExpanded = expandedRiskId === c.id;

                  return (
                    <div
                      key={c.id}
                      className={`card space-y-4 transition ${
                        c.priority_band === "HIGH"
                          ? "border-l-4 border-l-rose-500 bg-gradient-to-r from-rose-50/20 to-white"
                          : c.priority_band === "MEDIUM"
                            ? "border-l-4 border-l-amber-500"
                            : "border-l-4 border-l-emerald-500"
                      }`}
                    >
                      {/* Top Meta Bar */}
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm font-bold text-slate-900">{c.reference}</span>
                          <PriorityBadge band={c.priority_band} />
                          <StatusBadge status={c.status} label={c.status_label} />
                          {c.is_demo && <DemoBadge />}
                        </div>

                        <div className="flex items-center gap-2">
                          {c.cluster_label && (
                            <span className="chip bg-sky-100 text-sky-800 font-semibold text-[11px]" title={c.cluster_theme || ""}>
                              Cluster {c.cluster_label}
                            </span>
                          )}
                          <span className="text-xs text-slate-400">{timeAgo(c.created_at)}</span>
                        </div>
                      </div>

                      {/* Main Info Section */}
                      <div className="grid gap-4 md:grid-cols-3">
                        <div className="md:col-span-2 space-y-1.5">
                          <h3 className="text-base font-bold text-slate-900">{c.vendor_name}</h3>
                          <p className="text-xs font-semibold text-prism-700">
                            {c.food_item ? `${c.food_item} • ` : ""}
                            {c.issue_label}
                          </p>
                          <p className="text-xs text-slate-500">{c.location_text || c.area || "Location unlisted"}</p>
                          {c.description_preview && (
                            <p className="mt-2 text-xs leading-relaxed text-slate-600 line-clamp-2">
                              &quot;{c.description_preview}&quot;
                            </p>
                          )}
                        </div>

                        {/* Risk Meter Widget */}
                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 flex flex-col justify-between">
                          <RiskMeter score={c.risk_score} band={c.priority_band} compact />
                          <div className="mt-3 flex items-center justify-between text-[11px]">
                            <span className="text-slate-500">
                              📷 {c.evidence_count} evidence file(s)
                            </span>
                            {c.risk_factors?.components && (
                              <button
                                type="button"
                                onClick={() => setExpandedRiskId(isRiskExpanded ? null : c.id)}
                                className="font-semibold text-prism-700 hover:underline"
                              >
                                {isRiskExpanded ? "Hide Risk Factors ▲" : "Explain Score ▼"}
                              </button>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Expandable Risk Factors Breakdown */}
                      {isRiskExpanded && c.risk_factors?.components && (
                        <div className="rounded-xl border border-prism-200 bg-prism-50/40 p-4">
                          <RiskFactorList factors={c.risk_factors as import("@/lib/types").RiskFactors} />
                        </div>
                      )}

                      {/* Actions Footer */}
                      <div className="flex items-center justify-between border-t border-slate-100 pt-3">
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                          <span>Incident: {formatDateTime(c.incident_datetime)}</span>
                          {c.has_investigation && (
                            <span className="chip bg-emerald-100 text-emerald-800 font-semibold">
                              Inspection active
                            </span>
                          )}
                        </div>

                        <Link
                          href={`/inspector/cases/${c.id}`}
                          className="btn-primary py-2 px-4 text-xs font-semibold"
                        >
                          Review & Investigate Case →
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: COMPLAINT CLUSTERS */}
        {activeTab === "clusters" && (
          <div className="space-y-4">
            <div className="card bg-white p-4">
              <h2 className="text-base font-bold text-slate-900">Semantic Complaint Clusters</h2>
              <p className="mt-0.5 text-xs text-slate-500">
                PRISM clusters complaints that describe semantically similar issues across vendors or geographic areas.
              </p>
            </div>

            {clusters.length === 0 ? (
              <EmptyState
                title="No active clusters detected"
                body="Clustering requires multiple semantically similar reports to trigger DBSCAN grouping."
              />
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {clusters.map((cl) => (
                  <div key={cl.id} className="card space-y-3 border-l-4 border-l-sky-500 bg-white">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-sm font-bold text-sky-800 bg-sky-100 px-2 py-0.5 rounded-lg">
                        Cluster {cl.label}
                      </span>
                      <span className="chip bg-slate-100 text-slate-700 font-semibold">
                        {cl.report_count} Reports
                      </span>
                    </div>

                    <div>
                      <h3 className="text-sm font-bold text-slate-900">{cl.theme}</h3>
                      <p className="mt-1 text-xs text-slate-500">
                        Dominant Establishment: <span className="font-semibold text-slate-800">{cl.dominant_vendor || "Multiple"}</span>
                      </p>
                      <p className="text-xs text-slate-500">
                        Dominant Area: <span className="font-semibold text-slate-800">{cl.dominant_area || "Multiple"}</span>
                      </p>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-100 pt-2">
                      <span>Avg Similarity: {(cl.avg_similarity * 100).toFixed(0)}%</span>
                      <span>{timeAgo(cl.created_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: HOTSPOT SIGNALS */}
        {activeTab === "hotspots" && (
          <div className="space-y-4">
            <div className="card bg-white p-4">
              <h2 className="text-base font-bold text-slate-900">Geographic Hotspot Signals</h2>
              <p className="mt-0.5 text-xs text-slate-500">
                Reports are bucketed into ~1.1 km geo-cells. Red cells indicate high complaint volume or elevated vendor risk.
              </p>
            </div>

            {hotspots.length === 0 ? (
              <EmptyState title="No hotspot activity detected" body="No geo-located complaints available in the selected window." />
            ) : (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {hotspots.map((h) => (
                  <div
                    key={h.id}
                    className={`card space-y-3 ${
                      h.level === "red"
                        ? "border-l-4 border-l-rose-500 bg-rose-50/30"
                        : h.level === "yellow"
                          ? "border-l-4 border-l-amber-500 bg-amber-50/30"
                          : "border-l-4 border-l-emerald-500 bg-emerald-50/30"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900">{h.area}</span>
                      <span
                        className={`chip font-bold uppercase ${
                          h.level === "red"
                            ? "bg-rose-100 text-rose-800"
                            : h.level === "yellow"
                              ? "bg-amber-100 text-amber-800"
                              : "bg-emerald-100 text-emerald-800"
                        }`}
                      >
                        {h.level} Cell Signal
                      </span>
                    </div>

                    <div className="space-y-1 text-xs text-slate-700">
                      <p>
                        Total Cell Reports: <span className="font-bold text-slate-900">{h.report_count}</span>
                      </p>
                      <p>
                        7-Day Activity Growth: <span className="font-bold text-slate-900">+{h.growth_pct}%</span>
                      </p>
                      <p>
                        Max Vendor Risk: <span className="font-bold text-slate-900">{h.max_vendor_risk}/100</span>
                      </p>
                    </div>

                    {h.establishments && h.establishments.length > 0 && (
                      <div className="text-[11px] text-slate-500 border-t border-slate-200/60 pt-2">
                        <span className="font-semibold">Establishments: </span>
                        {h.establishments.join(", ")}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
