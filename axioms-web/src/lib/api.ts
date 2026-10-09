import type {
  AgentProfile,
  ApprovalPayload,
  AssessmentBlueprintRequest,
  AutoEvalReportRequest,
  ContentPackageRequest,
  HealthResponse,
  LecturePlanRequest,
  OperationsSummary,
  PortfolioPackageRequest,
  ResearchBriefRequest,
  SocialMediaPackageRequest,
  TaskListResponse,
  TaskRecord,
  TaskRequest,
  TaskStatus,
  TaskStatusResponse,
  UsageSummary,
  WritingDraftRequest,
} from "./types";

const API_BASE =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
    : (process.env.NEXT_PUBLIC_API_URL ?? "http://api:8000");

// ── Core fetch helper ────────────────────────────────────────────────────────

interface RequestConfig {
  apiKey: string;
  allowExternalProvider?: boolean;
}

function headers(config: RequestConfig): Record<string, string> {
  const h: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (config.apiKey) h["X-API-Key"] = config.apiKey;
  if (config.allowExternalProvider) h["X-Axioms-Allow-External-Provider"] = "true";
  return h;
}

async function request<T>(
  method: string,
  path: string,
  config: RequestConfig,
  body?: unknown
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: headers(config),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, detail.detail ?? "Request failed");
  }
  return res.json();
}

async function requestBlob(
  method: string,
  path: string,
  config: RequestConfig,
  body?: unknown
): Promise<Blob> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: headers(config),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, detail.detail ?? "Request failed");
  }
  return res.blob();
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ── API client ───────────────────────────────────────────────────────────────

export function createApiClient(config: RequestConfig) {
  const get = <T>(path: string) => request<T>("GET", path, config);
  const post = <T>(path: string, body?: unknown) => request<T>("POST", path, config, body);
  const del = <T>(path: string, body?: unknown) => request<T>("DELETE", path, config, body);
  const postBlob = (path: string, body?: unknown) => requestBlob("POST", path, config, body);

  return {
    // ── Health & system ────────────────────────────────────────────────────
    health: () => get<HealthResponse>("/health"),
    agents: () => get<AgentProfile[]>("/agents"),
    operationsSummary: () => get<OperationsSummary>("/operations/summary"),
    usageSummary: () => get<UsageSummary>("/usage/summary"),

    // ── Tasks ──────────────────────────────────────────────────────────────
    listTasks: (status?: TaskStatus, limit = 50, cursor?: string) => {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (limit !== 50) params.set("limit", String(limit));
      if (cursor) params.set("cursor", cursor);
      const qs = params.toString();
      return get<TaskListResponse>(`/tasks${qs ? `?${qs}` : ""}`);
    },
    getTask: (id: string) => get<TaskRecord>(`/tasks/${id}`),
    getTaskStatus: (id: string) => get<TaskStatusResponse>(`/tasks/${id}/status`),
    createTask: (task: TaskRequest) => post<TaskRecord>("/tasks", task),
    approveTask: (id: string, payload: ApprovalPayload) =>
      post<TaskRecord>(`/tasks/${id}/approval`, payload),
    executeTask: (id: string, parallel = false) =>
      post<TaskRecord>(`/tasks/${id}/execute?parallel=${parallel}`),
    cancelTask: (id: string, requestedBy: string, note?: string) =>
      post<TaskRecord>(`/tasks/${id}/cancel`, {
        requested_by: requestedBy,
        note,
      }),
    recoverTask: (id: string, recoveredBy: string, note?: string) =>
      post<TaskRecord>(`/tasks/${id}/recover`, {
        recovered_by: recoveredBy,
        note,
        confirm_execution_stopped: true,
      }),
    reviseTask: (id: string, requestedBy: string) =>
      post<TaskRecord>(`/tasks/${id}/revise`, { requested_by: requestedBy }),
    getTaskTrace: (id: string) => get<Record<string, unknown>>(`/tasks/${id}/trace`),
    getTaskLineage: (id: string) => get<Record<string, unknown>>(`/tasks/${id}/lineage`),

    // ── Lecture Plans ──────────────────────────────────────────────────────
    createLecturePlan: (plan: LecturePlanRequest) =>
      post<Record<string, unknown>>("/lecture-plans", plan),
    downloadLecturePlanDocx: (plan: LecturePlanRequest) =>
      postBlob("/lecture-plans/docx", plan),

    // ── Writing Drafts ─────────────────────────────────────────────────────
    createWritingDraft: (draft: WritingDraftRequest) =>
      post<Record<string, unknown>>("/writing-drafts", draft),
    downloadWritingDraftDocx: (draft: WritingDraftRequest) =>
      postBlob("/writing-drafts/docx", draft),

    // ── Research Briefs ────────────────────────────────────────────────────
    createResearchBrief: (brief: ResearchBriefRequest) =>
      post<Record<string, unknown>>("/research-briefs", brief),
    createAgenticResearchBrief: (brief: ResearchBriefRequest) =>
      post<Record<string, unknown>>("/research-briefs/agentic", brief),
    downloadResearchBriefDocx: (brief: ResearchBriefRequest) =>
      postBlob("/research-briefs/docx", brief),
    discoverResearch: (query: string, maxResults = 5) =>
      post<Record<string, unknown>>("/research/discover", {
        query,
        max_results: maxResults,
      }),

    // ── Assessment Blueprints ──────────────────────────────────────────────
    createAssessmentBlueprint: (bp: AssessmentBlueprintRequest) =>
      post<Record<string, unknown>>("/assessment-blueprints", bp),
    createAgenticAssessment: (bp: AssessmentBlueprintRequest) =>
      post<Record<string, unknown>>("/assessment-blueprints/agentic", bp),
    downloadStudentDocx: (bp: AssessmentBlueprintRequest) =>
      postBlob("/assessment-blueprints/student-docx", bp),
    downloadInstructorDocx: (bp: AssessmentBlueprintRequest) =>
      postBlob("/assessment-blueprints/instructor-docx", bp),

    // ── Content Packages ───────────────────────────────────────────────────
    createContentPackage: (pkg: ContentPackageRequest) =>
      post<Record<string, unknown>>("/content-packages", pkg),
    createAgenticContent: (pkg: ContentPackageRequest) =>
      post<Record<string, unknown>>("/content-packages/agentic", pkg),
    downloadContentDocx: (pkg: ContentPackageRequest) =>
      postBlob("/content-packages/docx", pkg),

    // ── Social Media Packages ──────────────────────────────────────────────
    createSocialMediaPackage: (pkg: SocialMediaPackageRequest) =>
      post<Record<string, unknown>>("/social-media-packages", pkg),
    createAgenticSocialMedia: (pkg: SocialMediaPackageRequest) =>
      post<Record<string, unknown>>("/social-media-packages/agentic", pkg),
    downloadSocialMediaDocx: (pkg: SocialMediaPackageRequest) =>
      postBlob("/social-media-packages/docx", pkg),

    // ── Portfolio Packages ─────────────────────────────────────────────────
    createPortfolioPackage: (pkg: PortfolioPackageRequest) =>
      post<Record<string, unknown>>("/portfolio-packages", pkg),
    createAgenticPortfolio: (pkg: PortfolioPackageRequest) =>
      post<Record<string, unknown>>("/portfolio-packages/agentic", pkg),
    downloadPortfolioDocx: (pkg: PortfolioPackageRequest) =>
      postBlob("/portfolio-packages/docx", pkg),

    // ── AutoEval Reports ───────────────────────────────────────────────────
    createAutoEvalReport: (report: AutoEvalReportRequest) =>
      post<Record<string, unknown>>("/autoeval-reports", report),
    downloadAutoEvalDocx: (report: AutoEvalReportRequest) =>
      postBlob("/autoeval-reports/docx", report),

    // ── Episodic Memory ────────────────────────────────────────────────────
    searchMemory: (query: string, limit = 5) =>
      get<Record<string, unknown>[]>(`/episodic-memory/search?query=${encodeURIComponent(query)}&limit=${limit}`),
    deleteMemory: (id: string, deletedBy: string, note?: string) =>
      del<Record<string, unknown>>(`/episodic-memory/${id}`, {
        deleted_by: deletedBy,
        note,
      }),

    // ── Personal KB ────────────────────────────────────────────────────────
    listKBEntries: () => get<Record<string, unknown>[]>("/personal-kb/entries"),

    // ── Similarity ─────────────────────────────────────────────────────────
    screenSimilarity: (body: unknown) =>
      post<Record<string, unknown>>("/similarity/screen", body),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
