export type Role = "citizen" | "inspector";

export interface SessionUser {
  id: string;
  email: string;
  name: string;
  role: Role;
}

export interface VisionResult {
  detected_issue: string;
  risk_level: "Low" | "Moderate" | "High";
  confidence: number;
  explanation: string;
  issue_type: string;
  model: string;
  disclaimer: string;
}

export interface AssistantResult {
  fields: Record<string, string>;
  missing_fields: string[];
  next_question: string | null;
  complete: boolean;
  notice: string | null;
  model: string;
  disclaimer: string;
}

export interface EvidenceRecord {
  id: string;
  report_id: string;
  file_url: string;
  file_name: string;
  file_type: string;
  file_size: number;
  sha256_hash: string;
  kind: string;
  uploader_role: string;
  geo_lat: number | null;
  geo_lng: number | null;
  capture_timestamp: string | null;
  uploaded_at: string;
  is_demo: boolean;
  audit_log?: { id: string; action: string; actor: string; detail: string | null; timestamp: string }[];
}

export interface AIAssessmentRecord {
  id: string;
  source: string;
  detected_issue: string;
  risk_level: string;
  confidence: number;
  explanation: string;
  model: string;
  created_at: string;
  disclaimer: string;
}

export interface RiskComponent {
  key: string;
  label: string;
  weight_pct: number;
  normalised: number;
  contribution: number;
}

export interface RiskFactors {
  total_reports: number;
  reports_last_7_days: number;
  reports_previous_7_days: number;
  similar_reports: number;
  mean_similarity: number;
  growth_pct: number;
  avg_severity: number;
  geo_concentration_pct: number;
  reports_with_evidence: number;
  verified_history: number;
  components: RiskComponent[];
  explanations: string[];
  disclaimer: string;
}

export interface ClusterRecord {
  id: string;
  label: string;
  theme: string;
  report_count: number;
  dominant_vendor: string | null;
  dominant_area: string | null;
  avg_similarity: number;
  criteria: Record<string, unknown>;
  created_at: string;
  note: string;
  reports?: ReportSummary[];
}

export interface ReportSummary {
  id: string;
  reference: string;
  vendor_name: string;
  vendor_id: string | null;
  food_item: string | null;
  issue_type: string;
  issue_label: string;
  status: string;
  status_label: string;
  area: string | null;
  location_text: string | null;
  latitude: number | null;
  longitude: number | null;
  severity: number;
  incident_datetime: string | null;
  created_at: string;
  cluster_id: string | null;
  is_demo: boolean;
  description_preview: string;
  similarity?: number;
}

export interface TimelineStep {
  status: string;
  label: string;
  state: "done" | "current" | "pending";
}

export interface ReportDetail extends ReportSummary {
  user_description: string;
  evidence_available: string | null;
  evidence: EvidenceRecord[];
  ai_assessments: AIAssessmentRecord[];
  updates: { status: string; message: string; actor_role: string; timestamp: string }[];
  timeline: TimelineStep[];
  cluster: ClusterRecord | null;
  risk: { score: number; band: string; factors: RiskFactors } | null;
  disclaimer: string;
  investigations?: InvestigationRecord[];
  reporter?: { name: string; email: string } | null;
}

export interface InvestigationRecord {
  id: string;
  report_id: string;
  inspector_name: string;
  status: string;
  checklist: Record<string, boolean>;
  notes: string;
  findings: string | null;
  decision: string | null;
  decision_note: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InspectorSummary {
  new_reports: number;
  high_priority: number;
  medium_priority: number;
  low_priority: number;
  active_investigations: number;
  potential_hotspots: number;
  new_clusters: number;
  total_clusters: number;
  total_reports: number;
  demo_data: boolean;
}

export interface CaseListItem extends ReportSummary {
  priority_score: number;
  priority_band: "HIGH" | "MEDIUM" | "LOW";
  risk_score: number;
  risk_factors: RiskFactors | Record<string, never>;
  cluster_label: string | null;
  cluster_theme: string | null;
  evidence_count: number;
  has_investigation: boolean;
}

export interface Hotspot {
  id: string;
  latitude: number;
  longitude: number;
  report_count: number;
  reports_last_7_days: number;
  growth_pct: number;
  level: "red" | "yellow" | "green";
  max_vendor_risk: number;
  area: string;
  establishments: string[];
  issue_types: string[];
  clusters: string[];
  note: string;
}

export interface CaseDetail {
  report: ReportDetail;
  vendor: {
    id: string;
    name: string;
    address: string | null;
    area: string | null;
    city: string | null;
    latitude: number | null;
    longitude: number | null;
    licence_ref: string | null;
    is_demo: boolean;
  } | null;
  risk: { vendor_id: string; vendor_name: string; score: number; band: string; factors: RiskFactors } | null;
  vendor_reports: ReportSummary[];
  cluster: ClusterRecord | null;
  similar_reports: ReportSummary[];
  hotspots: Hotspot[];
  investigations: InvestigationRecord[];
}
