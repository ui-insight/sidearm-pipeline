export type IdentityQueueStatus =
  | "open"
  | "in_review"
  | "resolved"
  | "accepted_gap";

export interface IdentityCandidate {
  id: number;
  display_name: string;
}

export interface IdentityQueueItem {
  id: number;
  sport_program_id: number;
  game_id: number | null;
  player_id: number | null;
  team_id: number | null;
  source_snapshot_id: number | null;
  status: IdentityQueueStatus;
  severity: string;
  summary: string;
  details: Record<string, unknown>;
  detected_at: string;
  resolved_at: string | null;
  resolution_notes: string | null;
  candidate_players: IdentityCandidate[];
  resolved_player_name: string | null;
}

export interface IdentityResolution {
  issue_id: number;
  player_id: number;
  match_key: string;
  status: "resolved";
}

export interface IdentityPlayerCreation {
  displayName: string;
  resolutionNotes: string;
}
