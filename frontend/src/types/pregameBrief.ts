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
  team_name: string;
  jersey_number: string | null;
  position: string | null;
  class_year: string | null;
  bio_url: string | null;
  games_played: number;
  total: string;
  per_game: string;
  evidence: BriefGame[];
}

export interface BriefLeaderGroup {
  stat_key: string;
  label: string;
  context: string;
  leaders: BriefPlayerLeader[];
}

export interface PreviousMatchupPlayer {
  team_name: string;
  player_name: string;
  jersey_number: string | null;
  starter: boolean;
  minutes: number;
  points: number;
  rebounds: number;
  assists: number;
  steals: number;
  blocks: number;
}

export interface PreviousMatchupTeam {
  team_name: string;
  standouts: PreviousMatchupPlayer[];
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
  vandal_leader_groups: BriefLeaderGroup[];
  previous_matchup_teams: PreviousMatchupTeam[];
  evidence_game_count: number;
  methodology: string;
}
