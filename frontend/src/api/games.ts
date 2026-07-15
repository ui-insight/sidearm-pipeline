import { api } from "./client";
import type {
  GameDetail,
  GameSummary,
  GeneratedContent,
  NormalizedPlayerGameStat,
} from "../types/game";

export const gamesApi = {
  list: () => api.get<GameSummary[]>("/games"),
  get: (id: number) => api.get<GameDetail>(`/games/${id}`),
  playerStats: (id: number) =>
    api.get<NormalizedPlayerGameStat[]>(`/games/${id}/player-stats`),
  ingest: (url: string) => api.post<GameDetail>("/games", { url }),
  remove: (id: number) => api.delete<void>(`/games/${id}`),
  generate: (id: number) =>
    api.post<GeneratedContent>(`/games/${id}/generate`, {}),
};
