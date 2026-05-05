import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ingestRunsApi } from "../api/ingestRuns";
import { ApiError } from "../api/client";
import type { IngestRun } from "../types/ingestRun";

const STATUS_STYLES: Record<string, string> = {
  succeeded: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  running: "bg-yellow-100 text-yellow-800",
};

const TRIGGER_LABELS: Record<string, string> = {
  manual: "Manual",
  scheduled: "Scheduled",
  manual_rerun: "Re-run",
};

function formatDuration(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>
      {status}
    </span>
  );
}

function IngestRunsPage() {
  const [runs, setRuns] = useState<IngestRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rerunningId, setRerunningId] = useState<number | null>(null);
  const [rerunError, setRerunError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await ingestRunsApi.list({ limit: 100 });
      setRuns(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load ingest runs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleRerun(run: IngestRun) {
    if (!run.game_id) return;
    setRerunningId(run.id);
    setRerunError(null);
    try {
      await ingestRunsApi.rerun(run.game_id);
      await refresh();
    } catch (err) {
      const detail =
        err instanceof ApiError
          ? typeof err.data === "object" && err.data && "detail" in err.data
            ? String(err.data.detail)
            : err.message
          : err instanceof Error
            ? err.message
            : "Re-run failed";
      setRerunError(detail);
    } finally {
      setRerunningId(null);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-6 py-10">
        <header className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Ingest Runs</h1>
            <p className="text-sm text-gray-600 mt-1">
              Recent ingestion attempts — both manual and scheduled.
            </p>
          </div>
          <div className="flex items-center gap-4">
            <Link
              to="/"
              className="text-sm text-gray-600 hover:text-yellow-700"
            >
              ← Dashboard
            </Link>
            <button
              type="button"
              onClick={refresh}
              disabled={loading}
              className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-gray-800 disabled:opacity-50"
            >
              {loading ? "Refreshing…" : "Refresh"}
            </button>
          </div>
        </header>

        {rerunError && (
          <p className="mb-6 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-4 py-3">
            {rerunError}
          </p>
        )}

        {error && (
          <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-4 py-3">
            {error}
          </p>
        )}

        {!loading && !error && runs.length === 0 && (
          <p className="text-sm text-gray-500">No ingest runs recorded yet.</p>
        )}

        {runs.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs uppercase text-gray-500">
                  <th className="px-4 py-3">Started</th>
                  <th className="px-4 py-3">Sport</th>
                  <th className="px-4 py-3">Trigger</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Duration</th>
                  <th className="px-4 py-3">Attempts</th>
                  <th className="px-4 py-3">Error</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {runs.map((run) => (
                  <tr key={run.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 whitespace-nowrap text-gray-700">
                      {formatDate(run.started_at)}
                    </td>
                    <td className="px-4 py-3 uppercase text-gray-700">
                      {run.sport ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {TRIGGER_LABELS[run.trigger_type] ?? run.trigger_type}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="px-4 py-3 font-mono text-gray-700">
                      {formatDuration(run.duration_ms)}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {run.attempt_count}/{run.max_attempts}
                    </td>
                    <td className="px-4 py-3 text-red-700 max-w-xs truncate">
                      {run.error_type
                        ? `${run.error_type}: ${run.error_message ?? ""}`
                        : null}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        {run.game_id && (
                          <Link
                            to={`/games/${run.game_id}`}
                            className="text-xs text-yellow-700 hover:underline"
                          >
                            View game
                          </Link>
                        )}
                        {run.game_id && (
                          <button
                            type="button"
                            onClick={() => handleRerun(run)}
                            disabled={rerunningId === run.id}
                            className="text-xs text-gray-500 hover:text-gray-900 disabled:opacity-50"
                          >
                            {rerunningId === run.id ? "Running…" : "Re-run"}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default IngestRunsPage;
