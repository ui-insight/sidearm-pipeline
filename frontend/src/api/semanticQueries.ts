import { api } from "./client";
import type { LeaderboardStat } from "../types/recordBook";
import type {
  ConferenceScope,
  PlayerGameSplitResult,
  SemanticWorkspaceOptions,
  StatLeadersResult,
  TeamSeasonRecordResult,
  VenueScope,
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

  playerGameSplit: (
    playerId: number,
    season: string,
    statKey: LeaderboardStat,
    conferenceScope: ConferenceScope,
    venueScope: VenueScope,
    opponent: string | null,
  ) =>
    api.post<PlayerGameSplitResult>("/semantic-queries/execute", {
      query_id: "player_game_split",
      player_id: playerId,
      stat_key: statKey,
      season,
      conference_scope: conferenceScope,
      venue_scope: venueScope,
      ...(opponent ? { opponent } : {}),
    }),
};
