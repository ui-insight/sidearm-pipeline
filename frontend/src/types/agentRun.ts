export interface AgentRunStep {
  id: number;
  agent_run_id: number;
  step_name: string;
  step_order: number;
  input_snapshot: Record<string, unknown> | null;
  output_snapshot: Record<string, unknown> | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  error_message: string | null;
}

export interface AgentRunEvaluation {
  id: number;
  agent_run_id: number;
  eval_type: string;
  metric_name: string;
  passed: boolean | null;
  score: number | null;
  detail: Record<string, unknown> | null;
  evaluated_at: string;
}

export interface AgentRunRead {
  id: number;
  agent_name: string;
  model: string;
  prompt_version: string;
  game_id: number | null;
  trigger: string;
  input_payload: Record<string, unknown> | null;
  output_payload: Record<string, unknown> | null;
  status: string;
  eval_score: number | null;
  human_verdict: "approved" | "rejected" | null;
  human_verdict_at: string | null;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  run_metadata: Record<string, unknown>;
  steps: AgentRunStep[];
  evaluations: AgentRunEvaluation[];
}

export interface AgentRunSummary {
  id: number;
  agent_name: string;
  model: string;
  status: string;
  eval_score: number | null;
  human_verdict: "approved" | "rejected" | null;
  started_at: string;
  duration_ms: number | null;
  game_id: number | null;
  evaluations: AgentRunEvaluation[];
}

export interface NLQueryResult {
  question: string;
  sql: string | null;
  rows: Record<string, unknown>[];
  answer: string;
  agent_run_id: number;
}
