import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { semanticQueriesApi } from "../api/semanticQueries";
import WorkspaceViewActions from "../components/WorkspaceViewActions";
import WorkspaceViewNav from "../components/WorkspaceViewNav";
import type {
  ConferenceScope,
  PlayerGameSplit,
  SemanticWorkspaceOptions,
  VenueScope,
} from "../types/semanticQuery";
import {
  alignComparisonGames,
  buildPlayerComparisonCsv,
} from "../utils/workspaceCsv";

const CONFERENCE_SCOPES: { value: ConferenceScope; label: string }[] = [
  { value: "all", label: "All games" },
  { value: "conference", label: "Conference" },
  { value: "non_conference", label: "Non-conference" },
];

const VENUE_SCOPES: { value: VenueScope; label: string }[] = [
  { value: "all", label: "All venues" },
  { value: "home", label: "Home" },
  { value: "away", label: "Away" },
  { value: "neutral", label: "Neutral" },
];

function isConferenceScope(value: string | null): value is ConferenceScope {
  return CONFERENCE_SCOPES.some((scope) => scope.value === value);
}

function isVenueScope(value: string | null): value is VenueScope {
  return VENUE_SCOPES.some((scope) => scope.value === value);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "The player comparison could not be loaded.";
}

function formatValue(value: string | null): string {
  if (value === null) return "No verified value";
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

function ComparisonSkeleton() {
  return (
    <div
      className="animate-pulse border-y border-gray-200 bg-white"
      role="status"
      aria-label="Loading player comparison"
    >
      <div className="border-b border-gray-200 px-5 py-7 sm:px-7">
        <div className="h-3 w-28 rounded bg-gray-200" />
        <div className="mt-4 h-8 max-w-xl rounded bg-gray-200" />
      </div>
      <div className="grid divide-y divide-gray-200 sm:grid-cols-2 sm:divide-x sm:divide-y-0">
        {[0, 1].map((section) => (
          <div key={section} className="space-y-4 px-5 py-6 sm:px-7">
            <div className="h-5 w-36 rounded bg-gray-200" />
            <div className="h-9 w-24 rounded bg-gray-200" />
            <div className="h-2 rounded bg-gray-100" />
            <div className="h-4 max-w-xs rounded bg-gray-100" />
          </div>
        ))}
      </div>
      <span className="sr-only">Loading player comparison</span>
    </div>
  );
}

function PlayerResult({
  label,
  result,
  maximum,
}: {
  label: "Player A" | "Player B";
  result: PlayerGameSplit;
  maximum: number;
}) {
  const numericValue = Math.abs(Number(result.value ?? 0));
  return (
    <section className="px-5 py-6 sm:px-7">
      <p className="text-xs font-bold uppercase tracking-[0.08em] text-amber-700">
        {label}
      </p>
      <h3 className="mt-1 text-xl font-black text-gray-950">
        {result.player_name}
      </h3>
      <div className="mt-5 flex items-end justify-between gap-4">
        <div>
          <p className="font-mono text-3xl font-black tabular-nums text-gray-950">
            {formatValue(result.value)}
          </p>
          <p className="mt-1 text-xs font-bold uppercase tracking-[0.06em] text-gray-500">
            {result.stat_label}
          </p>
        </div>
        <p className="pb-1 text-right text-sm text-gray-600">
          <span className="font-mono font-bold tabular-nums text-gray-950">
            {result.games_count}
          </span>{" "}
          {result.games_count === 1 ? "game" : "games"} reviewed
        </p>
      </div>
      <progress
        value={numericValue}
        max={maximum}
        aria-label={`${result.player_name}: ${formatValue(result.value)} ${result.stat_label}`}
        className="mt-4 h-2 w-full appearance-none overflow-hidden bg-gray-100 [&::-moz-progress-bar]:bg-yellow-500 [&::-webkit-progress-bar]:bg-gray-100 [&::-webkit-progress-value]:bg-yellow-500"
      />
      <div className="mt-5 border-t border-gray-200 pt-4 text-xs leading-5 text-gray-500">
        <p>{result.coverage.statement}</p>
        <p className="mt-1">
          <QualitySummary count={result.open_quality_issue_count} />
        </p>
      </div>
    </section>
  );
}

function PlayerComparisonPage() {
  const [options, setOptions] = useState<SemanticWorkspaceOptions | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const [leftResult, setLeftResult] = useState<PlayerGameSplit | null>(null);
  const [rightResult, setRightResult] = useState<PlayerGameSplit | null>(null);
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
  const requestedConference = searchParams.get("conference");
  const conferenceScope = isConferenceScope(requestedConference)
    ? requestedConference
    : "all";
  const requestedVenue = searchParams.get("venue");
  const venueScope = isVenueScope(requestedVenue) ? requestedVenue : "all";

  const availablePlayers = useMemo(
    () =>
      (options?.players ?? []).filter((player) =>
        player.seasons.includes(season),
      ),
    [options, season],
  );
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
  const requestedLeftPlayerId = Number(searchParams.get("left"));
  const leftPlayerId =
    availablePlayers.find(
      (player) => player.player_id === requestedLeftPlayerId,
    )?.player_id ??
    availablePlayers[0]?.player_id ??
    0;
  const requestedRightPlayerId = Number(searchParams.get("right"));
  const rightPlayerId =
    availablePlayers.find(
      (player) =>
        player.player_id === requestedRightPlayerId &&
        player.player_id !== leftPlayerId,
    )?.player_id ??
    availablePlayers.find((player) => player.player_id !== leftPlayerId)
      ?.player_id ??
    0;
  const currentViewParams = {
    season,
    stat: statKey,
    conference: conferenceScope,
    venue: venueScope,
    opponent,
    left: String(leftPlayerId),
    right: String(rightPlayerId),
  };

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
        setLeftResult(null);
        setRightResult(null);
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
    if (
      !season ||
      !statKey ||
      leftPlayerId === 0 ||
      rightPlayerId === 0 ||
      leftPlayerId === rightPlayerId
    ) {
      return;
    }
    let active = true;

    async function loadComparison() {
      setLoadingResults(true);
      setError(null);
      try {
        const [leftResponse, rightResponse] = await Promise.all([
          semanticQueriesApi.playerGameSplit(
            leftPlayerId,
            season,
            statKey,
            conferenceScope,
            venueScope,
            opponentName,
          ),
          semanticQueriesApi.playerGameSplit(
            rightPlayerId,
            season,
            statKey,
            conferenceScope,
            venueScope,
            opponentName,
          ),
        ]);
        if (!active) return;
        setLeftResult(leftResponse.result);
        setRightResult(rightResponse.result);
      } catch (loadError) {
        if (!active) return;
        setLeftResult(null);
        setRightResult(null);
        setError(errorMessage(loadError));
      } finally {
        if (active) setLoadingResults(false);
      }
    }

    void loadComparison();
    return () => {
      active = false;
    };
  }, [
    conferenceScope,
    leftPlayerId,
    opponentName,
    reloadKey,
    rightPlayerId,
    season,
    statKey,
    venueScope,
  ]);

  useEffect(() => {
    if (!options || !season || !statKey || !leftPlayerId || !rightPlayerId) {
      return;
    }
    const canonicalParams = {
      season,
      stat: statKey,
      conference: conferenceScope,
      venue: venueScope,
      opponent,
      left: String(leftPlayerId),
      right: String(rightPlayerId),
    };
    const canonicalSearch = new URLSearchParams(canonicalParams).toString();
    if (canonicalSearch !== searchParams.toString()) {
      setSearchParams(canonicalParams, { replace: true });
    }
  }, [
    conferenceScope,
    leftPlayerId,
    opponent,
    options,
    rightPlayerId,
    searchParams,
    season,
    setSearchParams,
    statKey,
    venueScope,
  ]);

  function updateViewParams(changes: Record<string, string>) {
    setSearchParams({ ...currentViewParams, ...changes });
  }

  function changeSeason(nextSeason: string) {
    const nextPlayers = (options?.players ?? []).filter((player) =>
      player.seasons.includes(nextSeason),
    );
    const nextLeft =
      nextPlayers.find((player) => player.player_id === leftPlayerId) ??
      nextPlayers[0];
    const nextRight =
      nextPlayers.find(
        (player) =>
          player.player_id === rightPlayerId &&
          player.player_id !== nextLeft?.player_id,
      ) ?? nextPlayers.find((player) => player.player_id !== nextLeft?.player_id);
    const nextOpponents = (options?.opponents ?? []).filter((candidate) =>
      candidate.seasons.includes(nextSeason),
    );
    const nextOpponent =
      opponent === "all" ||
      nextOpponents.some((candidate) => candidate.opponent_name === opponent)
        ? opponent
        : "all";
    updateViewParams({
      season: nextSeason,
      opponent: nextOpponent,
      left: String(nextLeft?.player_id ?? 0),
      right: String(nextRight?.player_id ?? 0),
    });
  }

  function changeLeftPlayer(nextPlayerId: number) {
    const nextRightPlayerId =
      nextPlayerId === rightPlayerId
        ? (availablePlayers.find(
            (player) => player.player_id !== nextPlayerId,
          )?.player_id ?? 0)
        : rightPlayerId;
    updateViewParams({
      left: String(nextPlayerId),
      right: String(nextRightPlayerId),
    });
  }

  function changeRightPlayer(nextPlayerId: number) {
    const nextLeftPlayerId =
      nextPlayerId === leftPlayerId
        ? (availablePlayers.find(
            (player) => player.player_id !== nextPlayerId,
          )?.player_id ?? 0)
        : leftPlayerId;
    updateViewParams({
      left: String(nextLeftPlayerId),
      right: String(nextPlayerId),
    });
  }

  function exportCsv() {
    if (!leftResult || !rightResult) return;
    const blob = new Blob(
      [buildPlayerComparisonCsv(leftResult, rightResult)],
      { type: "text/csv;charset=utf-8" },
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `wbb-${season}-${statKey}-${fileSlug(leftResult.player_name)}-v-${fileSlug(rightResult.player_name)}.csv`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  const selectedMetric = options?.metrics.find(
    (metric) => metric.stat_key === statKey,
  );
  const selectedOpponent = availableOpponents.find(
    (candidate) => candidate.opponent_name === opponentName,
  );
  const canCompare =
    leftPlayerId > 0 &&
    rightPlayerId > 0 &&
    leftPlayerId !== rightPlayerId;
  const globallyEmpty =
    !loadingOptions &&
    !error &&
    options !== null &&
    (options.seasons.length === 0 ||
      options.metrics.length === 0 ||
      options.players.length < 2);
  const hasResults =
    canCompare && leftResult !== null && rightResult !== null;
  const comparisonRows = hasResults
    ? alignComparisonGames(leftResult, rightResult)
    : [];
  const maximumValue = hasResults
    ? Math.max(
        Math.abs(Number(leftResult.value ?? 0)),
        Math.abs(Number(rightResult.value ?? 0)),
        1,
      )
    : 1;
  const conferenceLabel =
    CONFERENCE_SCOPES.find((scope) => scope.value === conferenceScope)?.label ??
    "Selected games";
  const venueLabel =
    VENUE_SCOPES.find((scope) => scope.value === venueScope)?.label ??
    "Selected venues";

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <header className="max-w-3xl">
        <p className="text-xs font-black uppercase tracking-[0.14em] text-amber-700">
          Exploratory workspace
        </p>
        <h1 className="mt-2 text-3xl font-black tracking-tight text-gray-950 sm:text-4xl">
          Player comparison
        </h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-gray-600">
          Put two players under the same season, competition, venue, statistic,
          and opponent filters, with the game evidence kept in view.
        </p>
      </header>
      <WorkspaceViewNav />

      {options && !globallyEmpty ? (
        <WorkspaceViewActions view="comparison" params={currentViewParams} />
      ) : null}

      {options && !globallyEmpty ? (
        <section
          aria-label="Comparison filters"
          className="mt-8 border-y border-gray-300 bg-white px-4 py-4 sm:px-5"
        >
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-[1fr_1fr_0.7fr_0.85fr_0.85fr_0.9fr_1fr_auto] xl:items-end">
            <label className="text-xs font-bold uppercase tracking-[0.06em] text-gray-600">
              Player A
              <select
                value={leftPlayerId}
                onChange={(event) => changeLeftPlayer(Number(event.target.value))}
                className="mt-1.5 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-gray-950 focus:border-yellow-500 focus:outline-2 focus:outline-offset-1 focus:outline-yellow-500"
              >
                {leftPlayerId === 0 ? (
                  <option value={0}>No player available</option>
                ) : null}
                {availablePlayers.map((player) => (
                  <option
                    key={player.player_id}
                    value={player.player_id}
                    disabled={player.player_id === rightPlayerId}
                  >
                    {player.player_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-bold uppercase tracking-[0.06em] text-gray-600">
              Player B
              <select
                value={rightPlayerId}
                onChange={(event) =>
                  changeRightPlayer(Number(event.target.value))
                }
                className="mt-1.5 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-gray-950 focus:border-yellow-500 focus:outline-2 focus:outline-offset-1 focus:outline-yellow-500"
              >
                {rightPlayerId === 0 ? (
                  <option value={0}>No second player</option>
                ) : null}
                {availablePlayers.map((player) => (
                  <option
                    key={player.player_id}
                    value={player.player_id}
                    disabled={player.player_id === leftPlayerId}
                  >
                    {player.player_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-bold uppercase tracking-[0.06em] text-gray-600">
              Season
              <select
                value={season}
                onChange={(event) => changeSeason(event.target.value)}
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
              Competition
              <select
                value={conferenceScope}
                onChange={(event) =>
                  updateViewParams({ conference: event.target.value })
                }
                className="mt-1.5 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-gray-950 focus:border-yellow-500 focus:outline-2 focus:outline-offset-1 focus:outline-yellow-500"
              >
                {CONFERENCE_SCOPES.map((scope) => (
                  <option key={scope.value} value={scope.value}>
                    {scope.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-bold uppercase tracking-[0.06em] text-gray-600">
              Venue
              <select
                value={venueScope}
                onChange={(event) =>
                  updateViewParams({ venue: event.target.value })
                }
                className="mt-1.5 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-gray-950 focus:border-yellow-500 focus:outline-2 focus:outline-offset-1 focus:outline-yellow-500"
              >
                {VENUE_SCOPES.map((scope) => (
                  <option key={scope.value} value={scope.value}>
                    {scope.label}
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
                {availableOpponents.map((candidate) => (
                  <option
                    key={candidate.opponent_name}
                    value={candidate.opponent_name}
                  >
                    {candidate.opponent_name}
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
          <ComparisonSkeleton />
        </div>
      ) : null}

      {error && !loadingOptions && !loadingResults ? (
        <section
          role="alert"
          className="mt-8 border border-red-200 bg-red-50 px-5 py-5"
        >
          <h2 className="text-base font-bold text-red-950">
            Player comparison unavailable
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

      {globallyEmpty ? (
        <section className="mt-8 border-y border-gray-300 bg-white px-5 py-10 text-center">
          <h2 className="text-xl font-bold text-gray-950">
            Two-player evidence is not ready yet
          </h2>
          <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-gray-600">
            At least two canonical players need vetted game facts before a
            comparison can be assembled.
          </p>
        </section>
      ) : null}

      {!globallyEmpty && !loadingOptions && !error && !canCompare ? (
        <section className="mt-8 border-y border-gray-300 bg-white px-5 py-8 text-center">
          <h2 className="text-lg font-bold text-gray-950">
            This season needs another player
          </h2>
          <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-gray-600">
            Fewer than two players have vetted game evidence in {season}.
            Choose another season to continue.
          </p>
        </section>
      ) : null}

      {!loadingOptions && !loadingResults && !error && hasResults ? (
        <article className="mt-8 border-y border-gray-300 bg-white">
          <header className="border-b border-gray-300 px-5 py-6 sm:px-7 sm:py-7">
            <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">
              {season} · {conferenceLabel} · {venueLabel}
              {selectedOpponent
                ? ` · ${selectedOpponent.opponent_name}`
                : " · All opponents"}
            </p>
            <h2 className="mt-2 text-2xl font-black tracking-tight text-gray-950 sm:text-3xl">
              {leftResult.player_name} vs. {rightResult.player_name}
            </h2>
            <p className="mt-2 text-sm leading-6 text-gray-600">
              {selectedMetric?.display_label ?? leftResult.stat_label}
              {selectedOpponent
                ? ` against ${selectedOpponent.opponent_name}`
                : ""} from the same governed game filters.
            </p>
          </header>

          <div className="grid divide-y divide-gray-300 sm:grid-cols-2 sm:divide-x sm:divide-y-0">
            <PlayerResult
              label="Player A"
              result={leftResult}
              maximum={maximumValue}
            />
            <PlayerResult
              label="Player B"
              result={rightResult}
              maximum={maximumValue}
            />
          </div>

          <section
            aria-labelledby="comparison-evidence-heading"
            className="border-t border-gray-300"
          >
            <div className="px-5 pb-4 pt-6 sm:px-7">
              <p className="text-xs font-bold uppercase tracking-[0.08em] text-amber-700">
                Shared evidence
              </p>
              <h3
                id="comparison-evidence-heading"
                className="mt-1 text-xl font-black text-gray-950"
              >
                Game-by-game comparison
              </h3>
            </div>
            {comparisonRows.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse text-left text-sm">
                  <thead className="border-y border-gray-200 bg-gray-50 text-xs uppercase tracking-[0.05em] text-gray-500">
                    <tr>
                      <th scope="col" className="px-5 py-3 font-bold sm:pl-7">
                        Game
                      </th>
                      <th scope="col" className="px-3 py-3 text-right font-bold">
                        <span className="sm:hidden">Player A</span>
                        <span className="hidden sm:inline">
                          {leftResult.player_name}
                        </span>
                      </th>
                      <th scope="col" className="px-3 py-3 text-right font-bold">
                        <span className="sm:hidden">Player B</span>
                        <span className="hidden sm:inline">
                          {rightResult.player_name}
                        </span>
                      </th>
                      <th
                        scope="col"
                        className="px-5 py-3 text-right font-bold sm:pr-7"
                      >
                        Evidence
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {comparisonRows.map((game) => (
                      <tr key={game.game_id}>
                        <td className="px-5 py-3 sm:pl-7">
                          <span className="font-semibold text-gray-950">
                            {game.opponent}
                          </span>
                          <span className="mt-1 block font-mono text-[11px] tabular-nums text-gray-500">
                            <span className="whitespace-nowrap">
                              {game.game_date ?? "Date unavailable"}
                            </span>
                            <span className="block sm:inline">
                              {" "}· {game.venue ?? "Venue unavailable"}
                              {game.conference_event ? " · Conf." : ""}
                            </span>
                          </span>
                        </td>
                        <td className="px-3 py-3 text-right font-mono font-bold tabular-nums text-gray-950">
                          {game.left_value === null
                            ? "N/A"
                            : formatValue(game.left_value)}
                        </td>
                        <td className="px-3 py-3 text-right font-mono font-bold tabular-nums text-gray-950">
                          {game.right_value === null
                            ? "N/A"
                            : formatValue(game.right_value)}
                        </td>
                        <td className="px-5 py-3 text-right sm:pr-7">
                          <span className="inline-flex gap-2">
                            {game.left_source_url ? (
                              <a
                                href={game.left_source_url}
                                target="_blank"
                                rel="noreferrer"
                                aria-label={`View ${leftResult.player_name} source against ${game.opponent}`}
                                className="font-semibold text-gray-600 underline decoration-gray-300 underline-offset-4 hover:text-gray-950 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
                              >
                                A
                              </a>
                            ) : (
                              <span className="text-gray-400">A</span>
                            )}
                            {game.right_source_url ? (
                              <a
                                href={game.right_source_url}
                                target="_blank"
                                rel="noreferrer"
                                aria-label={`View ${rightResult.player_name} source against ${game.opponent}`}
                                className="font-semibold text-gray-600 underline decoration-gray-300 underline-offset-4 hover:text-gray-950 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
                              >
                                B
                              </a>
                            ) : (
                              <span className="text-gray-400">B</span>
                            )}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="px-5 pb-7 text-sm leading-6 text-gray-600 sm:px-7">
                Neither player has game evidence for these filters.
              </p>
            )}
          </section>
        </article>
      ) : null}
    </div>
  );
}

export default PlayerComparisonPage;
