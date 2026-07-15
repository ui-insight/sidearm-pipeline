import { api } from "./client";
import type {
  IdentityQueueItem,
  IdentityQueueStatus,
  IdentityResolution,
} from "../types/identityResolution";

export const identityResolutionApi = {
  list: (status: IdentityQueueStatus) =>
    api.get<IdentityQueueItem[]>("/identity-resolution/queue", { status }),
  resolve: (issueId: number, playerId: number, resolutionNotes: string) =>
    api.post<IdentityResolution>(
      `/identity-resolution/queue/${issueId}/resolve`,
      {
        player_id: playerId,
        resolution_notes: resolutionNotes,
      },
    ),
};
