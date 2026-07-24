import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { ApiError } from "../api/client";
import { semanticQueriesApi } from "../api/semanticQueries";
import type { Leaderboard } from "../types/recordBook";
import type {
  SemanticWorkspaceOptions,
  TeamSeasonRecord,
} from "../types/semanticQuery";

const TARGET_SEASON = "2025-26";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Demo readiness could not be checked.";
}

function AthleticsDemoPage() {
  const [options, setOptions] = useState<SemanticWorkspaceOptions | null>(null);
  const [record, setRecord] = useState<TeamSeasonRecord | null>(null);
  const [leaders, setLeaders] = useState<Leaderboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadReadiness() {
      setLoading(true);
      setError(null);
      try {
        const nextOptions = await semanticQueriesApi.options();
        if (!active) return;
        setOptions(nextOptions);

        const season = nextOptions.seasons.includes(TARGET_SEASON)
          ? TARGET_SEASON
          : nextOptions.default_season ?? nextOptions.seasons[0];
        const statKey =
          nextOptions.default_stat_key ?? nextOptions.metrics[0]?.stat_key;
        if (!season || !statKey) return;

        const [recordResponse, leaderResponse] = await Promise.all([
          semanticQueriesApi.teamSeasonRecord(season, "all", null),
          semanticQueriesApi.statLeaders(season, statKey, 10),
        ]);
        if (!active) return;
        setRecord(recordResponse.result);
        setLeaders(leaderResponse.result);
      } catch (loadError) {
        if (!active) return;
        setError(errorMessage(loadError));
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadReadiness();
    return () => {
      active = false;
    };
  }, []);

  const season = options?.seasons.includes(TARGET_SEASON)
    ? TARGET_SEASON
    : options?.default_season ?? options?.seasons[0] ?? "";
  const metric =
    options?.metrics.find(
      (candidate) => candidate.stat_key === options.default_stat_key,
    ) ?? options?.metrics[0];
  const players = useMemo(
    () =>
      (options?.players ?? []).filter((player) =>
        player.seasons.includes(season),
      ),
    [options, season],
  );
  const opponents = useMemo(
    () =>
      (options?.opponents ?? []).filter((opponent) =>
        opponent.seasons.includes(season),
      ),
    [options, season],
  );

  const seasonReady = Boolean(season && metric && record && leaders);
  const evidenceReady = Boolean(
    record && record.games_played > 0 && record.games.every((game) => game.source_url),
  );
  const qualityReady = Boolean(
    record &&
      leaders &&
      record.open_quality_issue_count === 0 &&
      leaders.open_quality_issue_count === 0,
  );
  const comparisonReady = players.length >= 2;
  const demoReady =
    seasonReady && evidenceReady && qualityReady && comparisonReady;

  const seasonDeskUrl = metric
    ? `/workspace?${new URLSearchParams({
        season,
        stat: metric.stat_key,
        scope: "all",
        opponent: "all",
        limit: "10",
      })}`
    : "/workspace";
  const opponentDeskUrl = metric && opponents[0]
    ? `/workspace?${new URLSearchParams({
        season,
        stat: metric.stat_key,
        scope: "all",
        opponent: opponents[0].opponent_name,
        limit: "10",
      })}`
    : "/workspace";
  const comparisonUrl = metric && players[0] && players[1]
    ? `/workspace/compare?${new URLSearchParams({
        season,
        stat: metric.stat_key,
        conference: "all",
        venue: "all",
        opponent: "all",
        left: String(players[0].player_id),
        right: String(players[1].player_id),
      })}`
    : "/workspace/compare";

  const gates = [
    {
      label: "Season facts",
      ready: seasonReady,
      detail: seasonReady
        ? `${record?.games_played ?? 0} final games and ${leaders?.total_players ?? 0} ranked players`
        : "Sync the completed WBB season and cumulative statistics.",
    },
    {
      label: "Source evidence",
      ready: evidenceReady,
      detail: evidenceReady
        ? "Every game in the record has a source link."
        : "Final-game evidence is missing or incomplete.",
    },
    {
      label: "Quality review",
      ready: qualityReady,
      detail: qualityReady
        ? "No open issues affect the season record or leaderboard."
        : `${(record?.open_quality_issue_count ?? 0) + (leaders?.open_quality_issue_count ?? 0)} open issue references remain.`,
    },
    {
      label: "Player comparison",
      ready: comparisonReady,
      detail: comparisonReady
        ? `${players.length} players have game-level evidence.`
        : "At least two resolved players need game-level evidence.",
    },
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <header className="grid gap-6 border-b border-gray-300 pb-8 lg:grid-cols-[1fr_auto] lg:items-end">
        <div className="max-w-3xl">
          <p className="text-xs font-black uppercase tracking-[0.14em] text-amber-700">
            Athletics briefing
          </p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-gray-950 sm:text-4xl">
            WBB demo desk
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-gray-600">
            Verify the evidence, then walk through three questions an athletics
            staff member can answer without SQL.
          </p>
        </div>
        {!loading && !error ? (
          <div
            className={`inline-flex w-fit items-center gap-2 rounded-full px-3 py-1.5 text-sm font-bold ${
              demoReady
                ? "bg-emerald-50 text-emerald-800"
                : "bg-amber-50 text-amber-900"
            }`}
            role="status"
          >
            <span aria-hidden="true">{demoReady ? "✓" : "!"}</span>
            {demoReady ? "Ready to present" : "Preparation required"}
          </div>
        ) : null}
      </header>

      {loading ? (
        <div className="animate-pulse py-10" role="status">
          <div className="h-5 w-48 rounded bg-gray-200" />
          <div className="mt-6 space-y-3">
            <div className="h-14 rounded bg-gray-100" />
            <div className="h-14 rounded bg-gray-100" />
            <div className="h-14 rounded bg-gray-100" />
          </div>
          <span className="sr-only">Checking demo readiness</span>
        </div>
      ) : error ? (
        <section className="mt-8 border border-red-200 bg-red-50 px-5 py-4" role="alert">
          <h2 className="font-bold text-red-900">Readiness check failed</h2>
          <p className="mt-1 text-sm text-red-800">{error}</p>
          <Link
            to="/"
            className="mt-3 inline-block text-sm font-bold text-red-900 underline underline-offset-2"
          >
            Return to season sync
          </Link>
        </section>
      ) : (
        <>
          <section className="grid border-b border-gray-300 py-8 lg:grid-cols-[15rem_1fr] lg:gap-10">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">
                Readiness gates
              </p>
              <h2 className="mt-2 text-xl font-black text-gray-950">
                {season || TARGET_SEASON}
              </h2>
              <p className="mt-2 text-sm leading-6 text-gray-600">
                These checks use current warehouse results, not a static demo checklist.
              </p>
            </div>
            <ol className="mt-6 divide-y divide-gray-200 border-y border-gray-200 lg:mt-0">
              {gates.map((gate) => (
                <li
                  key={gate.label}
                  className="grid gap-1 py-4 sm:grid-cols-[11rem_1fr_auto] sm:items-center sm:gap-4"
                >
                  <span className="font-bold text-gray-950">{gate.label}</span>
                  <span className="text-sm text-gray-600">{gate.detail}</span>
                  <span
                    className={`text-xs font-black uppercase tracking-[0.08em] ${
                      gate.ready ? "text-emerald-700" : "text-amber-800"
                    }`}
                  >
                    {gate.ready ? "Ready" : "Needs work"}
                  </span>
                </li>
              ))}
            </ol>
          </section>

          <section className="py-8">
            <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">
              Ten-minute walkthrough
            </p>
            <h2 className="mt-2 text-2xl font-black text-gray-950">
              Three questions, every answer sourced
            </h2>
            <ol className="mt-6 divide-y divide-gray-200 border-y border-gray-300 bg-white">
              <li className="grid gap-4 px-4 py-5 sm:grid-cols-[2rem_1fr_auto] sm:items-center sm:px-5">
                <span className="font-mono text-lg font-black text-amber-700">01</span>
                <div>
                  <h3 className="font-bold text-gray-950">Who led the season?</h3>
                  <p className="mt-1 text-sm text-gray-600">
                    Open the team record and {metric?.display_label.toLowerCase() ?? "stat"} leaders with coverage beside the result.
                  </p>
                </div>
                <Link className="text-sm font-bold text-gray-950 underline decoration-amber-500 underline-offset-4" to={seasonDeskUrl}>
                  Open season desk
                </Link>
              </li>
              <li className="grid gap-4 px-4 py-5 sm:grid-cols-[2rem_1fr_auto] sm:items-center sm:px-5">
                <span className="font-mono text-lg font-black text-amber-700">02</span>
                <div>
                  <h3 className="font-bold text-gray-950">What happened against one opponent?</h3>
                  <p className="mt-1 text-sm text-gray-600">
                    {opponents[0]
                      ? `Review ${opponents[0].opponent_name} results and the contributing boxscores.`
                      : "Sync game-level evidence to unlock an opponent walkthrough."}
                  </p>
                </div>
                <Link className="text-sm font-bold text-gray-950 underline decoration-amber-500 underline-offset-4" to={opponentDeskUrl}>
                  Open opponent view
                </Link>
              </li>
              <li className="grid gap-4 px-4 py-5 sm:grid-cols-[2rem_1fr_auto] sm:items-center sm:px-5">
                <span className="font-mono text-lg font-black text-amber-700">03</span>
                <div>
                  <h3 className="font-bold text-gray-950">How do two players compare?</h3>
                  <p className="mt-1 text-sm text-gray-600">
                    {players[0] && players[1]
                      ? `Compare ${players[0].player_name} and ${players[1].player_name} over the same verified games.`
                      : "Resolve two player identities to unlock the comparison."}
                  </p>
                </div>
                <Link className="text-sm font-bold text-gray-950 underline decoration-amber-500 underline-offset-4" to={comparisonUrl}>
                  Open comparison
                </Link>
              </li>
            </ol>
          </section>

          {!demoReady ? (
            <section className="border border-amber-200 bg-amber-50 px-5 py-5 sm:flex sm:items-center sm:justify-between sm:gap-6">
              <div>
                <h2 className="font-bold text-gray-950">Finish the data preparation</h2>
                <p className="mt-1 text-sm leading-6 text-gray-700">
                  Sync the season first, then clear identity and quality issues before presenting.
                </p>
              </div>
              <Link
                to="/"
                className="mt-4 inline-flex rounded-md bg-gray-950 px-4 py-2 text-sm font-bold text-white transition-colors hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 sm:mt-0"
              >
                Go to season sync
              </Link>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}

export default AthleticsDemoPage;
