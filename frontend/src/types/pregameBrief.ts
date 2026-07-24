export interface BriefGame {
  game_id: number;
  game_date: string;
  opponent: string;
  venue: string;
  idaho_score: number;
  opponent_score: number;
  result: "win" | "loss" | "tie";
  source_url: string;
}

export interface BriefPlayerLeader {
  player_id: number;
  player_name: string;
  games_played: number;
  total_points: string;
  points_per_game: string;
  evidence: BriefGame[];
}

export interface HistoricalPregameBrief {
  program_name: string;
  season: string;
  as_of_date: string;
  target_game: BriefGame;
  season_record: {
    games_played: number;
    wins: number;
    losses: number;
    ties: number;
  };
  recent_form: BriefGame[];
  prior_meetings: BriefGame[];
  scoring_leaders: BriefPlayerLeader[];
  evidence_game_count: number;
  methodology: string;
}
