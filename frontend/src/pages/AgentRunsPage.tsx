import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { agentRunsApi } from "../api/agentRuns";
import type { AgentRunEvaluation, AgentRunSummary } from "../types/agentRun";

function statusColor(status: string): string {
  switch (status) {
    case "succeeded":
      return "text-green-700 bg-green-50 border-green-200";
    case "failed":
      return "text-red-700 bg-red-50 border-red-200";
    case "running":
      return "text-blue-700 bg-blue-50 border-blue-200";
    default:
      return "text-gray-600 bg-gray-50 border-gray-200";
  }
}

function verdictBadge(verdict: "approved" | "rejected" | null): string {
  if (verdict === "approved") return "text-green-700 bg-green-50 border-green-200";
  if (verdict === "rejected") return "text-red-700 bg-red-50 border-red-200";
  return "text-gray-400 bg-gray-50 border-gray-200";
}

function scoreBar(score: number | null): React.ReactNode {
  if (score === null) return <span className="text-gray-400 text-xs">—</span>;
  const pct = Math.round(score * 100);
  const color =
    pct >= 80 ? "bg-green-500" : pct >= 50 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-600 tabular-nums">{pct}%</span>
    </div>
  );
}

function metricBars(evals: AgentRunEvaluation[]): React.ReactNode {
  if (evals.length === 0) return null;
  return (
    <div className="mt-1 space-y-0.5">
      {evals.map((ev) => {
        const ok = ev.passed ?? (ev.score != null && ev.score >= 0.5);
        return (
          <div key={ev.id} className="flex items-center gap-1.5">
            <span className="text-xs text-gray-400 w-24 truncate">{ev.metric_name}</span>
            {ev.score != null ? (
              <>
                <div className="w-8 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${ok ? "bg-green-400" : "bg-red-400"}`}
                    style={{ width: `${Math.round(ev.score * 100)}%` }}
                  />
                </div>
                <span className="text-xs text-gray-400 tabular-nums">
                  {Math.round(ev.score * 100)}%
                </span>
              </>
            ) : (
              <span className="text-xs">{ok ? "✓" : "✗"}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

function AgentRunsPage() {
  const [runs, setRuns] = useState<AgentRunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    agentRunsApi
      .list()
      .then((rows) => {
        if (active) setRuns(rows);
      })
      .catch((err) => {
        if (active)
          setError(err instanceof Error ? err.message : "Failed to load agent runs");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="max-w-6xl mx-auto px-6 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Agent Runs</h1>
        <p className="text-sm text-gray-500 mt-1">
          Full provenance log for every AI agent invocation.
        </p>
      </header>

      {error && (
        <p className="mb-6 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {error}
        </p>
      )}

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {loading ? (
          <p className="p-6 text-sm text-gray-500">Loading…</p>
        ) : runs.length === 0 ? (
          <p className="p-6 text-sm text-gray-500">No agent runs yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Agent</th>
                <th className="px-4 py-3">Model</th>
                <th className="px-4 py-3">Game</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Eval</th>
                <th className="px-4 py-3">Verdict</th>
                <th className="px-4 py-3">Started</th>
                <th className="px-4 py-3">ms</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.id}
                  className="border-t border-gray-100 even:bg-gray-50 hover:bg-gray-50"
                >
                  <td className="px-4 py-3 font-mono text-gray-500">#{run.id}</td>
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {run.agent_name}
                  </td>
                  <td className="px-4 py-3">
                    <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded font-mono">
                      {run.model}
                    </code>
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {run.game_id != null ? (
                      <Link
                        to={`/games/${run.game_id}`}
                        className="hover:text-yellow-700 underline"
                      >
                        #{run.game_id}
                      </Link>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${statusColor(run.status)}`}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {scoreBar(run.eval_score)}
                    {metricBars(run.evaluations)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block rounded-full border px-2 py-0.5 text-xs ${verdictBadge(run.human_verdict)}`}
                    >
                      {run.human_verdict ?? "pending"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                    {new Date(run.started_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500 tabular-nums">
                    {run.duration_ms != null ? run.duration_ms : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default AgentRunsPage;
