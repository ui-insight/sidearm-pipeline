import { api } from "./client";
import type { GameDetail, GameSummary, GeneratedContent } from "../types/game";

export const gamesApi = {
  list: () => api.get<GameSummary[]>("/games"),
  get: (id: number) => api.get<GameDetail>(`/games/${id}`),
  ingest: (url: string) => api.post<GameDetail>("/games", { url }),
  remove: (id: number) => api.delete<void>(`/games/${id}`),
  generate: (id: number) =>
    api.post<GeneratedContent>(`/games/${id}/generate`, {}),
};
