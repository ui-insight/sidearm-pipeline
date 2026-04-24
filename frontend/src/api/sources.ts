import { api } from "./client";
import type { ScheduleEvent } from "../types/schedule";

export const sourcesApi = {
  schedule: (sportSlug: string, season?: string) =>
    api.get<ScheduleEvent[]>(
      `/sources/${sportSlug}/schedule`,
      season ? { season } : undefined,
    ),
};
