export type AchievementReviewState = "pending" | "approved" | "rejected";

export interface AchievementSuggestion {
  id: number;
  game_id: number;
  player_id: number;
  player_name: string;
  stat_key: string;
  stat_label: string;
  suggestion_key: string;
  achievement_type: string;
  scope: string;
  computed_value: string;
  comparison_value: string | null;
  rank: number | null;
  deterministic_notability_score: string;
  context: Record<string, unknown>;
  coverage_context: Record<string, unknown>;
  phrasing: string | null;
  ai_rank: number | null;
  ai_model: string | null;
  ai_prompt_version: string | null;
  ai_output_hash: string | null;
  ai_ranked_at: string | null;
  source_url: string | null;
  reviewed_at: string | null;
  reviewed_by: string | null;
  state: AchievementReviewState;
}

export interface AchievementReviewGame {
  game_id: number;
  title: string | null;
  game_date: string | null;
  season: string | null;
  home_team: string | null;
  away_team: string | null;
  home_score: number | null;
  away_score: number | null;
  source_url: string;
  suggestions: AchievementSuggestion[];
}

export interface AchievementReviewQueue {
  items: AchievementReviewGame[];
  total_games: number;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
}
