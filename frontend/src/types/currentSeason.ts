export interface CurrentSeasonRosterSummary {
  source_url: string;
  season: string;
  source_snapshot_id: number;
  players_seen: number;
  players_created: number;
  identities_created: number;
  player_seasons_created: number;
  player_seasons_updated: number;
  quality_issues_created: number;
}

export interface CurrentSeasonGameRefresh {
  game_id: number;
  title: string;
  source_url: string;
  reasons: string[];
  status: "refreshed" | "failed";
  error: string | null;
}

export interface CurrentSeasonSync {
  run_id: number;
  sport_slug: string;
  season: string;
  status: "succeeded" | "partial";
  correction_lookback: number;
  started_at: string;
  finished_at: string;
  roster: CurrentSeasonRosterSummary;
  schedule_events_seen: number;
  schedule_games_created: number;
  schedule_games_changed: number;
  schedule_games_unchanged: number;
  final_boxscores_seen: number;
  boxscores_selected: number;
  boxscores_refreshed: number;
  boxscores_skipped: number;
  boxscores_failed: number;
  open_identity_issues: number;
  games: CurrentSeasonGameRefresh[];
}
