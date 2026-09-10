import type {
  AssistantResult,
  CaseDetail,
  CaseListItem,
  ClusterRecord,
  EvidenceRecord,
  Hotspot,
  InspectorSummary,
  InvestigationRecord,
  ReportDetail,
  ReportSummary,
  SessionUser,
  VisionResult,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

const TOKEN_KEY = "prism.token";
const USER_KEY = "prism.user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function storeSession(token: string, user: SessionUser) {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function readStoredUser(): SessionUser | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  return raw ? (JSON.parse(raw) as SessionUser) : null;
}

export function clearSession() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}, isForm = false): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (!isForm) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiError("Cannot reach the PRISM backend. Check your connection and try again.", 0);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).join("; ")
          : `Request failed (${res.status})`;
    throw new ApiError(message, res.status);
  }
  return data as T;
}

export const api = {
  health: () =>
    request<{ status: string; demo_mode: boolean; ai_provider: string; storage_backend: string; embedding_backend: string }>(
      "/health",
    ),

  // auth
  login: (email: string, password: string) =>
    request<{ access_token: string; user: SessionUser }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (payload: { email: string; password: string; name: string; phone?: string; role?: string }) =>
    request<{ access_token: string; user: SessionUser }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  me: () => request<SessionUser & { jurisdiction: string | null }>("/auth/me"),

  // ai
  aiStatus: () => request<{ provider: string; demo_mode: boolean; vision_model: string; disclaimer: string }>("/ai/status"),
  analyzeImage: (file: File, hint: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("hint", hint);
    return request<VisionResult>("/ai/analyze-image", { method: "POST", body: form }, true);
  },
  structureComplaint: (payload: {
    messages: { role: string; content: string }[];
    known_fields: Record<string, unknown>;
    vision?: VisionResult | null;
  }) => request<AssistantResult>("/ai/structure-complaint", { method: "POST", body: JSON.stringify(payload) }),

  // reports
  createReport: (payload: Record<string, unknown>) =>
    request<ReportDetail>("/reports", { method: "POST", body: JSON.stringify(payload) }),
  finalizeReport: (id: string) => request<ReportDetail>(`/reports/${id}/finalize`, { method: "POST" }),
  myReports: () => request<{ count: number; reports: ReportSummary[] }>("/reports"),
  getReport: (idOrRef: string) => request<ReportDetail>(`/reports/${idOrRef}`),

  // evidence
  uploadEvidence: (reportId: string, file: File, kind = "citizen_photo", coords?: { lat: number; lng: number }) => {
    const form = new FormData();
    form.append("report_id", reportId);
    form.append("kind", kind);
    form.append("file", file);
    if (coords) {
      form.append("geo_lat", String(coords.lat));
      form.append("geo_lng", String(coords.lng));
    }
    return request<EvidenceRecord>("/evidence", { method: "POST", body: form }, true);
  },
  getEvidence: (id: string) => request<EvidenceRecord>(`/evidence/${id}`),
  verifyEvidence: (id: string) =>
    request<{ evidence_id: string; recorded_hash: string; recomputed_hash: string; integrity_verified: boolean }>(
      `/evidence/${id}/verify`,
    ),

  // intelligence
  clusters: () => request<{ embedding_backend: string; count: number; clusters: ClusterRecord[] }>("/clusters"),
  cluster: (id: string) => request<ClusterRecord>(`/clusters/${id}`),
  hotspots: (days = 30) => request<{ days: number; hotspots: Hotspot[] }>(`/hotspots?days=${days}`),
  vendorRisk: (vendorId: string) => request<CaseDetail["risk"]>(`/risk/${vendorId}`),
  recomputeIntel: () => request<{ clusters: number; embedding_backend: string }>("/intel/recompute", { method: "POST" }),

  // inspector
  inspectorSummary: () => request<InspectorSummary>("/inspector/summary"),
  inspectorCases: (statuses?: string) =>
    request<{ count: number; cases: CaseListItem[] }>(
      `/inspector/cases${statuses ? `?status_filter=${encodeURIComponent(statuses)}` : ""}`,
    ),
  inspectorCase: (id: string) => request<CaseDetail>(`/inspector/cases/${id}`),
  markUnderReview: (id: string) => request<ReportDetail>(`/inspector/cases/${id}/review`, { method: "POST" }),

  // investigations
  startInvestigation: (reportId: string, notes = "") =>
    request<InvestigationRecord>("/investigations", {
      method: "POST",
      body: JSON.stringify({ report_id: reportId, notes }),
    }),
  updateInvestigation: (
    id: string,
    payload: { checklist?: Record<string, boolean>; notes?: string; findings?: string; status?: string },
  ) => request<InvestigationRecord>(`/investigations/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  uploadInspectionEvidence: (id: string, file: File, kind = "inspection_photo") => {
    const form = new FormData();
    form.append("kind", kind);
    form.append("file", file);
    return request<EvidenceRecord>(`/investigations/${id}/evidence`, { method: "POST", body: form }, true);
  },
  recordDecision: (id: string, payload: { status: string; decision_note: string; findings?: string }) =>
    request<{ investigation: InvestigationRecord; report_status: string }>(`/investigations/${id}/decision`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export function evidenceUrl(fileUrl: string): string {
  return fileUrl.startsWith("http") ? fileUrl : `${API_BASE}${fileUrl}`;
}
