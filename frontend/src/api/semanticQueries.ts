import { api } from "./client";
import type { LeaderboardStat } from "../types/recordBook";
import type {
  ConferenceScope,
  SemanticWorkspaceOptions,
  StatLeadersResult,
  TeamSeasonRecordResult,
} from "../types/semanticQuery";

export const semanticQueriesApi = {
  options: () =>
    api.get<SemanticWorkspaceOptions>("/semantic-queries/options"),

  teamSeasonRecord: (season: string, conferenceScope: ConferenceScope) =>
    api.post<TeamSeasonRecordResult>("/semantic-queries/execute", {
      query_id: "team_season_record",
      season,
      conference_scope: conferenceScope,
    }),

  statLeaders: (season: string, statKey: LeaderboardStat, limit: number) =>
    api.post<StatLeadersResult>("/semantic-queries/execute", {
      query_id: "stat_leaders",
      stat_key: statKey,
      scope: "season",
      season,
      limit,
    }),
};
