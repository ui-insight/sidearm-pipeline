export type LeaderboardScope = "career" | "season";
export type LeaderboardStat = "points" | "total_rebounds" | "assists";

export interface RecordBookCoverage {
  first_season: string | null;
  last_season: string | null;
  completeness: "complete" | "partial" | "unknown" | "unavailable";
  source_systems: string[];
  known_limitations: string[];
  verified_at: string | null;
  statement: string;
}

export interface LeaderSeasonEvidence {
  season: string;
  value: string;
  source_snapshot_id: number | null;
  source_url: string | null;
}

export interface LeaderboardLeader {
  rank: number;
  player_id: number;
  player_name: string;
  total: string;
  seasons_count: number;
  season_breakdown: LeaderSeasonEvidence[];
}

export interface Leaderboard {
  program_slug: string;
  program_name: string;
  stat_key: LeaderboardStat;
  stat_label: string;
  scope: LeaderboardScope;
  season: string | null;
  available_seasons: string[];
  total_players: number;
  open_quality_issue_count: number;
  coverage: RecordBookCoverage;
  leaders: LeaderboardLeader[];
}
