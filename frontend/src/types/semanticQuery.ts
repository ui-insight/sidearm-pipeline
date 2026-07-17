import type {
  Leaderboard,
  LeaderboardStat,
  RecordBookMetric,
} from "./recordBook";

export type ConferenceScope = "all" | "conference" | "non_conference";

export interface SemanticWorkspaceOptions {
  program_slug: string;
  program_name: string;
  seasons: string[];
  metrics: RecordBookMetric[];
  leader_limits: number[];
  default_season: string | null;
  default_stat_key: LeaderboardStat | null;
}

export interface SemanticCoverage {
  grain: string;
  first_season: string | null;
  last_season: string | null;
  completeness: "complete" | "partial" | "unknown" | "unavailable";
  source_systems: string[];
  known_limitations: string[];
  verified_at: string | null;
  statement: string;
}

export interface TeamSeasonRecordGame {
  game_id: number;
  game_date: string | null;
  opponent: string;
  venue: string | null;
  conference_event: boolean;
  idaho_score: number;
  opponent_score: number;
  result: "win" | "loss" | "tie";
  source_url: string;
}

export interface TeamSeasonRecord {
  program_slug: string;
  program_name: string;
  season: string;
  conference_scope: ConferenceScope;
  games_played: number;
  wins: number;
  losses: number;
  ties: number;
  open_quality_issue_count: number;
  coverage: SemanticCoverage;
  games: TeamSeasonRecordGame[];
}

export interface TeamSeasonRecordResult {
  query_id: "team_season_record";
  result: TeamSeasonRecord;
}

export interface StatLeadersResult {
  query_id: "stat_leaders";
  result: Leaderboard;
}
