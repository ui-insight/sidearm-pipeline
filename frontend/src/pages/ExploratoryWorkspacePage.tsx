import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { semanticQueriesApi } from "../api/semanticQueries";
import type { Leaderboard } from "../types/recordBook";
import type {
  ConferenceScope,
  OpponentStatLeaderboard,
  SemanticWorkspaceOptions,
  TeamSeasonRecord,
} from "../types/semanticQuery";
import { buildWorkspaceCsv } from "../utils/workspaceCsv";
import WorkspaceViewNav from "../components/WorkspaceViewNav";
import WorkspaceViewActions from "../components/WorkspaceViewActions";

const RECORD_SCOPES: { value: ConferenceScope; label: string }[] = [
  { value: "all", label: "All games" },
  { value: "conference", label: "Conference" },
  { value: "non_conference", label: "Non-conference" },
];

function isConferenceScope(value: string | null): value is ConferenceScope {
  return RECORD_SCOPES.some((scope) => scope.value === value);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "The season desk could not be loaded.";
}

function formatValue(value: string): string {
  const number = Number(value);
  return Number.isFinite(number)
    ? new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(
        number,
      )
    : value;
}

function fileSlug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function SeasonDeskSkeleton() {
  return (
    <div
      className="animate-pulse border-y border-gray-200 bg-white"
      role="status"
      aria-label="Loading season desk"
    >
      <div className="border-b border-gray-200 px-5 py-7 sm:px-7">
        <div className="h-3 w-24 rounded bg-gray-200" />
        <div className="mt-4 h-8 max-w-xl rounded bg-gray-200" />
        <div className="mt-3 h-4 max-w-md rounded bg-gray-100" />
      </div>
      <div className="grid divide-y divide-gray-200 lg:grid-cols-2 lg:divide-x lg:divide-y-0">
        {[0, 1].map((section) => (
          <div key={section} className="space-y-5 px-5 py-6 sm:px-7">
            <div className="h-5 w-36 rounded bg-gray-200" />
            {[0, 1, 2, 3].map((row) => (
              <div key={row} className="h-8 rounded bg-gray-100" />
            ))}
          </div>
        ))}
      </div>
      <span className="sr-only">Loading season desk</span>
    </div>
  );
}

function QualitySummary({ count }: { count: number }) {
  return (
    <span
      className={
        count === 0
          ? "font-semibold text-emerald-700"
          : "font-semibold text-amber-700"
      }
    >
      {count === 0
        ? "No open quality issues"
        : `${count} open quality ${count === 1 ? "issue" : "issues"}`}
    </span>
  );
}

function ExploratoryWorkspacePage() {
  const [options, setOptions] = useState<SemanticWorkspaceOptions | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const [record, setRecord] = useState<TeamSeasonRecord | null>(null);
  const [leaderboard, setLeaderboard] = useState<
    Leaderboard | OpponentStatLeaderboard | null
  >(null);
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [loadingResults, setLoadingResults] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const requestedSeason = searchParams.get("season");
  const season =
    options?.seasons.find((candidate) => candidate === requestedSeason) ??
    options?.default_season ??
    options?.seasons[0] ??
    "";
  const requestedStatKey = searchParams.get("stat");
  const statKey =
    options?.metrics.find((metric) => metric.stat_key === requestedStatKey)
      ?.stat_key ??
    options?.default_stat_key ??
    options?.metrics[0]?.stat_key ??
    "";
  const requestedScope = searchParams.get("scope");
  const conferenceScope = isConferenceScope(requestedScope)
    ? requestedScope
    : "all";
  const requestedLimit = Number(searchParams.get("limit"));
  const leaderLimit = options?.leader_limits.includes(requestedLimit)
    ? requestedLimit
    : (options?.leader_limits.find((limit) => limit === 10) ??
      options?.leader_limits[0] ??
      10);
  const availableOpponents = useMemo(
    () =>
      (options?.opponents ?? []).filter((opponent) =>
        opponent.seasons.includes(season),
      ),
    [options, season],
  );
  const requestedOpponent = searchParams.get("opponent");
  const opponent =
    requestedOpponent &&
    (requestedOpponent === "all" ||
      availableOpponents.some(
        (candidate) => candidate.opponent_name === requestedOpponent,
      ))
      ? requestedOpponent
      : "all";
  const opponentName = opponent === "all" ? null : opponent;
  const currentViewParams = {
    season,
    stat: statKey,
    scope: conferenceScope,
    opponent,
    limit: String(leaderLimit),
  };

  const selectedMetric = useMemo(
    () => options?.metrics.find((metric) => metric.stat_key === statKey),
    [options, statKey],
  );

  useEffect(() => {
    let active = true;

    async function loadOptions() {
      setLoadingOptions(true);
      setError(null);
      try {
        const nextOptions = await semanticQueriesApi.options();
        if (!active) return;
        setOptions(nextOptions);
      } catch (loadError) {
        if (!active) return;
        setOptions(null);
        setRecord(null);
        setLeaderboard(null);
        setError(errorMessage(loadError));
      } finally {
        if (active) setLoadingOptions(false);
      }
    }

    void loadOptions();
    return () => {
      active = false;
    };
  }, [reloadKey]);

  useEffect(() => {
    if (!season || !statKey) return;
    let active = true;

    async function loadResults() {
      setLoadingResults(true);
      setError(null);
      try {
        const [recordResponse, leadersResponse] = await Promise.all([
          semanticQueriesApi.teamSeasonRecord(
            season,
            conferenceScope,
            opponentName,
          ),
          opponentName
            ? semanticQueriesApi.opponentStatLeaders(
                season,
                statKey,
                conferenceScope,
                opponentName,
                leaderLimit,
              )
            : semanticQueriesApi.statLeaders(season, statKey, leaderLimit),
        ]);
        if (!active) return;
        setRecord(recordResponse.result);
        setLeaderboard(leadersResponse.result);
      } catch (loadError) {
        if (!active) return;
        setRecord(null);
        setLeaderboard(null);
        setError(errorMessage(loadError));
      } finally {
        if (active) setLoadingResults(false);
      }
    }

    void loadResults();
    return () => {
      active = false;
    };
  }, [
    conferenceScope,
    leaderLimit,
    opponentName,
    reloadKey,
    season,
    statKey,
  ]);

  useEffect(() => {
    if (!options || !season || !statKey) return;
    const canonicalParams = {
      season,
      stat: statKey,
      scope: conferenceScope,
      opponent,
      limit: String(leaderLimit),
    };
    const canonicalSearch = new URLSearchParams(canonicalParams).toString();
    if (canonicalSearch !== searchParams.toString()) {
      setSearchParams(canonicalParams, { replace: true });
    }
  }, [
    conferenceScope,
    leaderLimit,
    options,
    opponent,
    searchParams,
    season,
    setSearchParams,
    statKey,
  ]);

  function updateViewParams(changes: Record<string, string>) {
    setSearchParams({ ...currentViewParams, ...changes });
  }

  function exportCsv() {
    if (!record || !leaderboard) return;
    const blob = new Blob([buildWorkspaceCsv(record, leaderboard)], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    const opponentPart = opponentName ? `-${fileSlug(opponentName)}` : "";
    link.download = `wbb-${season}-${statKey}-${conferenceScope}${opponentPart}.csv`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  const isEmpty =
    !loadingOptions &&
    !error &&
    options !== null &&
    (options.seasons.length === 0 || options.metrics.length === 0);
  const hasResults = record !== null && leaderboard !== null;
  const scopeLabel =
    RECORD_SCOPES.find((scope) => scope.value === conferenceScope)?.label ??
    "Selected";
  const opponentLabel = opponentName ?? "All opponents";
  const maximumLeaderValue = Math.max(
    ...((leaderboard?.leaders ?? []).map((leader) => Number(leader.total)) || [
      0,
    ]),
    1,
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <header className="max-w-3xl">
        <p className="text-xs font-black uppercase tracking-[0.14em] text-amber-700">
          Exploratory workspace
        </p>
        <h1 className="mt-2 text-3xl font-black tracking-tight text-gray-950 sm:text-4xl">
          Season desk
        </h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-gray-600">
          Answer a season question with the team record, statistical leaders,
          and source evidence kept together on one working surface.
        </p>
      </header>
      <WorkspaceViewNav />

      {options && !isEmpty ? (
        <WorkspaceViewActions view="season" params={currentViewParams} />
      ) : null}

      {options && !isEmpty ? (
        <section
          aria-label="Workspace filters"
          className="mt-8 border-y border-gray-300 bg-white px-4 py-4 sm:px-5"
        >
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 lg:items-end xl:grid-cols-[0.85fr_1.15fr_1.15fr_1.05fr_0.7fr_auto]">
            <label className="text-xs font-bold uppercase tracking-[0.06em] text-gray-600">
              Season
              <select
                value={season}
                onChange={(event) =>
                  updateViewParams({ season: event.target.value })
                }
                className="mt-1.5 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-gray-950 focus:border-yellow-500 focus:outline-2 focus:outline-offset-1 focus:outline-yellow-500"
              >
                {options.seasons.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-bold uppercase tracking-[0.06em] text-gray-600">
              Statistic
              <select
                value={statKey}
                onChange={(event) =>
                  updateViewParams({ stat: event.target.value })
                }
                className="mt-1.5 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-gray-950 focus:border-yellow-500 focus:outline-2 focus:outline-offset-1 focus:outline-yellow-500"
              >
                {options.metrics.map((metric) => (
                  <option key={metric.stat_key} value={metric.stat_key}>
                    {metric.display_label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-bold uppercase tracking-[0.06em] text-gray-600">
              Opponent
              <select
                value={opponent}
                onChange={(event) =>
                  updateViewParams({ opponent: event.target.value })
                }
                className="mt-1.5 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-gray-950 focus:border-yellow-500 focus:outline-2 focus:outline-offset-1 focus:outline-yellow-500"
              >
                <option value="all">All opponents</option>
                {availableOpponents.map((option) => (
                  <option
                    key={option.opponent_name}
                    value={option.opponent_name}
                  >
                    {option.opponent_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-bold uppercase tracking-[0.06em] text-gray-600">
              Game scope
              <select
                value={conferenceScope}
                onChange={(event) =>
                  updateViewParams({ scope: event.target.value })
                }
                className="mt-1.5 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-gray-950 focus:border-yellow-500 focus:outline-2 focus:outline-offset-1 focus:outline-yellow-500"
              >
                {RECORD_SCOPES.map((scope) => (
                  <option key={scope.value} value={scope.value}>
                    {scope.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-bold uppercase tracking-[0.06em] text-gray-600">
              Leaders
              <select
                value={leaderLimit}
                onChange={(event) =>
                  updateViewParams({ limit: event.target.value })
                }
                className="mt-1.5 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-gray-950 focus:border-yellow-500 focus:outline-2 focus:outline-offset-1 focus:outline-yellow-500"
              >
                {options.leader_limits.map((limit) => (
                  <option key={limit} value={limit}>
                    Top {limit}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={exportCsv}
              disabled={!hasResults || loadingResults}
              className="rounded-md bg-gray-950 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:bg-gray-300 disabled:text-gray-500"
            >
              Export CSV
            </button>
          </div>
        </section>
      ) : null}

      {loadingOptions || loadingResults ? (
        <div className="mt-8">
          <SeasonDeskSkeleton />
        </div>
      ) : null}

      {error && !loadingOptions && !loadingResults ? (
        <section
          role="alert"
          className="mt-8 border-l-4 border-red-600 bg-red-50 px-5 py-5"
        >
          <h2 className="text-base font-bold text-red-950">
            Season desk unavailable
          </h2>
          <p className="mt-1 text-sm leading-6 text-red-800">{error}</p>
          <button
            type="button"
            onClick={() => setReloadKey((key) => key + 1)}
            className="mt-4 rounded-md border border-red-300 bg-white px-3 py-2 text-sm font-bold text-red-900 hover:border-red-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
          >
            Try again
          </button>
        </section>
      ) : null}

      {isEmpty ? (
        <section className="mt-8 border-y border-gray-300 bg-white px-5 py-10 text-center">
          <h2 className="text-xl font-bold text-gray-950">
            No season evidence is ready yet
          </h2>
          <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-gray-600">
            Load a season and its player totals before using this workspace.
          </p>
          <Link
            to="/backfills"
            className="mt-5 inline-block rounded-md bg-gray-950 px-4 py-2.5 text-sm font-bold text-white hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
          >
            Open backfills
          </Link>
        </section>
      ) : null}

      {!loadingOptions && !loadingResults && !error && hasResults ? (
        <article className="mt-8 border-y border-gray-300 bg-white">
          <header className="border-b border-gray-300 px-5 py-6 sm:px-7 sm:py-7">
            <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">
              {scopeLabel} · {opponentLabel} · {record.games_played}{" "}
              {record.games_played === 1 ? "game" : "games"} reviewed
            </p>
            <h2 className="mt-2 text-2xl font-black tracking-tight text-gray-950 sm:text-3xl">
              Idaho finished {record.wins}–{record.losses}
              {record.ties > 0 ? `–${record.ties}` : ""} in {record.season}
              {opponentName ? ` against ${opponentName}` : ""}.
            </h2>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm leading-6 text-gray-600">
              <span>{record.coverage.statement}</span>
              <QualitySummary count={record.open_quality_issue_count} />
            </div>
          </header>

          <div className="grid divide-y divide-gray-300 lg:grid-cols-[0.9fr_1.1fr] lg:divide-x lg:divide-y-0">
            <section
              aria-labelledby="leaderboard-heading"
              className="px-5 py-6 sm:px-7"
            >
              <p className="text-xs font-bold uppercase tracking-[0.08em] text-amber-700">
                {opponentName ? "Game-grain player leaders" : "Player leaders"}
              </p>
              <h3
                id="leaderboard-heading"
                className="mt-1 text-xl font-black text-gray-950"
              >
                {record.season} {selectedMetric?.display_label ?? "Statistic"}
                {opponentName ? ` vs ${opponentName}` : ""}
              </h3>
              {leaderboard.leaders.length > 0 ? (
                <ol className="mt-6 space-y-5">
                  {leaderboard.leaders.map((leader) => {
                    const gameEvidence =
                      "games" in leader ? leader.games : null;
                    const seasonSource =
                      "season_breakdown" in leader
                        ? leader.season_breakdown[0]?.source_url
                        : null;
                    return (
                      <li key={leader.player_id}>
                        <div className="flex items-baseline gap-3">
                          <span className="w-6 font-mono text-xs font-bold tabular-nums text-gray-400">
                            {leader.rank}
                          </span>
                          <span className="min-w-0 flex-1 truncate text-sm font-bold text-gray-950">
                            {leader.player_name}
                          </span>
                          <span className="font-mono text-sm font-black tabular-nums text-gray-950">
                            {formatValue(leader.total)}
                          </span>
                        </div>
                        <div className="mt-1.5 flex items-center gap-3 pl-9">
                          <progress
                            value={Number(leader.total)}
                            max={maximumLeaderValue}
                            aria-label={`${leader.player_name}: ${formatValue(leader.total)} ${leaderboard.stat_label}`}
                            className="h-2 min-w-0 flex-1 appearance-none overflow-hidden bg-gray-100 [&::-moz-progress-bar]:bg-yellow-500 [&::-webkit-progress-bar]:bg-gray-100 [&::-webkit-progress-value]:bg-yellow-500"
                          />
                          {gameEvidence ? (
                            <span className="flex shrink-0 items-center gap-2 text-xs text-gray-500">
                              {gameEvidence.length}{" "}
                              {gameEvidence.length === 1 ? "game" : "games"}
                              {gameEvidence.map((game, index) =>
                                game.source_url ? (
                                  <a
                                    key={game.game_id}
                                    href={game.source_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    aria-label={`View game ${index + 1} source for ${leader.player_name} against ${game.opponent}`}
                                    className="font-semibold text-gray-600 underline decoration-gray-300 underline-offset-4 hover:text-gray-950 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
                                  >
                                    Source {index + 1}
                                  </a>
                                ) : null,
                              )}
                              {gameEvidence.every((game) => !game.source_url) ? (
                                <span className="text-gray-400">
                                  Internal source
                                </span>
                              ) : null}
                            </span>
                          ) : seasonSource ? (
                            <a
                              href={seasonSource}
                              target="_blank"
                              rel="noreferrer"
                              aria-label={`View source for ${leader.player_name}`}
                              className="text-xs font-semibold text-gray-600 underline decoration-gray-300 underline-offset-4 hover:text-gray-950 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
                            >
                              Source
                            </a>
                          ) : (
                            <span className="text-xs text-gray-400">
                              Internal source
                            </span>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ol>
              ) : (
                <p className="mt-5 text-sm leading-6 text-gray-600">
                  No player totals match this season and statistic.
                  {opponentName ? ` No game facts match ${opponentName}.` : ""}
                </p>
              )}
              <div className="mt-7 border-t border-gray-200 pt-4 text-xs leading-5 text-gray-500">
                <p>{leaderboard.coverage.statement}</p>
                <p className="mt-1">
                  <QualitySummary
                    count={leaderboard.open_quality_issue_count}
                  />
                </p>
              </div>
            </section>

            <section aria-labelledby="game-ledger-heading" className="min-w-0">
              <div className="px-5 pb-4 pt-6 sm:px-7">
                <p className="text-xs font-bold uppercase tracking-[0.08em] text-amber-700">
                  Team evidence
                </p>
                <h3
                  id="game-ledger-heading"
                  className="mt-1 text-xl font-black text-gray-950"
                >
                  Game ledger
                </h3>
              </div>
              {record.games.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full border-collapse text-left text-sm">
                    <thead className="border-y border-gray-200 bg-gray-50 text-xs uppercase tracking-[0.05em] text-gray-500">
                      <tr>
                        <th
                          scope="col"
                          className="hidden px-5 py-3 font-bold sm:table-cell sm:pl-7"
                        >
                          Date
                        </th>
                        <th scope="col" className="px-3 py-3 font-bold">
                          Opponent
                        </th>
                        <th scope="col" className="px-3 py-3 font-bold">
                          Result
                        </th>
                        <th
                          scope="col"
                          className="px-3 py-3 text-right font-bold sm:px-5 sm:pr-7"
                        >
                          Evidence
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {record.games.map((game) => (
                        <tr key={game.game_id}>
                          <td className="hidden whitespace-nowrap px-5 py-3 font-mono text-xs tabular-nums text-gray-500 sm:table-cell sm:pl-7">
                            {game.game_date ?? "Date unavailable"}
                          </td>
                          <td className="px-3 py-3">
                            <span className="font-semibold text-gray-950">
                              {game.opponent}
                            </span>
                            {game.conference_event ? (
                              <span className="ml-2 text-[10px] font-bold uppercase tracking-[0.05em] text-amber-700">
                                Conf.
                              </span>
                            ) : null}
                            <span className="mt-1 block font-mono text-[11px] tabular-nums text-gray-500 sm:hidden">
                              {game.game_date ?? "Date unavailable"}
                            </span>
                          </td>
                          <td className="whitespace-nowrap px-3 py-3 font-mono font-bold tabular-nums text-gray-950">
                            <span className="mr-2 uppercase text-gray-500">
                              {game.result.slice(0, 1)}
                            </span>
                            {game.idaho_score}–{game.opponent_score}
                          </td>
                          <td className="px-3 py-3 text-right sm:px-5 sm:pr-7">
                            <a
                              href={game.source_url}
                              target="_blank"
                              rel="noreferrer"
                              aria-label={`View source for Idaho versus ${game.opponent}`}
                              className="font-semibold text-gray-600 underline decoration-gray-300 underline-offset-4 hover:text-gray-950 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
                            >
                              Source
                            </a>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="px-5 pb-7 text-sm leading-6 text-gray-600 sm:px-7">
                  No games match this game scope
                  {opponentName ? ` against ${opponentName}` : ""}.
                </p>
              )}
            </section>
          </div>
        </article>
      ) : null}
    </div>
  );
}

export default ExploratoryWorkspacePage;
