import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { gamesApi } from "../api/games";
import { ApiError } from "../api/client";
import PublishStatusBadge from "../components/PublishStatusBadge";
import type { GameSummary } from "../types/game";

type FilterStatus = "all" | "draft" | "validated" | "published" | "errored";

const FILTER_OPTIONS: { value: FilterStatus; label: string }[] = [
  { value: "all", label: "All" },
  { value: "draft", label: "Draft" },
  { value: "validated", label: "Validated" },
  { value: "published", label: "Published" },
  { value: "errored", label: "Errors" },
];

function OperatorPage() {
  const [games, setGames] = useState<GameSummary[]>([]);
  const [filter, setFilter] = useState<FilterStatus>("all");
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [rowLoading, setRowLoading] = useState<Record<number, boolean>>({});
  const [rowError, setRowError] = useState<Record<number, string>>({});

  const loadGames = useCallback(async (status: FilterStatus) => {
    setListLoading(true);
    setListError(null);
    try {
      const params = status !== "all" ? { publish_status: status } : undefined;
      const rows = await gamesApi.list(params);
      setGames(rows);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Failed to load games");
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadGames(filter);
  }, [filter, loadGames]);

  async function handleValidate(game: GameSummary) {
    setRowLoading((prev) => ({ ...prev, [game.id]: true }));
    setRowError((prev) => {
      const next = { ...prev };
      delete next[game.id];
      return next;
    });
    try {
      const result = await gamesApi.validate(game.id);
      setGames((prev) =>
        prev.map((g) =>
          g.id === game.id
            ? {
                ...g,
                publish_status: result.publish_status,
                last_validated_at: result.validated_at,
              }
            : g,
        ),
      );
    } catch (err) {
      const detail =
        err instanceof ApiError
          ? typeof err.data === "object" && err.data && "detail" in err.data
            ? String(err.data.detail)
            : err.message
          : err instanceof Error
            ? err.message
            : "Validation failed";
      setRowError((prev) => ({ ...prev, [game.id]: detail }));
    } finally {
      setRowLoading((prev) => ({ ...prev, [game.id]: false }));
    }
  }

  async function handlePublish(game: GameSummary) {
    setRowLoading((prev) => ({ ...prev, [game.id]: true }));
    setRowError((prev) => {
      const next = { ...prev };
      delete next[game.id];
      return next;
    });
    try {
      const updated = await gamesApi.publish(game.id);
      setGames((prev) =>
        prev.map((g) =>
          g.id === game.id ? { ...g, publish_status: updated.publish_status } : g,
        ),
      );
    } catch (err) {
      const detail =
        err instanceof ApiError
          ? typeof err.data === "object" && err.data && "detail" in err.data
            ? String(err.data.detail)
            : err.message
          : err instanceof Error
            ? err.message
            : "Publish failed";
      setRowError((prev) => ({ ...prev, [game.id]: detail }));
    } finally {
      setRowLoading((prev) => ({ ...prev, [game.id]: false }));
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto px-6 py-10">
        <header className="mb-8 flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              Operator Review
            </h1>
            <p className="text-sm text-gray-600 mt-1">
              Validate and publish game records.
            </p>
          </div>
          <Link to="/" className="text-sm text-gray-500 hover:text-yellow-700 mt-1">
            ← Home
          </Link>
        </header>

        <div className="mb-6 flex flex-wrap gap-2">
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setFilter(opt.value)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
                filter === opt.value
                  ? "bg-gray-900 text-white"
                  : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {listError && (
          <p className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
            {listError}
          </p>
        )}

        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          {listLoading ? (
            <p className="p-6 text-sm text-gray-500">Loading…</p>
          ) : games.length === 0 ? (
            <p className="p-6 text-sm text-gray-500">No games match this filter.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs uppercase text-gray-500">
                  <th className="px-6 py-3">Title / Date / Sport</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Last Validated</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {games.map((game) => {
                  const loading = rowLoading[game.id] ?? false;
                  const err = rowError[game.id];
                  return (
                    <tr key={game.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <Link
                          to={`/games/${game.id}`}
                          className="font-medium text-gray-900 hover:text-yellow-700"
                        >
                          {game.title ??
                            `${game.away_team ?? "Away"} at ${game.home_team ?? "Home"}`}
                        </Link>
                        <p className="mt-0.5 text-xs text-gray-500">
                          {game.game_date ?? "—"}
                          {game.sport && ` · ${game.sport.toUpperCase()}`}
                        </p>
                        {err && (
                          <p className="mt-1 text-xs text-red-600">{err}</p>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        <PublishStatusBadge status={game.publish_status} />
                      </td>
                      <td className="px-4 py-4 text-xs text-gray-500">
                        {game.last_validated_at
                          ? new Date(game.last_validated_at).toLocaleString()
                          : "—"}
                      </td>
                      <td className="px-4 py-4 text-right">
                        <div className="inline-flex gap-2">
                          <button
                            type="button"
                            onClick={() => void handleValidate(game)}
                            disabled={loading}
                            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-50 disabled:opacity-50"
                          >
                            {loading ? "…" : "Validate"}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handlePublish(game)}
                            disabled={loading || game.publish_status !== "validated"}
                            className="rounded-md bg-yellow-500 px-3 py-1.5 text-xs font-medium text-gray-900 transition hover:bg-yellow-600 disabled:opacity-50"
                          >
                            {loading ? "…" : "Publish"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

export default OperatorPage;
