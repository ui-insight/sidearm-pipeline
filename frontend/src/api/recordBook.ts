import { api } from "./client";
import type {
  LeaderboardScope,
  PointsLeaderboard,
} from "../types/recordBook";

export const recordBookApi = {
  pointsLeaders: (scope: LeaderboardScope, season?: string) => {
    const params: Record<string, string> = {
      scope,
      limit: "10",
    };
    if (scope === "season" && season) params.season = season;
    return api.get<PointsLeaderboard>("/record-book/leaders/points", params);
  },
};
