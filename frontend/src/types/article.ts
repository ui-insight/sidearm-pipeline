export type ArticleType =
  | "game_recap"
  | "player_spotlight"
  | "achievement_story";

export type ArticleStatus =
  | "brief"
  | "generating"
  | "in_edit"
  | "ready"
  | "needs_revalidation"
  | "archived";

export type ArticleGenerationJobState =
  | "queued"
  | "running"
  | "succeeded"
  | "failed";

export interface ArticleBriefCreate {
  suggestion_ids: number[];
  article_type: ArticleType;
  angle: string;
  audience: string;
  constraints: string | null;
  idempotency_key: string;
}

export interface ArticleGameEvidence {
  id: number;
  canonical_uid: string;
  sport: string | null;
  season: string | null;
  game_date: string | null;
  title: string | null;
  home_team: string | null;
  away_team: string | null;
  home_score: number | null;
  away_score: number | null;
  source_url: string;
}

export interface EvidenceSource {
  snapshot_id: number;
  source_system: string;
  source_type: string;
  source_url: string;
  content_hash: string;
  fetched_at: string;
}

export interface EvidenceCoverageWindow {
  id: number;
  grain: string;
  first_season: string | null;
  last_season: string | null;
  completeness: "complete" | "partial";
  known_limitations: string | null;
  claim_scope: string;
}

export interface ArticleEvidenceSuggestion {
  evidence_item_id: string;
  id: number;
  suggestion_key: string;
  player_id: number;
  player_name: string;
  stat_definition_id: number;
  notability_policy_id: number;
  notability_policy_version: number;
  stat_key: string;
  stat_label: string;
  achievement_type: string;
  scope: string;
  computed_value: string;
  comparison_value: string | null;
  rank: number | null;
  phrasing: string | null;
  context: Record<string, unknown>;
  source: EvidenceSource;
  coverage_window: EvidenceCoverageWindow;
  verdict: {
    state: "approved";
    reviewed_at: string;
    reviewed_by: string;
  };
  fact_hash: string;
}

export interface EvidenceBundle {
  id: number;
  version: number;
  schema_version: string;
  content_hash: string;
  created_by: string;
  created_at: string;
  suggestions: ArticleEvidenceSuggestion[];
}

export interface ArticleDraftBlock {
  kind: "lead" | "body" | "closing";
  text: string;
  evidence_ids: string[];
}

export interface ArticleValidationFinding {
  code: string;
  severity: "error" | "warning";
  message: string;
  block_index: number | null;
  evidence_ids: string[];
}

export interface ArticleVersion {
  id: number;
  article_id: number;
  version: number;
  origin: "ai" | "human";
  parent_version_id: number | null;
  headline: string;
  headline_evidence_ids: string[];
  body: string;
  blocks: ArticleDraftBlock[];
  evidence_bundle_id: number;
  evidence_hash: string;
  style_guide_version_id: number;
  style_snapshot: Record<string, unknown>;
  style_hash: string;
  prompt_version: string | null;
  editor_instructions: string | null;
  provider: string | null;
  model: string | null;
  output_hash: string | null;
  validation_results: ArticleValidationFinding[];
  author: string | null;
  created_at: string;
  warning_overrides: ArticleWarningOverride[];
}

export interface ArticleWarningOverride {
  id: number;
  article_version_id: number;
  finding_code: string;
  reason: string;
  overridden_by: string;
  created_at: string;
}

export interface ArticleReadinessDecision {
  id: number;
  article_id: number;
  article_version_id: number;
  action: "ready" | "reopened";
  actor: string;
  reason: string | null;
  created_at: string;
}

export interface ArticleVersionCreate {
  base_version_id: number;
  headline: string;
  headline_evidence_ids: string[];
  blocks: ArticleDraftBlock[];
}

export interface ArticleReadyResult {
  article_id: number;
  status: "ready";
  ready_version: ArticleVersion;
  decision: ArticleReadinessDecision;
}

export interface ArticleGenerationJob {
  id: number;
  article_id: number;
  state: ArticleGenerationJobState;
  requested_by: string;
  attempt_count: number;
  evidence_bundle_id: number;
  style_guide_version_id: number;
  base_version_id: number | null;
  style_snapshot: {
    versions?: Array<{
      id: number;
      guide_key: string;
      version: number;
      name: string;
      scope_type: string;
      scope_value: string | null;
      content_hash: string;
    }>;
    [key: string]: unknown;
  };
  style_hash: string;
  provider: string;
  model: string;
  prompt_version: string;
  editor_instructions: string | null;
  input_hash: string;
  output_hash: string | null;
  validation_results: ArticleValidationFinding[];
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  article_version: ArticleVersion | null;
}

export interface ArticleBrief {
  id: number;
  status: ArticleStatus;
  article_type: ArticleType;
  angle: string;
  audience: string;
  constraints: string | null;
  created_by: string;
  created_at: string;
  game: ArticleGameEvidence;
  evidence_bundle: EvidenceBundle;
  latest_generation_job?: ArticleGenerationJob | null;
  latest_version?: ArticleVersion | null;
  ready_version?: ArticleVersion | null;
  versions: ArticleVersion[];
  readiness_history: ArticleReadinessDecision[];
}

export interface ArticleQueueItem {
  id: number;
  status: ArticleStatus;
  article_type: ArticleType;
  angle: string;
  owner: string;
  created_at: string;
  game_date: string | null;
  game_title: string | null;
  latest_version: ArticleVersion | null;
  ready_version: ArticleVersion | null;
}

export interface ArticleQueue {
  items: ArticleQueueItem[];
  total: number;
}
