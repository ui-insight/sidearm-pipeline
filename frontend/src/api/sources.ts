import { api } from "./client";
import type { GameSummary } from "../types/game";
import type { CurrentSeasonSync } from "../types/currentSeason";
import type {
  HistoricalRangeBackfill,
  HistoricalRangeRequest,
} from "../types/historicalBackfill";
import type { ScheduleEvent } from "../types/schedule";

export const sourcesApi = {
  schedule: (sportSlug: string, season?: string) =>
    api.get<ScheduleEvent[]>(
      `/sources/${sportSlug}/schedule`,
      season ? { season } : undefined,
    ),
  importSchedule: (sportSlug: string, season?: string) =>
    api.post<GameSummary[]>(
      `/sources/${sportSlug}/schedule/import${
        season ? `?season=${encodeURIComponent(season)}` : ""
      }`,
    ),
  syncSeason: (
    sportSlug: string,
    season: string,
    correctionLookback = 2,
  ) =>
    api.post<CurrentSeasonSync>(
      `/sources/${sportSlug}/seasons/${season}/sync?correction_lookback=${correctionLookback}`,
    ),
  backfillHistoricalWbbRange: (request: HistoricalRangeRequest) => {
    const params = new URLSearchParams({
      start_season: request.startSeason,
      end_season: request.endSeason,
      boxscore_delay_seconds: String(request.boxscoreDelaySeconds),
    });
    if (request.resumeRunId !== undefined) {
      params.set("resume_run_id", String(request.resumeRunId));
    }
    return api.post<HistoricalRangeBackfill>(
      `/sources/womens-basketball/historical-backfill?${params.toString()}`,
    );
  },
};
