import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { gamesApi } from "../api/games";
import { ApiError } from "../api/client";
import type { GameSummary } from "../types/game";

function formatScore(game: GameSummary): string {
  if (game.away_score === null || game.home_score === null) return "—";
  return `${game.away_score} – ${game.home_score}`;
}

function HomePage() {
  const [games, setGames] = useState<GameSummary[]>([]);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listLoading, setListLoading] = useState(true);

  const refresh = useCallback(async () => {
    setListLoading(true);
    try {
      const rows = await gamesApi.list();
      setGames(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load games");
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;

    async function loadInitialGames() {
      try {
        const rows = await gamesApi.list();
        if (!active) return;
        setGames(rows);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load games");
      } finally {
        if (active) {
          setListLoading(false);
        }
      }
    }

    void loadInitialGames();

    return () => {
      active = false;
    };
  }, []);

  async function handleIngest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await gamesApi.ingest(url.trim());
      setUrl("");
      await refresh();
    } catch (err) {
      const detail =
        err instanceof ApiError
          ? typeof err.data === "object" && err.data && "detail" in err.data
            ? String(err.data.detail)
            : err.message
          : err instanceof Error
            ? err.message
            : "Ingest failed";
      setError(detail);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this game?")) return;
    try {
      await gamesApi.remove(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto px-6 py-10">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Vandals Stats Pipeline
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Ingest Sidearm boxscore URLs and browse the normalized data.
          </p>
        </header>

        <section className="bg-white rounded-lg shadow-sm p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">
            Ingest a boxscore
          </h2>
          <form onSubmit={handleIngest} className="flex flex-col sm:flex-row gap-3">
            <input
              type="url"
              required
              placeholder="https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-yellow-500"
            />
            <button
              type="submit"
              disabled={loading}
              className="bg-yellow-500 hover:bg-yellow-600 disabled:opacity-50 text-gray-900 font-medium px-4 py-2 rounded-md text-sm transition"
            >
              {loading ? "Ingesting…" : "Ingest"}
            </button>
          </form>
          {error && (
            <p className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
              {error}
            </p>
          )}
        </section>

        <section className="bg-white rounded-lg shadow-sm">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">
              Ingested games
            </h2>
            <span className="text-xs text-gray-500">
              {games.length} record{games.length === 1 ? "" : "s"}
            </span>
          </div>
          {listLoading ? (
            <p className="p-6 text-sm text-gray-500">Loading…</p>
          ) : games.length === 0 ? (
            <p className="p-6 text-sm text-gray-500">
              No games yet. Paste a Sidearm boxscore URL above to ingest one.
            </p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {games.map((game) => (
                <li key={game.id} className="px-6 py-4 flex items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <Link
                      to={`/games/${game.id}`}
                      className="text-sm font-medium text-gray-900 hover:text-yellow-700 truncate block"
                    >
                      {game.away_team ?? "Away"} at {game.home_team ?? "Home"}
                    </Link>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {game.sport && (
                        <span className="uppercase mr-2">{game.sport}</span>
                      )}
                      {game.game_date ?? ""} · {game.season}
                    </p>
                  </div>
                  <span className="text-sm font-mono text-gray-800 tabular-nums">
                    {formatScore(game)}
                  </span>
                  <button
                    onClick={() => handleDelete(game.id)}
                    className="text-xs text-gray-400 hover:text-red-600"
                    aria-label={`Delete ${game.title ?? "game"}`}
                  >
                    Delete
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

export default HomePage;
