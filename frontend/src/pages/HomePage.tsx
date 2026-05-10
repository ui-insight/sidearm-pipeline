import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { gamesApi } from "../api/games";
import { sourcesApi } from "../api/sources";
import { ApiError } from "../api/client";
import type { GameSummary } from "../types/game";
import type { ScheduleEvent } from "../types/schedule";

const SAMPLE_BOXSCORE_URL =
  "https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467";

const SPORT_OPTIONS = [
  { slug: "football", label: "Football", seasons: ["2025", "2026"] },
  { slug: "mens-basketball", label: "Men's Basketball", seasons: ["2025-26"] },
  {
    slug: "womens-basketball",
    label: "Women's Basketball",
    seasons: ["2025-26"],
  },
  { slug: "womens-soccer", label: "Women's Soccer", seasons: ["2025"] },
  { slug: "womens-volleyball", label: "Women's Volleyball", seasons: ["2025"] },
];
const DEFAULT_SPORT_SLUG = "football";
const DEFAULT_SEASON = "2025";

function formatScore(game: GameSummary): string {
  if (game.away_score === null || game.home_score === null) return "—";
  return `${game.away_score} – ${game.home_score}`;
}

function formatScheduleScore(event: ScheduleEvent): string | null {
  if (event.team_score === null || event.opponent_score === null) return null;
  return `${event.team_score} – ${event.opponent_score}`;
}

function formatStatus(status: string): string {
  return status.replace(/_/g, " ");
}

function HomePage() {
  const [games, setGames] = useState<GameSummary[]>([]);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [ingestingBoxscoreUrl, setIngestingBoxscoreUrl] = useState<string | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const [selectedSport, setSelectedSport] = useState(DEFAULT_SPORT_SLUG);
  const [selectedSeason, setSelectedSeason] = useState(DEFAULT_SEASON);
  const [scheduleEvents, setScheduleEvents] = useState<ScheduleEvent[]>([]);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [scheduleImporting, setScheduleImporting] = useState(false);
  const [scheduleLoaded, setScheduleLoaded] = useState(false);
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const [scheduleImportMessage, setScheduleImportMessage] = useState<string | null>(
    null,
  );
  const selectedSportOption =
    SPORT_OPTIONS.find((sport) => sport.slug === selectedSport) ??
    SPORT_OPTIONS[0]!;

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
    await ingestBoxscore(url.trim());
  }

  async function ingestBoxscore(boxscoreUrl: string) {
    if (!boxscoreUrl) return;
    setError(null);
    setLoading(true);
    setIngestingBoxscoreUrl(boxscoreUrl);
    try {
      await gamesApi.ingest(boxscoreUrl);
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
      setIngestingBoxscoreUrl(null);
    }
  }

  async function loadSchedule() {
    setScheduleLoading(true);
    setScheduleLoaded(false);
    setScheduleError(null);
    setScheduleImportMessage(null);
    try {
      const events = await sourcesApi.schedule(selectedSport, selectedSeason);
      setScheduleEvents(events);
      setScheduleLoaded(true);
    } catch (err) {
      const detail =
        err instanceof ApiError
          ? typeof err.data === "object" && err.data && "detail" in err.data
            ? String(err.data.detail)
            : err.message
          : err instanceof Error
            ? err.message
            : "Failed to load schedule";
      setScheduleError(detail);
    } finally {
      setScheduleLoading(false);
    }
  }

  async function importSchedule() {
    setScheduleImporting(true);
    setScheduleError(null);
    setScheduleImportMessage(null);
    try {
      const importedGames = await sourcesApi.importSchedule(
        selectedSport,
        selectedSeason,
      );
      setScheduleImportMessage(
        `Imported ${importedGames.length} schedule event${
          importedGames.length === 1 ? "" : "s"
        }.`,
      );
      await refresh();
    } catch (err) {
      const detail =
        err instanceof ApiError
          ? typeof err.data === "object" && err.data && "detail" in err.data
            ? String(err.data.detail)
            : err.message
          : err instanceof Error
            ? err.message
            : "Failed to import schedule";
      setScheduleError(detail);
    } finally {
      setScheduleImporting(false);
    }
  }

  function resetScheduleSelection() {
    setScheduleEvents([]);
    setScheduleLoaded(false);
    setScheduleError(null);
    setScheduleImportMessage(null);
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
        <header className="mb-8 flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              Vandals Stats Pipeline
            </h1>
            <p className="text-sm text-gray-600 mt-1">
              Ingest Sidearm boxscore URLs and browse the normalized data.
            </p>
          </div>
          <div className="flex flex-col items-end gap-1 mt-1">
            <Link
              to="/ingest-runs"
              className="text-sm text-gray-500 hover:text-yellow-700"
            >
              Ingest history →
            </Link>
            <Link
              to="/agent-runs"
              className="text-sm text-gray-500 hover:text-yellow-700"
            >
              Agent runs →
            </Link>
            <Link
              to="/query"
              className="text-sm text-gray-500 hover:text-yellow-700"
            >
              Query →
            </Link>
            <Link
              to="/operator"
              className="text-sm text-gray-500 hover:text-yellow-700"
            >
              Operator →
            </Link>
          </div>
        </header>

        <section className="bg-white rounded-lg shadow-sm p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">
            Ingest a boxscore
          </h2>
          <div className="mb-4 flex flex-col gap-2 rounded-md border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-gray-800 sm:flex-row sm:items-center sm:justify-between">
            <span>
              Need a test URL? Use the 2025 Idaho vs UC Davis football
              boxscore.
            </span>
            <button
              type="button"
              onClick={() => setUrl(SAMPLE_BOXSCORE_URL)}
              className="self-start rounded-md border border-yellow-400 bg-white px-3 py-1.5 text-sm font-medium text-gray-900 transition hover:bg-yellow-100 sm:self-auto"
            >
              Use sample boxscore
            </button>
          </div>
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

        <section className="bg-white rounded-lg shadow-sm p-6 mb-8">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                Discover schedule
              </h2>
              <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,16rem)_8rem]">
                <div>
                  <label
                    htmlFor="sport-source"
                    className="block text-xs font-medium uppercase text-gray-500"
                  >
                    Sport
                  </label>
                  <select
                    id="sport-source"
                    value={selectedSport}
                    onChange={(event) => {
                      const sport = SPORT_OPTIONS.find(
                        (option) => option.slug === event.target.value,
                      );
                      setSelectedSport(event.target.value);
                      setSelectedSeason(sport?.seasons[0] ?? DEFAULT_SEASON);
                      resetScheduleSelection();
                    }}
                    className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-yellow-500"
                  >
                    {SPORT_OPTIONS.map((sport) => (
                      <option key={sport.slug} value={sport.slug}>
                        {sport.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="schedule-season"
                    className="block text-xs font-medium uppercase text-gray-500"
                  >
                    Season
                  </label>
                  <select
                    id="schedule-season"
                    value={selectedSeason}
                    onChange={(event) => {
                      setSelectedSeason(event.target.value);
                      resetScheduleSelection();
                    }}
                    className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-yellow-500"
                  >
                    {selectedSportOption.seasons.map((season) => (
                      <option key={season} value={season}>
                        {season}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                onClick={loadSchedule}
                disabled={scheduleLoading || scheduleImporting}
                className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-gray-800 disabled:opacity-50"
              >
                {scheduleLoading ? "Loading…" : "Load schedule"}
              </button>
              <button
                type="button"
                onClick={importSchedule}
                disabled={scheduleLoading || scheduleImporting}
                className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-900 transition hover:bg-gray-50 disabled:opacity-50"
              >
                {scheduleImporting ? "Importing…" : "Import schedule"}
              </button>
            </div>
          </div>

          {scheduleError && (
            <p className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
              {scheduleError}
            </p>
          )}

          {scheduleImportMessage && (
            <p className="mb-4 text-sm text-green-800 bg-green-50 border border-green-200 rounded px-3 py-2">
              {scheduleImportMessage}
            </p>
          )}

          {scheduleLoaded && scheduleEvents.length === 0 && (
            <p className="text-sm text-gray-500">No schedule events found.</p>
          )}

          {scheduleEvents.length > 0 && (
            <ul className="divide-y divide-gray-100 border-t border-gray-100">
              {scheduleEvents.map((event) => {
                const score = formatScheduleScore(event);
                return (
                  <li
                    key={`${event.sport_slug}-${event.source_event_id ?? event.opponent_name}`}
                    className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-medium text-gray-900">
                          {event.opponent_name ?? "Opponent TBD"}
                        </p>
                        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs uppercase text-gray-600">
                          {formatStatus(event.event_status)}
                        </span>
                        {score && (
                          <span className="font-mono text-xs text-gray-700">
                            {score}
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-xs text-gray-500">
                        {event.event_date ?? event.date_text ?? "Date TBD"}
                        {event.home_away_neutral &&
                          ` · ${event.home_away_neutral}`}
                        {event.location_name && ` · ${event.location_name}`}
                      </p>
                    </div>
                    {event.boxscore_url ? (
                      <button
                        type="button"
                        onClick={() => ingestBoxscore(event.boxscore_url ?? "")}
                        disabled={loading}
                        className="self-start rounded-md bg-yellow-500 px-3 py-1.5 text-sm font-medium text-gray-900 transition hover:bg-yellow-600 disabled:opacity-50 sm:self-auto"
                      >
                        {ingestingBoxscoreUrl === event.boxscore_url
                          ? "Ingesting…"
                          : "Ingest boxscore"}
                      </button>
                    ) : (
                      <span className="self-start rounded-md border border-gray-200 px-3 py-1.5 text-sm text-gray-400 sm:self-auto">
                        No boxscore
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
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
