export interface ScheduleEvent {
  sport_slug: string;
  sport_name: string;
  gender: string | null;
  season: string | null;
  source_system: string;
  schedule_url: string;
  source_event_id: string | null;
  opponent_source_id: string | null;
  opponent_name: string | null;
  event_status: string;
  home_away_neutral: string | null;
  event_date: string | null;
  date_text: string | null;
  time_text: string | null;
  location_name: string | null;
  venue_name: string | null;
  conference_name: string | null;
  conference_event: boolean;
  result_status: string | null;
  team_score: number | null;
  opponent_score: number | null;
  source_urls: Record<string, string>;
  boxscore_url: string | null;
}
