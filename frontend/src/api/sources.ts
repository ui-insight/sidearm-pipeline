import { api } from "./client";
import type { GameSummary } from "../types/game";
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
};
