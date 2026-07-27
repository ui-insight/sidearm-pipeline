export type ArticleType =
  | "game_recap"
  | "player_spotlight"
  | "achievement_story";

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

export interface ArticleBrief {
  id: number;
  status: "brief";
  article_type: ArticleType;
  angle: string;
  audience: string;
  constraints: string | null;
  created_by: string;
  created_at: string;
  game: ArticleGameEvidence;
  evidence_bundle: EvidenceBundle;
}
