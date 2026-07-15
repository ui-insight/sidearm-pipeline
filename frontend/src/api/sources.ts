import { api } from "./client";
import type { GameSummary } from "../types/game";
import type { CurrentSeasonSync } from "../types/currentSeason";
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
};
