// ── Agent Names ──────────────────────────────────────────────────────────────
export type AgentName =
  | "axioms_core"
  | "research"
  | "stem_ai_portfolio"
  | "lecture_design"
  | "assessment_design"
  | "content_creation"
  | "writing_communication"
  | "social_media"
  | "autoeval";

// ── Task Status ──────────────────────────────────────────────────────────────
export type TaskStatus =
  | "planned"
  | "pending_approval"
  | "approved"
  | "running"
  | "cancellation_requested"
  | "cancelled"
  | "awaiting_review"
  | "completed"
  | "failed"
  | "rejected";

export type ApprovalDecision = "approve" | "reject";
export type RiskTier = "low" | "elevated" | "high";

// ── Tasks ────────────────────────────────────────────────────────────────────
export interface TaskRequest {
  goal: string;
  audience?: string;
  deadline?: string | null;
  constraints?: string[];
  external_delivery?: boolean;
}

export interface TaskRecord {
  task_id: string;
  created_at: string;
  status: TaskStatus;
  risk_tier: RiskTier;
  request: {
    goal: string;
    audience: string;
    deadline: string | null;
    constraints: string[];
    external_delivery: boolean;
    revision_note: string | null;
  };
  subtasks: Subtask[];
  deliverables: Deliverable[];
  agent_trace: AgentStep[];
  approval_note: string | null;
  approved_by: string | null;
  reviewed_by: string | null;
  revision_of: string | null;
  reference_documents: Record<string, unknown>[];
}

export interface Subtask {
  agent: AgentName;
  title: string;
  instructions: string;
  depends_on: string[];
  checkpoint: boolean;
}

export interface Deliverable {
  title: string;
  agent: AgentName;
  content: string;
  status: TaskStatus;
}

export interface AgentStep {
  kind: string;
  summary: string;
  agent: AgentName | null;
  created_at: string;
}

export interface TaskListResponse {
  items: TaskRecord[];
  next_cursor: string | null;
  total: number;
}

export interface TaskStatusResponse {
  task_id: string;
  created_at: string;
  status: TaskStatus;
  risk_tier: RiskTier | null;
  deliverable_count: number;
  final_review_required: boolean;
}

// ── Agent Profiles ───────────────────────────────────────────────────────────
export interface AgentProfile {
  name: string;
  display_name: string;
  role: string;
  capabilities: string[];
  governance_notes: string[];
}

// ── Lecture Plan ──────────────────────────────────────────────────────────────
export interface LecturePlanRequest {
  topic: string;
  course_level: string;
  duration_minutes: number;
  audience: string;
  prior_knowledge?: string;
  learning_outcomes: string[];
  application_context?: string | null;
  include_computational_activity?: boolean;
}

// ── Writing Draft ────────────────────────────────────────────────────────────
export type DocumentType =
  | "journal_article"
  | "conference_paper"
  | "grant_proposal"
  | "technical_report"
  | "blog_post"
  | "course_material"
  | "policy_brief";

export interface WritingDraftRequest {
  document_type: DocumentType;
  subject: string;
  audience: string;
  purpose: string;
  key_points: string[];
  verified_facts: string[];
  tone?: string;
  references?: string[];
  external_delivery?: boolean;
}

// ── Research Brief ───────────────────────────────────────────────────────────
export type PublicationKind =
  | "journal_article"
  | "conference_paper"
  | "preprint"
  | "book_chapter"
  | "thesis"
  | "technical_report"
  | "working_paper";

export type VerificationStatus = "unverified" | "verified" | "retracted" | "disputed";

export interface EvidenceSource {
  source_id: string;
  title: string;
  authors: string[];
  year: number;
  publication_kind: PublicationKind;
  doi?: string | null;
  url?: string | null;
  peer_reviewed?: boolean;
  supported_claim?: string | null;
  verification_status?: VerificationStatus;
  verification_evidence?: string | null;
}

export interface ResearchBriefRequest {
  research_question: string;
  scope: string;
  sources: EvidenceSource[];
  analysis_dimensions?: string[];
  target_venue?: string | null;
}

// ── Assessment Blueprint ─────────────────────────────────────────────────────
export type AssessmentType = "exam" | "quiz" | "assignment" | "project" | "lab_report";
export type BloomLevel = "remember" | "understand" | "apply" | "analyze" | "evaluate" | "create";
export type Difficulty = "easy" | "moderate" | "hard" | "expert";

export interface LearningOutcome {
  outcome_id: string;
  text: string;
  bloom_level: BloomLevel;
}

export interface AssessmentBlueprintRequest {
  topic: string;
  course_level: string;
  assessment_type: AssessmentType;
  duration_minutes: number;
  total_marks: number;
  question_count: number;
  learning_outcomes: LearningOutcome[];
  approved_source_scope: string;
  difficulties?: Difficulty[];
  require_handwritten_work?: boolean;
  require_reflection?: boolean;
  include_personalised_context?: boolean;
}

// ── Content Package ──────────────────────────────────────────────────────────
export type ContentFormat =
  | "video_script"
  | "podcast_script"
  | "infographic_brief"
  | "slide_deck"
  | "worksheet";

export type LanguageMode = "english" | "urdu" | "bilingual";

export interface ContentPackageRequest {
  topic: string;
  format: ContentFormat;
  audience: string;
  duration_minutes: number;
  approved_source_scope: string;
  learning_outcomes: string[];
  language_mode?: LanguageMode;
  application_context?: string | null;
  keywords?: string[];
}

// ── Social Media Package ─────────────────────────────────────────────────────
export type SocialPlatform = "twitter" | "linkedin" | "youtube" | "instagram" | "facebook";
export type SocialObjective = "educate" | "engage" | "promote" | "recruit";

export interface SocialMediaPackageRequest {
  topic: string;
  audience: string;
  platforms: SocialPlatform[];
  objective?: SocialObjective;
  approved_source_scope: string;
  verified_facts: string[];
  brand_voice?: string;
  call_to_action?: string | null;
  calendar_weeks?: number;
}

// ── Portfolio Package ────────────────────────────────────────────────────────
export type PortfolioAudience = "academic" | "industry" | "general";
export type RepositoryVisibility = "public" | "private";
export type DataAccessLevel = "open" | "restricted" | "synthetic";

export interface PortfolioEvidence {
  evidence_id: string;
  claim: string;
  source_reference: string;
  verified: boolean;
}

export interface DatasetAsset {
  name: string;
  access_level: DataAccessLevel;
  licence_or_permission?: string | null;
  attribution?: string | null;
}

export interface PortfolioPackageRequest {
  project_title: string;
  research_summary: string;
  target_audience: PortfolioAudience;
  repository_visibility: RepositoryVisibility;
  verified_evidence: PortfolioEvidence[];
  dataset_assets?: DatasetAsset[];
  include_demo_plan?: boolean;
  include_notebook_plan?: boolean;
}

// ── AutoEval Report ──────────────────────────────────────────────────────────
export type EvaluatedAgent =
  | "research"
  | "lecture_design"
  | "assessment_design"
  | "content_creation"
  | "writing_communication"
  | "social_media"
  | "stem_ai_portfolio";

export interface AutoEvalReportRequest {
  evaluated_agent: EvaluatedAgent;
  deliverable_title: string;
  artifact_text: string;
  required_elements: string[];
  evidence_markers?: string[];
  public_facing?: boolean;
  declared_sensitive_data?: boolean;
}

// ── Approval ─────────────────────────────────────────────────────────────────
export interface ApprovalPayload {
  decision: ApprovalDecision;
  approved_by: string;
  note?: string | null;
  override_blocking?: boolean;
}

// ── Episodic Memory ──────────────────────────────────────────────────────────
export type MemoryDecision = "approve" | "reject";

export interface MemoryEntry {
  memory_id: string;
  task_id: string;
  summary: string;
  created_at: string;
  approved_at?: string;
  retention_days: number;
}

// ── System ───────────────────────────────────────────────────────────────────
export interface HealthResponse {
  status: string;
}

export interface OperationsSummary {
  total_tasks: number;
  by_status: Record<TaskStatus, number>;
  dispatch: {
    queued: number;
    running: number;
    completed: number;
    failed: number;
  };
}

export interface UsageSummary {
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  by_provider: Record<string, { requests: number; input_tokens: number; output_tokens: number }>;
}

// ── Helper maps ──────────────────────────────────────────────────────────────
export const AGENT_DISPLAY_NAMES: Record<AgentName, string> = {
  axioms_core: "Axioms Core",
  research: "Research Agent",
  stem_ai_portfolio: "Portfolio Agent",
  lecture_design: "Lecture Agent",
  assessment_design: "Assessment Agent",
  content_creation: "Content Agent",
  writing_communication: "Writing Agent",
  social_media: "Social Media Agent",
  autoeval: "AutoEval Agent",
};

export const AGENT_DESCRIPTIONS: Record<AgentName, string> = {
  axioms_core: "Central orchestrator for multi-agent task coordination",
  research: "Literature review, evidence synthesis, and research briefs",
  stem_ai_portfolio: "Research portfolio packaging and showcase generation",
  lecture_design: "Structured lecture plan design with learning outcomes",
  assessment_design: "Bloom-aligned assessment blueprints and exam papers",
  content_creation: "Educational content in multiple formats",
  writing_communication: "Academic and professional writing drafts",
  social_media: "Platform-specific social media content calendars",
  autoeval: "Automated quality evaluation of agent deliverables",
};

export const STATUS_COLORS: Record<TaskStatus, string> = {
  planned: "bg-slate-100 text-slate-700",
  pending_approval: "bg-amber-100 text-amber-800",
  approved: "bg-blue-100 text-blue-800",
  running: "bg-indigo-100 text-indigo-800",
  cancellation_requested: "bg-orange-100 text-orange-800",
  cancelled: "bg-gray-100 text-gray-600",
  awaiting_review: "bg-purple-100 text-purple-800",
  completed: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
  rejected: "bg-red-100 text-red-700",
};
