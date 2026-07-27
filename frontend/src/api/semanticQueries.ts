import { api } from "./client";
import type { LeaderboardStat } from "../types/recordBook";
import type {
  ConferenceScope,
  OpponentStatLeadersResult,
  PlayerGameSplitResult,
  SemanticQuestionAnswer,
  SemanticWorkspaceOptions,
  StatLeadersResult,
  TeamSeasonRecordResult,
  VenueScope,
} from "../types/semanticQuery";

export const semanticQueriesApi = {
  options: () =>
    api.get<SemanticWorkspaceOptions>("/semantic-queries/options"),

  ask: (question: string) =>
    api.post<SemanticQuestionAnswer>("/semantic-queries/ask", { question }),

  teamSeasonRecord: (
    season: string,
    conferenceScope: ConferenceScope,
    opponent: string | null,
  ) =>
    api.post<TeamSeasonRecordResult>("/semantic-queries/execute", {
      query_id: "team_season_record",
      season,
      conference_scope: conferenceScope,
      ...(opponent ? { opponent } : {}),
    }),

  statLeaders: (season: string, statKey: LeaderboardStat, limit: number) =>
    api.post<StatLeadersResult>("/semantic-queries/execute", {
      query_id: "stat_leaders",
      stat_key: statKey,
      scope: "season",
      season,
      limit,
    }),

  opponentStatLeaders: (
    season: string,
    statKey: LeaderboardStat,
    conferenceScope: ConferenceScope,
    opponent: string,
    limit: number,
  ) =>
    api.post<OpponentStatLeadersResult>("/semantic-queries/execute", {
      query_id: "opponent_stat_leaders",
      stat_key: statKey,
      season,
      conference_scope: conferenceScope,
      opponent,
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
