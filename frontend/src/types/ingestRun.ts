export interface IngestRun {
  id: number;
  game_id: number | null;
  trigger_type: string;
  source_system: string;
  source_type: string;
  source_url: string;
  source_event_id: string | null;
  sport: string | null;
  season: string | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  attempt_count: number;
  max_attempts: number;
  http_status: number | null;
  retryable: boolean;
  error_type: string | null;
  error_message: string | null;
  run_metadata: Record<string, unknown>;
}
