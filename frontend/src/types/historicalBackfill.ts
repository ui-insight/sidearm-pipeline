export interface HistoricalSeasonCoverage {
  schedule_events_seen: number;
  final_games: number;
  final_games_with_boxscores: number;
  final_games_ingested: number;
  missing_boxscores: number;
  failed_boxscores: number;
  open_identity_issues: number;
  open_quality_issues: number;
  game_completeness: string;
  game_coverage_window_id: number | null;
}

export interface HistoricalRangeSeason {
  season: string;
  status: string;
  season_run_id: number | null;
  started_at: string;
  finished_at: string;
  coverage: HistoricalSeasonCoverage | null;
  error_type: string | null;
  error_message: string | null;
}

export interface HistoricalRangeBackfill {
  run_id: number;
  sport_slug: string;
  start_season: string;
  end_season: string;
  status: string;
  boxscore_delay_seconds: number;
  resumed: boolean;
  started_at: string;
  finished_at: string;
  seasons_total: number;
  seasons_attempted: number;
  seasons_skipped: number;
  seasons_succeeded: number;
  seasons_partial: number;
  seasons_failed: number;
  seasons: HistoricalRangeSeason[];
}

export interface HistoricalRangeRequest {
  startSeason: string;
  endSeason: string;
  boxscoreDelaySeconds: number;
  resumeRunId?: number;
}
