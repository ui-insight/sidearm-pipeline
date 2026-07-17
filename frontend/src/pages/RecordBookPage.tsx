import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { recordBookApi } from "../api/recordBook";
import type {
  Leaderboard,
  LeaderboardLeader,
  LeaderboardScope,
  LeaderboardStat,
} from "../types/recordBook";

const STATS: { value: LeaderboardStat; label: string }[] = [
  { value: "points", label: "Points" },
  { value: "total_rebounds", label: "Rebounds" },
  { value: "assists", label: "Assists" },
];

const SCOPES: { value: LeaderboardScope; label: string }[] = [
  { value: "career", label: "Career" },
  { value: "season", label: "Season" },
];

function formatValue(value: string): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(
    Number(value),
  );
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "The Record Book could not be loaded.";
}

function LeaderboardSkeleton({ statLabel }: { statLabel: string }) {
  const loadingLabel = `Loading ${statLabel.toLowerCase()} leaders`;
  return (
    <div className="animate-pulse" role="status" aria-label={loadingLabel}>
      <div className="border-b border-gray-200 px-4 py-4 sm:px-6">
        <div className="h-4 w-44 rounded bg-gray-200" />
      </div>
      {[0, 1, 2, 3, 4].map((row) => (
        <div
          key={row}
          className="grid grid-cols-[3rem_1fr_5rem] gap-4 border-b border-gray-100 px-4 py-4 sm:px-6"
        >
          <div className="h-4 w-6 rounded bg-gray-200" />
          <div className="h-4 w-36 rounded bg-gray-200" />
          <div className="ml-auto h-4 w-12 rounded bg-gray-200" />
        </div>
      ))}
      <span className="sr-only">{loadingLabel}</span>
    </div>
  );
}

function factSentence(
  leader: LeaderboardLeader,
  leaderboard: Leaderboard,
): string {
  const metric = leaderboard.stat_label.toLowerCase();
  if (leaderboard.scope === "season") {
    return `${leader.player_name} ranks No. ${leader.rank} in ${leaderboard.season} with ${formatValue(leader.total)} ${metric}.`;
  }

  const seasonWord = leader.seasons_count === 1 ? "season" : "seasons";
  const firstSeason = leaderboard.coverage.first_season;
  const lastSeason = leaderboard.coverage.last_season;
  const coverageWindow =
    firstSeason && lastSeason
      ? firstSeason === lastSeason
        ? firstSeason
        : `${firstSeason} through ${lastSeason}`
      : "available";
  return `${leader.player_name} ranks No. ${leader.rank} with ${formatValue(leader.total)} ${metric} across ${leader.seasons_count} ${seasonWord} in the verified ${coverageWindow} coverage window.`;
}

function PlayerFactSheet({
  leader,
  leaderboard,
}: {
  leader: LeaderboardLeader;
  leaderboard: Leaderboard;
}) {
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "error">(
    "idle",
  );
  const sentence = factSentence(leader, leaderboard);

  async function copyFact() {
    try {
      if (!navigator.clipboard) throw new Error("Clipboard unavailable");
      await Promise.race([
        navigator.clipboard.writeText(sentence),
        new Promise<never>((_, reject) =>
          window.setTimeout(
            () => reject(new Error("Clipboard request timed out")),
            1500,
          ),
        ),
      ]);
      setCopyStatus("copied");
    } catch {
      setCopyStatus("error");
    }
  }

  return (
    <aside
      aria-labelledby="player-fact-sheet-heading"
      className="border border-gray-200 bg-white lg:sticky lg:top-6 lg:self-start"
    >
      <div className="border-b border-gray-200 px-5 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-gray-500">
          Player fact sheet
        </p>
        <h2
          id="player-fact-sheet-heading"
          className="mt-1 text-lg font-semibold text-gray-950"
        >
          {leader.player_name}
        </h2>
      </div>

      <div className="border-b border-gray-200 px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase tracking-[0.06em] text-gray-500">
            Desk line
          </p>
          <button
            type="button"
            onClick={() => void copyFact()}
            className="rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-gray-700 hover:border-gray-500 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
          >
            {copyStatus === "copied"
              ? "Copied"
              : copyStatus === "error"
                ? "Copy failed"
                : "Copy fact"}
          </button>
        </div>
        <p className="mt-2 text-sm leading-6 text-gray-800">{sentence}</p>
        <p aria-live="polite" className="sr-only">
          {copyStatus === "copied"
            ? "Fact copied to clipboard."
            : copyStatus === "error"
              ? "The fact could not be copied."
              : ""}
        </p>
      </div>

      <dl className="grid grid-cols-3 border-b border-gray-200 bg-gray-50 px-5 py-3 text-center">
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-[0.06em] text-gray-500">
            Rank
          </dt>
          <dd className="mt-1 font-mono text-sm font-semibold tabular-nums text-gray-950">
            {leader.rank}
          </dd>
        </div>
        <div className="border-x border-gray-200">
          <dt className="text-[11px] font-semibold uppercase tracking-[0.06em] text-gray-500">
            {leaderboard.stat_label}
          </dt>
          <dd className="mt-1 font-mono text-sm font-semibold tabular-nums text-gray-950">
            {formatValue(leader.total)}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-[0.06em] text-gray-500">
            Seasons
          </dt>
          <dd className="mt-1 font-mono text-sm font-semibold tabular-nums text-gray-950">
            {leader.seasons_count}
          </dd>
        </div>
      </dl>

      <div className="px-5 pt-4">
        <h3 className="text-xs font-semibold uppercase tracking-[0.06em] text-gray-500">
          Source evidence
        </h3>
      </div>
      <ol className="divide-y divide-gray-200">
        {leader.season_breakdown.map((evidence) => (
          <li
            key={`${leader.player_id}-${evidence.season}`}
            className="px-5 py-4"
          >
            <div className="flex items-baseline justify-between gap-4">
              <span className="text-sm font-semibold text-gray-950">
                {evidence.season}
              </span>
              <span className="font-mono text-sm font-semibold tabular-nums text-gray-950">
                {formatValue(evidence.value)}
              </span>
            </div>
            <div className="mt-2 flex items-center justify-between gap-3 text-xs text-gray-500">
              <span>Season total</span>
              {evidence.source_url ? (
                <a
                  href={evidence.source_url}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={`View ${evidence.season} source`}
                  className="font-semibold text-gray-700 underline decoration-gray-300 underline-offset-4 hover:text-gray-950 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
                >
                  View source
                </a>
              ) : (
                <span>Source retained internally</span>
              )}
            </div>
          </li>
        ))}
      </ol>
    </aside>
  );
}

function RecordBookPage() {
  const [statKey, setStatKey] = useState<LeaderboardStat>("points");
  const [scope, setScope] = useState<LeaderboardScope>("career");
  const [season, setSeason] = useState("");
  const [availableSeasons, setAvailableSeasons] = useState<string[]>([]);
  const [data, setData] = useState<Leaderboard | null>(null);
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const selectedStatLabel =
    STATS.find((option) => option.value === statKey)?.label ?? "Points";

  useEffect(() => {
    let active = true;

    async function loadLeaders() {
      setLoading(true);
      setError(null);
      try {
        const leaderboard = await recordBookApi.leaders(
          statKey,
          scope,
          season || undefined,
        );
        if (!active) return;
        setData(leaderboard);
        setAvailableSeasons(leaderboard.available_seasons);
        if (
          scope === "season" &&
          leaderboard.season &&
          leaderboard.season !== season
        ) {
          setSeason(leaderboard.season);
        }
        setSelectedPlayerId((current) =>
          leaderboard.leaders.some((leader) => leader.player_id === current)
            ? current
            : (leaderboard.leaders[0]?.player_id ?? null),
        );
      } catch (loadError) {
        if (active) {
          setData(null);
          setError(errorMessage(loadError));
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadLeaders();
    return () => {
      active = false;
    };
  }, [reloadKey, scope, season, statKey]);

  function changeStat(nextStat: LeaderboardStat) {
    if (nextStat === statKey) return;
    if (scope === "season") setSeason("");
    setSelectedPlayerId(null);
    setStatKey(nextStat);
  }

  function changeScope(nextScope: LeaderboardScope) {
    if (nextScope === scope) return;
    const latestSeason = availableSeasons[0];
    if (nextScope === "season" && latestSeason) setSeason(latestSeason);
    setScope(nextScope);
  }

  const selectedLeader =
    data?.leaders.find((leader) => leader.player_id === selectedPlayerId) ?? null;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <header className="mb-7 max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-yellow-700">
          Record Book preview
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-gray-950">
          Women&apos;s basketball leaders
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
          Find verified season and coverage-window leaders, inspect their source
          evidence, and copy a publication-ready fact.
        </p>
      </header>

      <div className="mb-5 grid gap-4 border-y border-gray-200 bg-white px-4 py-4 sm:px-6 lg:grid-cols-[1fr_auto] lg:items-end">
        <div>
          <span className="block text-xs font-semibold uppercase tracking-[0.06em] text-gray-500">
            Statistic
          </span>
          <div
            role="group"
            aria-label="Leaderboard statistic"
            className="mt-2 flex flex-wrap gap-1"
          >
            {STATS.map((option) => (
              <button
                key={option.value}
                type="button"
                aria-pressed={statKey === option.value}
                onClick={() => changeStat(option.value)}
                className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 ${
                  statKey === option.value
                    ? "bg-yellow-400 text-gray-950"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-950"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <div>
            <span className="block text-xs font-semibold uppercase tracking-[0.06em] text-gray-500">
              Scope
            </span>
            <div
              role="tablist"
              aria-label="Leaderboard scope"
              className="mt-2 flex gap-1"
            >
              {SCOPES.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  role="tab"
                  aria-selected={scope === option.value}
                  onClick={() => changeScope(option.value)}
                  className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 ${
                    scope === option.value
                      ? "bg-gray-950 text-white"
                      : "text-gray-600 hover:bg-gray-100 hover:text-gray-950"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {scope === "season" ? (
            <label className="grid gap-1.5 text-xs font-semibold uppercase tracking-[0.06em] text-gray-600 sm:min-w-44">
              Season
              <select
                value={season}
                onChange={(event) => setSeason(event.target.value)}
                disabled={availableSeasons.length === 0}
                className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-gray-950 outline-none focus:border-gray-950 focus:ring-2 focus:ring-yellow-400 focus:ring-offset-2 disabled:bg-gray-100 disabled:text-gray-400"
              >
                {availableSeasons.length === 0 ? (
                  <option value="">No seasons</option>
                ) : null}
                {availableSeasons.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </div>
      </div>

      {error ? (
        <div
          role="alert"
          className="mb-5 border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-800"
        >
          <p className="font-semibold">The Record Book is unavailable</p>
          <p className="mt-1">{error}</p>
          <button
            type="button"
            onClick={() => setReloadKey((current) => current + 1)}
            className="mt-3 rounded-md border border-red-300 bg-white px-3 py-1.5 text-xs font-semibold text-red-800 hover:border-red-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
          >
            Try again
          </button>
        </div>
      ) : null}

      {!loading && data ? (
        <section
          aria-labelledby="coverage-heading"
          className="mb-5 border border-gray-200 bg-white px-5 py-4"
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="max-w-3xl">
              <div className="flex flex-wrap items-center gap-2">
                <h2
                  id="coverage-heading"
                  className="text-sm font-semibold text-gray-950"
                >
                  Coverage window
                </h2>
                <span
                  className={`rounded-full px-2 py-0.5 text-[11px] font-bold uppercase tracking-[0.06em] ${
                    data.coverage.completeness === "complete"
                      ? "bg-green-50 text-green-800"
                      : "bg-yellow-50 text-yellow-800"
                  }`}
                >
                  {data.coverage.completeness}
                </span>
              </div>
              <p className="mt-1 text-sm leading-6 text-gray-700">
                {data.coverage.statement}
              </p>
              {data.coverage.known_limitations.length > 0 ? (
                <details className="mt-2 text-xs text-gray-500">
                  <summary className="cursor-pointer font-semibold text-gray-600 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500">
                    Coverage notes
                  </summary>
                  <ul className="mt-2 list-disc space-y-1 pl-5">
                    {data.coverage.known_limitations.map((limitation) => (
                      <li key={limitation}>{limitation}</li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </div>
            <div className="flex gap-6 text-sm sm:text-right">
              <div>
                <span className="block text-xs uppercase tracking-[0.06em] text-gray-500">
                  Players
                </span>
                <span className="mt-1 block font-mono font-semibold tabular-nums text-gray-950">
                  {data.total_players}
                </span>
              </div>
              <div>
                <span className="block text-xs uppercase tracking-[0.06em] text-gray-500">
                  Scoped reviews
                </span>
                <span className="mt-1 block font-mono font-semibold tabular-nums text-gray-950">
                  {data.open_quality_issue_count}
                </span>
                <span className="mt-1 block text-[11px] text-gray-500">
                  Metric and window
                </span>
              </div>
            </div>
          </div>
        </section>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(18rem,0.75fr)]">
        <section
          aria-labelledby="leaderboard-heading"
          className="overflow-hidden border border-gray-200 bg-white"
        >
          <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 sm:px-6">
            <h2
              id="leaderboard-heading"
              className="text-sm font-semibold text-gray-950"
            >
              {scope === "career"
                ? `Career ${selectedStatLabel}`
                : `${season || "Season"} ${selectedStatLabel}`}
            </h2>
            {!loading && data ? (
              <span className="text-xs text-gray-500">
                Top {Math.min(10, data.total_players)}
              </span>
            ) : null}
          </div>

          {loading ? (
            <LeaderboardSkeleton statLabel={selectedStatLabel} />
          ) : data && data.leaders.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[34rem] border-collapse text-sm">
                <thead className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-[0.06em] text-gray-500">
                  <tr>
                    <th
                      scope="col"
                      className="w-16 px-4 py-3 text-center sm:px-6"
                    >
                      Rank
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Player
                    </th>
                    <th scope="col" className="px-4 py-3 text-right">
                      Seasons
                    </th>
                    <th scope="col" className="px-4 py-3 text-right sm:px-6">
                      {data.stat_label}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {data.leaders.map((leader) => {
                    const selected = leader.player_id === selectedPlayerId;
                    return (
                      <tr
                        key={leader.player_id}
                        className={selected ? "bg-yellow-50" : "hover:bg-gray-50"}
                      >
                        <td className="px-4 py-3 text-center font-mono text-xs font-semibold tabular-nums text-gray-500 sm:px-6">
                          {leader.rank}
                        </td>
                        <th scope="row" className="px-4 py-3 text-left font-medium">
                          <button
                            type="button"
                            aria-pressed={selected}
                            onClick={() => setSelectedPlayerId(leader.player_id)}
                            className="font-semibold text-gray-950 underline decoration-transparent underline-offset-4 hover:decoration-gray-400 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
                          >
                            {leader.player_name}
                          </button>
                        </th>
                        <td className="px-4 py-3 text-right font-mono tabular-nums text-gray-600">
                          {leader.seasons_count}
                        </td>
                        <td className="px-4 py-3 text-right font-mono font-semibold tabular-nums text-gray-950 sm:px-6">
                          {formatValue(leader.total)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="px-6 py-12 text-center">
              <p className="text-sm font-semibold text-gray-950">
                No {selectedStatLabel.toLowerCase()} leaders yet
              </p>
              <p className="mx-auto mt-1 max-w-lg text-sm text-gray-500">
                Import a cumulative women&apos;s basketball season to establish the
                first verified leaderboard.
              </p>
              <Link
                to="/backfills"
                className="mt-4 inline-flex rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold text-gray-700 hover:border-gray-400 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
              >
                Open backfills
              </Link>
            </div>
          )}
        </section>

        {!loading && selectedLeader && data ? (
          <PlayerFactSheet
            key={`${statKey}-${scope}-${season}-${selectedLeader.player_id}`}
            leader={selectedLeader}
            leaderboard={data}
          />
        ) : !loading && data?.leaders.length ? null : (
          <aside className="hidden border border-gray-200 bg-white px-5 py-6 text-sm text-gray-500 lg:block">
            Select a player to inspect and copy a sourced fact.
          </aside>
        )}
      </div>
    </div>
  );
}

export default RecordBookPage;
