import { api } from "./client";
import type {
  IdentityPlayerCreation,
  IdentityQueueFilters,
  IdentityQueuePage,
  IdentityResolution,
} from "../types/identityResolution";

export const identityResolutionApi = {
  list: (filters: IdentityQueueFilters) => {
    const params: Record<string, string> = {
      status: filters.status,
      limit: String(filters.limit),
      offset: String(filters.offset),
    };
    if (filters.season) params.season = filters.season;
    if (filters.institution) params.institution = filters.institution;
    if (filters.gameId) params.game_id = filters.gameId;
    return api.get<IdentityQueuePage>("/identity-resolution/queue/page", params);
  },
  resolve: (issueId: number, playerId: number, resolutionNotes: string) =>
    api.post<IdentityResolution>(
      `/identity-resolution/queue/${issueId}/resolve`,
      {
        player_id: playerId,
        resolution_notes: resolutionNotes,
      },
    ),
  createPlayer: (issueId: number, player: IdentityPlayerCreation) =>
    api.post<IdentityResolution>(
      `/identity-resolution/queue/${issueId}/create-player`,
      {
        display_name: player.displayName,
        resolution_notes: player.resolutionNotes,
      },
    ),
};
