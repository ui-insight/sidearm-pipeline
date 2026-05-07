import { api } from "./client";
import type { AgentRunRead, AgentRunSummary, NLQueryResult } from "../types/agentRun";
import type { GeneratedContent } from "../types/game";

export const agentRunsApi = {
  list: (params?: { agent_name?: string; status?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.agent_name) search.set("agent_name", params.agent_name);
    if (params?.status) search.set("status", params.status);
    if (params?.limit != null) search.set("limit", String(params.limit));
    const qs = search.toString();
    return api.get<AgentRunSummary[]>(`/agent-runs${qs ? `?${qs}` : ""}`);
  },

  get: (id: number) => api.get<AgentRunRead>(`/agent-runs/${id}`),

  evaluate: (id: number) =>
    api.post<AgentRunRead>(`/agent-runs/${id}/evaluate`, {}),

  approve: (id: number) =>
    api.post<GeneratedContent>(`/agent-runs/${id}/verdict`, {
      verdict: "approved",
    }),

  reject: (id: number) =>
    api.post<AgentRunRead>(`/agent-runs/${id}/verdict`, {
      verdict: "rejected",
    }),
};

export const nlQueryApi = {
  query: (question: string) =>
    api.post<NLQueryResult>("/nl-query", { question }),
};
