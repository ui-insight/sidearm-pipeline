import { api } from "./client";
import type { GameDetail, GameSummary, ValidationResult } from "../types/game";
import type { AgentRunRead } from "../types/agentRun";

export const gamesApi = {
  list: (params?: { publish_status?: string }) => {
    const searchParams: Record<string, string> = {};
    if (params?.publish_status !== undefined) {
      searchParams.publish_status = params.publish_status;
    }
    return api.get<GameSummary[]>(
      "/games",
      Object.keys(searchParams).length > 0 ? searchParams : undefined,
    );
  },
  get: (id: number) => api.get<GameDetail>(`/games/${id}`),
  ingest: (url: string) => api.post<GameDetail>("/games", { url }),
  remove: (id: number) => api.delete<void>(`/games/${id}`),
  generate: (id: number) => api.post<AgentRunRead>(`/games/${id}/generate`, {}),
  validate: (id: number) => api.post<ValidationResult>(`/games/${id}/validate`, {}),
  publish: (id: number) => api.post<GameDetail>(`/games/${id}/publish`, {}),
};
