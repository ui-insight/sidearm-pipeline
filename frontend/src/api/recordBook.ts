import { api } from "./client";
import type {
  LeaderboardScope,
  Leaderboard,
  LeaderboardStat,
  RecordBookMetricCatalog,
} from "../types/recordBook";

export const recordBookApi = {
  metrics: () => api.get<RecordBookMetricCatalog>("/record-book/metrics"),
  leaders: (statKey: LeaderboardStat, scope: LeaderboardScope, season?: string) => {
    const params: Record<string, string> = {
      scope,
      limit: "10",
    };
    if (scope === "season" && season) params.season = season;
    return api.get<Leaderboard>(`/record-book/leaders/${statKey}`, params);
  },
};
