import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { achievementsApi } from "../api/achievements";
import { ApiError } from "../api/client";
import type {
  AchievementReviewGame,
  AchievementReviewQueue,
  AchievementReviewState,
  AchievementSuggestion,
} from "../types/achievement";

const PAGE_SIZE = 25;

const STATE_OPTIONS: {
  value: AchievementReviewState;
  label: string;
  emptyHeading: string;
  emptyCopy: string;
}[] = [
  {
    value: "pending",
    label: "Needs review",
    emptyHeading: "The desk is clear",
    emptyCopy:
      "Ranked suggestions will appear here after verified game facts pass through the notability review model.",
  },
  {
    value: "approved",
    label: "Approved",
    emptyHeading: "No approved suggestions yet",
    emptyCopy: "Suggestions approved for SID use will remain available here.",
  },
  {
    value: "rejected",
    label: "Rejected",
    emptyHeading: "No rejected suggestions yet",
    emptyCopy:
      "Rejected patterns will appear here and reduce the weight of similar future suggestions.",
  },
];

function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.data === "object" && error.data && "detail" in error.data) {
      return String(error.data.detail);
    }
    return error.message;
  }
  return error instanceof Error
    ? error.message
    : "The achievement review queue could not be loaded.";
}

function formatDate(value: string | null): string {
  if (!value) return "Date unavailable";
  const parsed = new Date(`${value}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(parsed);
}

function formatReviewedAt(value: string | null): string {
  if (!value) return "Review time unavailable";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function gameTitle(game: AchievementReviewGame): string {
  return game.title ?? `${game.away_team ?? "Away"} at ${game.home_team ?? "Home"}`;
}

function scoreline(game: AchievementReviewGame): string | null {
  if (game.away_score === null || game.home_score === null) return null;
  return `${game.away_team ?? "Away"} ${game.away_score}, ${game.home_team ?? "Home"} ${game.home_score}`;
}

function achievementLabel(value: string): string {
  const labels: Record<string, string> = {
    career_high: "Career high",
    season_high: "Season high",
    threshold_crossing: "Career milestone",
    all_time_top_n: "Program ranking",
  };
  return labels[value] ?? value.replace(/_/g, " ");
}

function contextText(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function QueueSkeleton() {
  return (
    <div aria-label="Loading achievement reviews" className="animate-pulse">
      <div className="h-14 border-b border-gray-200 bg-gray-100" />
      <div className="h-14 border-b border-gray-200 bg-gray-50" />
      <div className="h-14 border-b border-gray-200 bg-gray-100" />
    </div>
  );
}

function AchievementReviewPage() {
  const [state, setState] = useState<AchievementReviewState>("pending");
  const [queue, setQueue] = useState<AchievementReviewQueue | null>(null);
  const [selectedGameId, setSelectedGameId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const [decisionId, setDecisionId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function loadQueue() {
      setLoading(true);
      setError(null);
      try {
        const result = await achievementsApi.reviewQueue(state, PAGE_SIZE, 0);
        if (!active) return;
        setQueue(result);
        setSelectedGameId((current) =>
          result.items.some((game) => game.game_id === current)
            ? current
            : (result.items[0]?.game_id ?? null),
        );
      } catch (loadError) {
        if (active) setError(apiErrorMessage(loadError));
      } finally {
        if (active) setLoading(false);
      }
    }
    void loadQueue();
    return () => {
      active = false;
    };
  }, [reloadKey, state]);

  const selectedGame = useMemo(
    () => queue?.items.find((game) => game.game_id === selectedGameId) ?? null,
    [queue, selectedGameId],
  );

  function countFor(nextState: AchievementReviewState): number {
    if (!queue) return 0;
    if (nextState === "approved") return queue.approved_count;
    if (nextState === "rejected") return queue.rejected_count;
    return queue.pending_count;
  }

  function changeState(nextState: AchievementReviewState) {
    setState(nextState);
    setSelectedGameId(null);
    setNotice(null);
  }

  async function recordVerdict(
    suggestion: AchievementSuggestion,
    verdict: "approved" | "rejected",
  ) {
    setDecisionId(suggestion.id);
    setError(null);
    setNotice(null);
    try {
      await achievementsApi.verdict(suggestion.id, verdict);
      setNotice(
        `${suggestion.player_name}'s ${achievementLabel(suggestion.achievement_type).toLowerCase()} was ${verdict}.`,
      );
      setReloadKey((current) => current + 1);
    } catch (decisionError) {
      setError(apiErrorMessage(decisionError));
    } finally {
      setDecisionId(null);
    }
  }

  const stateConfig = STATE_OPTIONS.find((option) => option.value === state)!;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <header className="mb-7 flex flex-col gap-5 border-b border-gray-300 pb-7 md:flex-row md:items-end md:justify-between">
        <div className="max-w-3xl">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-yellow-700">
            Editorial review
          </p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-gray-950">
            Achievement desk
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-gray-600">
            Decide which verified milestones are worth publishing. Every phrase is
            attached to its warehouse fact, source, and coverage boundary.
          </p>
        </div>
        <Link
          to="/record-book"
          className="inline-flex w-fit items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-semibold text-gray-800 transition-colors hover:border-gray-500 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
        >
          Open Record Book
        </Link>
      </header>

      <div className="mb-6 flex flex-wrap gap-2" aria-label="Review state">
        {STATE_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={state === option.value}
            onClick={() => changeState(option.value)}
            className={`rounded-full px-3 py-1.5 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 ${
              state === option.value
                ? "bg-gray-950 text-white"
                : "border border-gray-300 bg-white text-gray-600 hover:border-gray-500 hover:text-gray-950"
            }`}
          >
            {option.label}
            <span className="ml-2 tabular-nums" aria-label={`${countFor(option.value)} suggestions`}>
              {countFor(option.value)}
            </span>
          </button>
        ))}
      </div>

      {error ? (
        <div role="alert" className="mb-5 border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <p className="font-semibold">Review queue unavailable</p>
          <p className="mt-1">{error}</p>
        </div>
      ) : null}
      {notice ? (
        <p role="status" className="mb-5 border border-green-200 bg-green-50 px-4 py-3 text-sm font-medium text-green-800">
          {notice}
        </p>
      ) : null}

      {loading ? (
        <QueueSkeleton />
      ) : queue && queue.items.length > 0 && selectedGame ? (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm lg:grid lg:grid-cols-[19rem_minmax(0,1fr)]">
          <aside className="border-b border-gray-200 bg-gray-50 lg:border-b-0 lg:border-r">
            <div className="border-b border-gray-200 px-4 py-3">
              <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">
                {queue.total_games} game{queue.total_games === 1 ? "" : "s"}
              </p>
            </div>
            <div className="max-h-[38rem] overflow-y-auto">
              {queue.items.map((game) => (
                <button
                  key={game.game_id}
                  type="button"
                  onClick={() => setSelectedGameId(game.game_id)}
                  className={`block w-full border-b border-gray-200 px-4 py-4 text-left transition-colors focus-visible:relative focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-yellow-500 ${
                    selectedGameId === game.game_id
                      ? "bg-yellow-50 text-gray-950"
                      : "bg-white text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  <span className="block text-sm font-bold leading-5">{gameTitle(game)}</span>
                  <span className="mt-1 flex items-center justify-between gap-3 text-xs text-gray-500">
                    <span>{formatDate(game.game_date)}</span>
                    <span className="font-semibold tabular-nums">
                      {game.suggestions.length} item{game.suggestions.length === 1 ? "" : "s"}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </aside>

          <section aria-labelledby="selected-game-heading" className="min-w-0">
            <div className="border-b border-gray-200 px-5 py-5 sm:px-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">
                    {formatDate(selectedGame.game_date)}
                    {selectedGame.season ? ` · ${selectedGame.season}` : ""}
                  </p>
                  <h2 id="selected-game-heading" className="mt-1 text-xl font-black text-gray-950">
                    {gameTitle(selectedGame)}
                  </h2>
                  {scoreline(selectedGame) ? (
                    <p className="mt-1 font-mono text-sm tabular-nums text-gray-600">
                      {scoreline(selectedGame)}
                    </p>
                  ) : null}
                </div>
                <div className="flex gap-3 text-sm font-semibold">
                  <Link className="text-gray-700 underline decoration-gray-300 underline-offset-4 hover:text-gray-950" to={`/games/${selectedGame.game_id}`}>
                    Game facts
                  </Link>
                  <a className="text-gray-700 underline decoration-gray-300 underline-offset-4 hover:text-gray-950" href={selectedGame.source_url} target="_blank" rel="noreferrer">
                    Source
                  </a>
                </div>
              </div>
            </div>

            <ol className="divide-y divide-gray-200">
              {selectedGame.suggestions.map((suggestion) => {
                const claimScope = contextText(suggestion.coverage_context.claim_scope);
                const limitations = contextText(suggestion.coverage_context.known_limitations);
                return (
                  <li key={suggestion.id} className="px-5 py-5 sm:px-6 sm:py-6">
                    <div className="flex gap-4">
                      <div className="grid size-8 shrink-0 place-items-center rounded-full bg-gray-950 text-xs font-black tabular-nums text-white" aria-label={`Rank ${suggestion.ai_rank}`}>
                        {suggestion.ai_rank}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-base font-semibold leading-6 text-gray-950">
                          {suggestion.phrasing}
                        </p>
                        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-600">
                          <span className="font-bold text-gray-800">{suggestion.player_name}</span>
                          <span>{achievementLabel(suggestion.achievement_type)}</span>
                          <span className="font-mono tabular-nums">
                            {suggestion.computed_value} {suggestion.stat_label}
                          </span>
                          {claimScope ? <span>{claimScope}</span> : null}
                        </div>
                        <div className="mt-3 bg-gray-50 px-3 py-2 text-xs leading-5 text-gray-600">
                          <span className="font-semibold text-gray-800">Evidence:</span>{" "}
                          warehouse-computed {suggestion.scope} fact
                          {limitations ? `; ${limitations}` : "."}
                          {suggestion.source_url ? (
                            <>
                              {" "}
                              <a className="font-semibold underline decoration-gray-300 underline-offset-2 hover:text-gray-950" href={suggestion.source_url} target="_blank" rel="noreferrer">
                                Inspect snapshot
                              </a>
                            </>
                          ) : null}
                        </div>
                        {state === "pending" ? (
                          <div className="mt-4 flex flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={() => void recordVerdict(suggestion, "approved")}
                              disabled={decisionId !== null}
                              className="rounded-md bg-yellow-400 px-4 py-2 text-sm font-bold text-gray-950 transition-colors hover:bg-yellow-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-wait disabled:opacity-50"
                            >
                              {decisionId === suggestion.id ? "Saving…" : "Approve for use"}
                            </button>
                            <button
                              type="button"
                              onClick={() => void recordVerdict(suggestion, "rejected")}
                              disabled={decisionId !== null}
                              className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-semibold text-gray-700 transition-colors hover:border-red-300 hover:text-red-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-wait disabled:opacity-50"
                            >
                              Reject suggestion
                            </button>
                          </div>
                        ) : (
                          <p className="mt-4 text-xs text-gray-500">
                            {state === "approved" ? "Approved" : "Rejected"} by{" "}
                            <span className="font-semibold text-gray-700">
                              {suggestion.reviewed_by ?? "SID reviewer"}
                            </span>{" "}
                            on {formatReviewedAt(suggestion.reviewed_at)}
                          </p>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>
        </div>
      ) : (
        <div className="border-y border-gray-200 bg-white px-6 py-14 text-center">
          <h2 className="text-lg font-bold text-gray-950">{stateConfig.emptyHeading}</h2>
          <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-gray-600">
            {stateConfig.emptyCopy}
          </p>
          {state === "pending" ? (
            <Link to="/record-book" className="mt-5 inline-block text-sm font-semibold text-gray-900 underline decoration-yellow-500 decoration-2 underline-offset-4">
              Explore verified leaders
            </Link>
          ) : null}
        </div>
      )}
    </div>
  );
}

export default AchievementReviewPage;
