export interface TeamStat {
  stat_name: string;
  home_value: string | null;
  away_value: string | null;
  sort_order: number;
}

export interface PlayerStatGroup {
  category: string;
  team: string | null;
  columns: string[];
  rows: string[][];
}

export interface ScoringPlay {
  period: string | null;
  clock: string | null;
  team: string | null;
  description: string | null;
  home_score: number | null;
  away_score: number | null;
  sort_order: number;
}

export interface GameSummary {
  id: number;
  source_url: string;
  canonical_uid: string;
  source_system: string;
  source_event_id: string | null;
  sport: string | null;
  sport_name: string | null;
  gender: string | null;
  season: string | null;
  game_date: string | null;
  event_shape: string;
  event_status: string;
  publish_status: string;
  home_team: string | null;
  away_team: string | null;
  home_score: number | null;
  away_score: number | null;
  title: string | null;
  start_at: string | null;
  end_at: string | null;
  timezone: string | null;
  location_name: string | null;
  venue_name: string | null;
  home_away_neutral: string | null;
  conference_event: boolean;
  exhibition: boolean;
  first_seen_at: string | null;
  last_seen_at: string | null;
  last_successful_ingest_at: string | null;
  ingested_at: string;
  last_validated_at: string | null;
}

export interface EventSource {
  source_type: string;
  source_url: string;
  source_id: string | null;
  primary_source: boolean;
  discovered_at: string;
  last_fetched_at: string | null;
}

export interface SourceSnapshot {
  parser_version: string;
  content_hash: string;
  http_status: number | null;
  fetched_at: string;
}

export interface EventStatusHistory {
  from_status: string | null;
  to_status: string;
  reason: string | null;
  changed_at: string;
}

export interface GeneratedContent {
  id: number;
  game_id: number;
  recap: string;
  spotlight_player: string | null;
  spotlight_body: string;
  social_post: string;
  headline: string | null;
  model: string | null;
  generated_at: string;
}

export interface ValidationCheck {
  rule: string;
  passed: boolean;
  detail: string | null;
}

export interface ValidationResult {
  game_id: number;
  passed: boolean;
  publish_status: string;
  checks: ValidationCheck[];
  validated_at: string;
}

export interface PublishEvent {
  id: number;
  game_id: number;
  from_status: string;
  to_status: string;
  trigger: string;
  detail: Record<string, unknown>;
  changed_at: string;
}

import type { AgentRunSummary } from "./agentRun";

export interface GameDetail extends GameSummary {
  team_stats: TeamStat[];
  player_stats: PlayerStatGroup[];
  scoring_plays: ScoringPlay[];
  event_sources: EventSource[];
  source_snapshots: SourceSnapshot[];
  status_history: EventStatusHistory[];
  generated_content: GeneratedContent[];
  agent_runs: AgentRunSummary[];
  publish_events: PublishEvent[];
}
