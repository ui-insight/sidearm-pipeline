import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { ingestRunsApi } from "../api/ingestRuns";
import { sourcesApi } from "../api/sources";
import type { HistoricalRangeBackfill } from "../types/historicalBackfill";
import type { IngestRun } from "../types/ingestRun";

const DEFAULT_SEASON = "2024-25";

function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.data === "object" && error.data && "detail" in error.data) {
      return String(error.data.detail);
    }
    return error.message;
  }
  return error instanceof Error ? error.message : "The backfill could not be started.";
}

function metadataString(run: IngestRun, key: string): string | null {
  const value = run.run_metadata[key];
  return typeof value === "string" ? value : null;
}

function metadataNumber(run: IngestRun, key: string): number {
  const value = run.run_metadata[key];
  return typeof value === "number" ? value : 0;
}

function checkpointCount(run: IngestRun): number {
  const seasons = run.run_metadata.seasons;
  return Array.isArray(seasons) ? seasons.length : 0;
}

function seasonCount(run: IngestRun): number {
  const seasons = run.run_metadata.season_order;
  return Array.isArray(seasons) ? seasons.length : 0;
}

function formatTimestamp(value: string | null): string {
  if (!value) return "Still running";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusClasses(status: string): string {
  if (status === "succeeded") return "bg-green-50 text-green-800";
  if (status === "failed") return "bg-red-50 text-red-800";
  if (status === "running") return "bg-yellow-50 text-yellow-900";
  return "bg-gray-100 text-gray-700";
}

function HistoricalBackfillPage() {
  const [startSeason, setStartSeason] = useState(DEFAULT_SEASON);
  const [endSeason, setEndSeason] = useState(DEFAULT_SEASON);
  const [delaySeconds, setDelaySeconds] = useState("1");
  const [resumeRunId, setResumeRunId] = useState<number | null>(null);
  const [runs, setRuns] = useState<IngestRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<HistoricalRangeBackfill | null>(null);

  const loadRuns = useCallback(async () => {
    try {
      setRuns(await ingestRunsApi.listHistoricalWbbRanges());
    } catch (loadError) {
      setError(apiErrorMessage(loadError));
    } finally {
      setRunsLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;

    async function loadInitialRuns() {
      try {
        const loadedRuns = await ingestRunsApi.listHistoricalWbbRanges();
        if (active) setRuns(loadedRuns);
      } catch (loadError) {
        if (active) setError(apiErrorMessage(loadError));
      } finally {
        if (active) setRunsLoading(false);
      }
    }

    void loadInitialRuns();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!submitting) return undefined;
    const pollId = window.setInterval(() => {
      void loadRuns();
    }, 2000);
    return () => window.clearInterval(pollId);
  }, [loadRuns, submitting]);

  async function submitBackfill(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const completed = await sourcesApi.backfillHistoricalWbbRange({
        startSeason,
        endSeason,
        boxscoreDelaySeconds: Number(delaySeconds),
        resumeRunId: resumeRunId ?? undefined,
      });
      setResult(completed);
      setResumeRunId(null);
    } catch (submitError) {
      setError(apiErrorMessage(submitError));
    } finally {
      setSubmitting(false);
      await loadRuns();
    }
  }

  function prepareResume(run: IngestRun) {
    setStartSeason(metadataString(run, "start_season") ?? DEFAULT_SEASON);
    setEndSeason(metadataString(run, "end_season") ?? DEFAULT_SEASON);
    setDelaySeconds(String(run.run_metadata.boxscore_delay_seconds ?? 1));
    setResumeRunId(run.id);
    setResult(null);
    setError(null);
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <header className="mb-8 max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-yellow-700">
          Data operations
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-gray-950">
          Historical backfills
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
          Run completed women&apos;s basketball seasons in order. Each season is
          checkpointed, so a failed range can resume without repeating completed work.
        </p>
      </header>

      <section className="mb-8 overflow-hidden rounded-lg border border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-5 py-4 sm:px-6">
          <h2 className="text-lg font-semibold text-gray-950">Launch a range</h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-gray-600">
            Use academic seasons such as 2024-25. The request stays open while the
            run advances, and recent checkpoints refresh below.
          </p>
        </div>

        {resumeRunId !== null && (
          <div className="flex flex-col gap-2 border-b border-yellow-200 bg-yellow-50 px-5 py-3 text-sm text-gray-800 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <span>
              Resume run <strong className="font-semibold">{resumeRunId}</strong> with
              its original season range.
            </span>
            <button
              type="button"
              onClick={() => setResumeRunId(null)}
              className="self-start font-medium text-gray-700 underline decoration-gray-300 underline-offset-2 hover:decoration-yellow-600 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 sm:self-auto"
            >
              Start a new run instead
            </button>
          </div>
        )}

        <form
          onSubmit={submitBackfill}
          className="grid gap-4 px-5 py-5 sm:grid-cols-2 sm:px-6 lg:grid-cols-[1fr_1fr_10rem_auto] lg:items-end"
        >
          <label className="grid gap-1.5 text-xs font-semibold uppercase tracking-[0.06em] text-gray-600">
            Start season
            <input
              required
              pattern="20[0-9]{2}-[0-9]{2}"
              title="Use an academic season such as 2024-25"
              value={startSeason}
              onChange={(event) => setStartSeason(event.target.value)}
              className="rounded-md border border-gray-300 bg-white px-3 py-2 font-mono text-sm font-normal normal-case tracking-normal text-gray-950 outline-none focus:border-gray-950 focus:ring-2 focus:ring-yellow-400 focus:ring-offset-2"
            />
          </label>
          <label className="grid gap-1.5 text-xs font-semibold uppercase tracking-[0.06em] text-gray-600">
            End season
            <input
              required
              pattern="20[0-9]{2}-[0-9]{2}"
              title="Use an academic season such as 2024-25"
              value={endSeason}
              onChange={(event) => setEndSeason(event.target.value)}
              className="rounded-md border border-gray-300 bg-white px-3 py-2 font-mono text-sm font-normal normal-case tracking-normal text-gray-950 outline-none focus:border-gray-950 focus:ring-2 focus:ring-yellow-400 focus:ring-offset-2"
            />
          </label>
          <label className="grid gap-1.5 text-xs font-semibold uppercase tracking-[0.06em] text-gray-600">
            Delay (seconds)
            <input
              required
              type="number"
              min="0.25"
              max="10"
              step="0.25"
              value={delaySeconds}
              onChange={(event) => setDelaySeconds(event.target.value)}
              className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-gray-950 outline-none focus:border-gray-950 focus:ring-2 focus:ring-yellow-400 focus:ring-offset-2"
            />
          </label>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-yellow-500 px-4 py-2 text-sm font-semibold text-gray-950 transition-colors hover:bg-yellow-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting
              ? "Backfill running..."
              : resumeRunId === null
                ? "Start backfill"
                : `Resume run ${resumeRunId}`}
          </button>
        </form>
      </section>

      {error && (
        <p
          role="alert"
          className="mb-6 border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {error}
        </p>
      )}

      {result && (
        <section
          aria-live="polite"
          className="mb-8 overflow-hidden rounded-lg border border-gray-200 bg-white"
        >
          <div className="flex flex-col gap-2 border-b border-gray-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div>
              <h2 className="text-lg font-semibold text-gray-950">
                Run {result.run_id} finished
              </h2>
              <p className="mt-1 text-sm text-gray-600">
                {result.seasons_attempted} attempted, {result.seasons_skipped} skipped
              </p>
            </div>
            <span
              className={`self-start rounded-full px-2 py-0.5 text-xs font-medium sm:self-auto ${statusClasses(result.status)}`}
            >
              {result.status}
            </span>
          </div>
          <ol className="divide-y divide-gray-200">
            {result.seasons.map((seasonResult) => (
              <li
                key={seasonResult.season}
                className="grid gap-2 px-5 py-4 text-sm sm:grid-cols-[8rem_7rem_1fr] sm:items-center sm:px-6"
              >
                <span className="font-mono font-medium text-gray-950">
                  {seasonResult.season}
                </span>
                <span className="text-gray-700">{seasonResult.status}</span>
                <span className="text-gray-600">
                  {seasonResult.coverage
                    ? `${seasonResult.coverage.final_games_ingested} of ${seasonResult.coverage.final_games} finals ingested, ${seasonResult.coverage.open_identity_issues} identity reviews`
                    : seasonResult.error_message ?? "No coverage result"}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 sm:px-6">
          <div>
            <h2 className="text-lg font-semibold text-gray-950">Recent range runs</h2>
            <p className="mt-1 text-sm text-gray-600">
              Parent checkpoints and resumable failures, newest first.
            </p>
          </div>
          {submitting && (
            <span className="text-xs font-medium text-yellow-800">Polling checkpoints</span>
          )}
        </div>

        {runsLoading ? (
          <div className="animate-pulse divide-y divide-gray-100" aria-label="Loading runs">
            {[0, 1, 2].map((row) => (
              <div key={row} className="h-20 bg-gray-50 px-6 py-4" />
            ))}
          </div>
        ) : runs.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="text-sm font-semibold text-gray-950">No historical runs yet</p>
            <p className="mt-1 text-sm text-gray-500">
              Start with one completed season to verify coverage and source shape.
            </p>
          </div>
        ) : (
          <ol className="divide-y divide-gray-200">
            {runs.map((run) => {
              const start = metadataString(run, "start_season") ?? "Unknown";
              const end = metadataString(run, "end_season") ?? start;
              const failures = metadataNumber(run, "seasons_failed");
              const canResume = run.status === "failed" || failures > 0;
              return (
                <li
                  key={run.id}
                  className="grid gap-3 px-5 py-4 sm:px-6 lg:grid-cols-[7rem_10rem_1fr_auto] lg:items-center"
                >
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.06em] text-gray-500">
                      Run
                    </p>
                    <p className="mt-1 font-mono text-sm font-semibold text-gray-950">
                      {run.id}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.06em] text-gray-500">
                      Range
                    </p>
                    <p className="mt-1 font-mono text-sm text-gray-800">
                      {start === end ? start : `${start} to ${end}`}
                    </p>
                  </div>
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusClasses(run.status)}`}
                      >
                        {run.status}
                      </span>
                      <span className="text-xs tabular-nums text-gray-500">
                        {checkpointCount(run)} of {seasonCount(run)} seasons checkpointed
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-gray-500">
                      Updated {formatTimestamp(run.finished_at ?? metadataString(run, "last_checkpoint_at"))}
                    </p>
                  </div>
                  {canResume ? (
                    <button
                      type="button"
                      onClick={() => prepareResume(run)}
                      className="self-start rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:border-gray-400 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 lg:self-auto"
                    >
                      Prepare resume
                    </button>
                  ) : (
                    <span className="text-xs text-gray-500 lg:text-right">
                      {run.status === "running" ? "In progress" : "No retry needed"}
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </div>
  );
}

export default HistoricalBackfillPage;
