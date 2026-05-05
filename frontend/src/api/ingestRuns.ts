import { api } from "./client";
import type { IngestRun } from "../types/ingestRun";
import type { GameDetail } from "../types/game";

export const ingestRunsApi = {
  list(params?: { status?: string; limit?: number }): Promise<IngestRun[]> {
    const query: Record<string, string> = {};
    if (params?.status) query.status = params.status;
    if (params?.limit != null) query.limit = String(params.limit);
    return api.get<IngestRun[]>("/ingest-runs", query);
  },

  rerun(gameId: number): Promise<GameDetail> {
    return api.post<GameDetail>(`/games/${gameId}/ingest`);
  },
};
