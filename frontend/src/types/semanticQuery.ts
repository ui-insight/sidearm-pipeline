import type {
  Leaderboard,
  LeaderboardStat,
  RecordBookMetric,
} from "./recordBook";

export type ConferenceScope = "all" | "conference" | "non_conference";
export type VenueScope = "all" | "home" | "away" | "neutral";

export interface SemanticWorkspacePlayer {
  player_id: number;
  player_name: string;
  seasons: string[];
}

export interface SemanticWorkspaceOpponent {
  opponent_name: string;
  seasons: string[];
}

export interface SemanticWorkspaceOptions {
  program_slug: string;
  program_name: string;
  seasons: string[];
  metrics: RecordBookMetric[];
  players: SemanticWorkspacePlayer[];
  opponents: SemanticWorkspaceOpponent[];
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
  opponent: string | null;
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

export interface OpponentLeaderboardLeader {
  rank: number;
  player_id: number;
  player_name: string;
  total: string;
  games_count: number;
  games: PlayerGameSplitGame[];
}

export interface OpponentStatLeaderboard {
  program_slug: string;
  program_name: string;
  stat_key: LeaderboardStat;
  stat_label: string;
  aggregation_method: string;
  season: string;
  conference_scope: ConferenceScope;
  opponent: string;
  total_players: number;
  open_quality_issue_count: number;
  coverage: SemanticCoverage;
  leaders: OpponentLeaderboardLeader[];
}

export interface OpponentStatLeadersResult {
  query_id: "opponent_stat_leaders";
  result: OpponentStatLeaderboard;
}

export interface PlayerGameSplitGame {
  game_id: number;
  game_date: string | null;
  season: string;
  opponent: string;
  venue: string | null;
  conference_event: boolean;
  value: string;
  source_snapshot_id: number | null;
  source_url: string | null;
}

export interface PlayerGameSplit {
  program_slug: string;
  program_name: string;
  player_id: number;
  player_name: string;
  stat_key: string;
  stat_label: string;
  aggregation_method: string;
  season: string | null;
  conference_scope: ConferenceScope;
  venue_scope: VenueScope;
  opponent: string | null;
  value: string | null;
  games_count: number;
  open_quality_issue_count: number;
  coverage: SemanticCoverage;
  games: PlayerGameSplitGame[];
}

export interface PlayerGameSplitResult {
  query_id: "player_game_split";
  result: PlayerGameSplit;
}
