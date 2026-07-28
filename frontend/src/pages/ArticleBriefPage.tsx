import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { articlesApi } from "../api/articles";
import { ApiError } from "../api/client";
import type {
  ArticleBrief,
  ArticleGenerationJob,
  ArticleType,
} from "../types/article";

function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.data === "object" && error.data && "detail" in error.data) {
      return String(error.data.detail);
    }
    return error.message;
  }
  return error instanceof Error
    ? error.message
    : "The Article Brief could not be loaded.";
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function articleTypeLabel(value: ArticleType): string {
  const labels: Record<ArticleType, string> = {
    achievement_story: "Achievement story",
    game_recap: "Game recap",
    player_spotlight: "Player spotlight",
  };
  return labels[value];
}

function gameTitle(brief: ArticleBrief): string {
  return (
    brief.game.title ??
    `${brief.game.away_team ?? "Away"} at ${brief.game.home_team ?? "Home"}`
  );
}

function articleStatusLabel(status: ArticleBrief["status"]): string {
  const labels: Record<ArticleBrief["status"], string> = {
    archived: "Archived",
    brief: "Brief",
    generating: "Generating",
    in_edit: "In edit",
    needs_revalidation: "Needs revalidation",
    ready: "Ready",
  };
  return labels[status];
}

function generationIdempotencyKey(articleId: number): string {
  return `article-draft-${articleId}-${Date.now()}-${Math.random()
    .toString(36)
    .slice(2)}`;
}

function ArticleBriefPage() {
  const { id } = useParams();
  const articleId = Number(id);
  const [brief, setBrief] = useState<ArticleBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generationJob, setGenerationJob] =
    useState<ArticleGenerationJob | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function loadBrief() {
      if (!Number.isInteger(articleId) || articleId <= 0) {
        setError("Article not found.");
        setLoading(false);
        return;
      }
      try {
        const result = await articlesApi.get(articleId);
        if (active) {
          setBrief(result);
          setGenerationJob(result.latest_generation_job ?? null);
        }
      } catch (loadError) {
        if (active) setError(apiErrorMessage(loadError));
      } finally {
        if (active) setLoading(false);
      }
    }
    void loadBrief();
    return () => {
      active = false;
    };
  }, [articleId]);

  useEffect(() => {
    if (
      !generationJob ||
      (generationJob.state !== "queued" && generationJob.state !== "running")
    ) {
      return;
    }
    let active = true;
    const timer = window.setTimeout(async () => {
      try {
        const result = await articlesApi.getGenerationJob(
          articleId,
          generationJob.id,
        );
        if (!active) return;
        setGenerationError(null);
        setGenerationJob(result);
        if (result.state === "succeeded" && result.article_version) {
          setBrief((current) =>
            current
              ? {
                  ...current,
                  status: "in_edit",
                  latest_generation_job: result,
                  latest_version: result.article_version,
                }
              : current,
          );
        } else if (result.state === "failed") {
          setBrief((current) =>
            current ? { ...current, status: "brief" } : current,
          );
        }
      } catch (pollError) {
        if (active) {
          setGenerationError(apiErrorMessage(pollError));
          setGenerationJob((current) =>
            current ? { ...current } : current,
          );
        }
      }
    }, 1000);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [articleId, generationJob]);

  async function generateDraft() {
    if (!brief) return;
    setGenerationError(null);
    try {
      const job = await articlesApi.generateDraft(
        brief.id,
        generationIdempotencyKey(brief.id),
      );
      setGenerationJob(job);
      setBrief({ ...brief, status: "generating", latest_generation_job: job });
    } catch (generationFailure) {
      setGenerationError(apiErrorMessage(generationFailure));
    }
  }

  if (loading) {
    return (
      <div
        aria-label="Loading Article Brief"
        className="mx-auto max-w-5xl animate-pulse px-4 py-10 sm:px-6 lg:px-8"
      >
        <div className="h-8 w-2/3 bg-gray-200" />
        <div className="mt-6 h-48 bg-gray-100" />
      </div>
    );
  }

  if (error || !brief) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center sm:px-6">
        <h1 className="text-2xl font-black text-gray-950">
          Article Brief unavailable
        </h1>
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error ?? "Article not found."}
        </p>
        <Link
          to="/achievements"
          className="mt-6 inline-block text-sm font-semibold text-gray-900 underline decoration-yellow-500 decoration-2 underline-offset-4"
        >
          Return to Achievement desk
        </Link>
      </div>
    );
  }

  const activeGeneration =
    generationJob?.state === "queued" || generationJob?.state === "running";
  const latestVersion =
    generationJob?.article_version ?? brief.latest_version ?? null;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <nav aria-label="Breadcrumb" className="mb-6 text-sm text-gray-600">
        <Link
          to="/achievements"
          className="font-semibold underline decoration-gray-300 underline-offset-4 hover:text-gray-950"
        >
          Achievement desk
        </Link>
        <span aria-hidden="true" className="mx-2">
          /
        </span>
        Article {brief.id}
      </nav>

      <header className="border-b border-gray-300 pb-7">
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-yellow-700">
            Article Brief
          </p>
          <span className="rounded-full bg-gray-950 px-2.5 py-1 text-xs font-bold text-white">
            {articleStatusLabel(brief.status)}
          </span>
        </div>
        <h1 className="mt-3 max-w-4xl text-3xl font-black tracking-tight text-gray-950">
          {brief.angle}
        </h1>
        <p className="mt-3 text-sm text-gray-600">
          {articleTypeLabel(brief.article_type)} for {brief.audience}
        </p>
      </header>

      <div className="mt-7 grid gap-7 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div>
          {latestVersion ? (
            <section className="mb-7 rounded-lg border border-gray-300 bg-white shadow-sm">
              <div className="border-b border-gray-200 px-5 py-5 sm:px-6">
                <p className="text-xs font-bold uppercase tracking-[0.08em] text-yellow-700">
                  AI Article Version {latestVersion.version}
                </p>
                <h2 className="mt-2 text-2xl font-black tracking-tight text-gray-950">
                  {latestVersion.headline}
                </h2>
                <p className="mt-2 font-mono text-[11px] text-gray-500">
                  Evidence: {latestVersion.headline_evidence_ids.join(", ")}
                </p>
              </div>
              <div className="space-y-5 px-5 py-6 sm:px-6">
                {latestVersion.blocks.map((block, index) => (
                  <div key={`${block.kind}-${index}`}>
                    <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">
                      {block.kind}
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-base leading-7 text-gray-800">
                      {block.text}
                    </p>
                    <p className="mt-2 font-mono text-[11px] text-gray-500">
                      Evidence: {block.evidence_ids.join(", ")}
                    </p>
                  </div>
                ))}
              </div>
              <div className="border-t border-gray-200 bg-gray-50 px-5 py-4 text-xs text-gray-600 sm:px-6">
                Generated with {latestVersion.model ?? "configured model"} · Prompt{" "}
                {latestVersion.prompt_version ?? "unknown"} · Style snapshot{" "}
                {latestVersion.style_hash.slice(0, 12)}
              </div>
            </section>
          ) : null}

          <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 px-5 py-5 sm:px-6">
              <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">
                {brief.game.game_date ?? "Date unavailable"}
                {brief.game.season ? ` · ${brief.game.season}` : ""}
              </p>
              <h2 className="mt-1 text-xl font-black text-gray-950">
                {gameTitle(brief)}
              </h2>
              {brief.game.away_score !== null &&
              brief.game.home_score !== null ? (
                <p className="mt-1 font-mono text-sm tabular-nums text-gray-600">
                  {brief.game.away_team ?? "Away"} {brief.game.away_score},{" "}
                  {brief.game.home_team ?? "Home"} {brief.game.home_score}
                </p>
              ) : null}
            </div>

            <div className="px-5 py-5 sm:px-6">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">
                    Frozen evidence
                  </p>
                  <h2 className="mt-1 text-lg font-black text-gray-950">
                    {brief.evidence_bundle.suggestions.length} approved suggestion
                    {brief.evidence_bundle.suggestions.length === 1 ? "" : "s"}
                  </h2>
                </div>
                <Link
                  to={`/games/${brief.game.id}`}
                  className="text-sm font-semibold text-gray-800 underline decoration-gray-300 underline-offset-4 hover:text-gray-950"
                >
                  Game facts
                </Link>
              </div>
            </div>

            <ol className="divide-y divide-gray-200 border-t border-gray-200">
              {brief.evidence_bundle.suggestions.map((suggestion) => (
                <li key={suggestion.evidence_item_id} className="px-5 py-6 sm:px-6">
                  <p className="text-base font-semibold leading-6 text-gray-950">
                    {suggestion.phrasing ??
                      `${suggestion.player_name}: ${suggestion.computed_value} ${suggestion.stat_label}`}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-600">
                    <span className="font-bold text-gray-800">
                      {suggestion.player_name}
                    </span>
                    <span className="font-mono tabular-nums">
                      {suggestion.computed_value} {suggestion.stat_label}
                    </span>
                    <span>{suggestion.coverage_window.claim_scope}</span>
                  </div>
                  <div className="mt-4 border border-yellow-200 bg-yellow-50 px-4 py-3 text-xs leading-5 text-gray-600">
                    <p>
                      <span className="font-semibold text-gray-800">
                        Coverage:
                      </span>{" "}
                      {suggestion.coverage_window.completeness}
                      {suggestion.coverage_window.known_limitations
                        ? `; ${suggestion.coverage_window.known_limitations}`
                        : ""}
                    </p>
                    <p className="mt-1">
                      Approved by{" "}
                      <span className="font-semibold text-gray-800">
                        {suggestion.verdict.reviewed_by}
                      </span>{" "}
                      on {formatDateTime(suggestion.verdict.reviewed_at)}
                    </p>
                    <a
                      href={suggestion.source.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2 inline-block font-semibold text-gray-800 underline decoration-gray-300 underline-offset-2 hover:text-gray-950"
                    >
                      Inspect source snapshot
                    </a>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>

        <aside className="space-y-5">
          <section className="rounded-lg border border-gray-300 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-black text-gray-950">Article writer</h2>
            {activeGeneration ? (
              <div role="status" className="mt-3 text-sm leading-6 text-gray-600">
                <p className="font-semibold text-gray-900">
                  {generationJob?.state === "queued"
                    ? "Draft queued"
                    : "Generating evidence-bound copy"}
                </p>
                <p>
                  The durable job can resume safely if the service restarts.
                </p>
              </div>
            ) : latestVersion ? (
              <div className="mt-3 text-sm leading-6 text-gray-600">
                <p className="font-semibold text-green-800">Draft validated</p>
                <p>
                  The copy passed deterministic fact and blocking style checks.
                  Human editing and readiness approval come next.
                </p>
              </div>
            ) : (
              <p className="mt-2 text-sm leading-6 text-gray-600">
                Generate a first draft using only this frozen evidence and the
                active versioned athletics Style Guide.
              </p>
            )}

            {generationJob?.state === "failed" ? (
              <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                <p role="alert" className="font-semibold">
                  {generationJob.error_message ?? "Draft generation failed."}
                </p>
                {generationJob.validation_results.length > 0 ? (
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-xs">
                    {generationJob.validation_results.map((finding, index) => (
                      <li key={`${finding.code}-${index}`}>{finding.message}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}

            {generationError ? (
              <p role="alert" className="mt-3 text-sm text-red-700">
                {generationError}
              </p>
            ) : null}

            {!latestVersion && !activeGeneration && brief.status === "brief" ? (
              <button
                type="button"
                onClick={() => void generateDraft()}
                className="mt-4 w-full bg-gray-950 px-4 py-2.5 text-sm font-bold text-white hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:ring-offset-2"
              >
                {generationJob?.state === "failed" ? "Retry draft" : "Generate draft"}
              </button>
            ) : null}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-black text-gray-950">Audit record</h2>
            <dl className="mt-4 space-y-3 text-xs">
              <div>
                <dt className="font-bold uppercase tracking-[0.06em] text-gray-500">
                  Created
                </dt>
                <dd className="mt-1 text-gray-700">
                  Created by {brief.created_by} · {formatDateTime(brief.created_at)}
                </dd>
              </div>
              <div>
                <dt className="font-bold uppercase tracking-[0.06em] text-gray-500">
                  Evidence
                </dt>
                <dd className="mt-1 text-gray-700">
                  Evidence bundle v{brief.evidence_bundle.version}
                </dd>
              </div>
              <div>
                <dt className="font-bold uppercase tracking-[0.06em] text-gray-500">
                  SHA-256
                </dt>
                <dd className="mt-1 break-all font-mono text-[11px] text-gray-600">
                  {brief.evidence_bundle.content_hash}
                </dd>
              </div>
            </dl>
          </section>

          {brief.constraints ? (
            <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-black text-gray-950">
                Writer constraints
              </h2>
              <p className="mt-2 text-sm leading-6 text-gray-600">
                {brief.constraints}
              </p>
            </section>
          ) : null}

          <section className="border border-yellow-200 bg-yellow-50 p-5">
            <h2 className="text-sm font-black text-gray-950">Next gate</h2>
            <p className="mt-2 text-sm leading-6 text-gray-600">
              {latestVersion
                ? "A human editor must review and approve an immutable version before any channel rendition can be created."
                : "This brief freezes what the writer may use. Generation never approves or distributes copy."}
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}

export default ArticleBriefPage;
