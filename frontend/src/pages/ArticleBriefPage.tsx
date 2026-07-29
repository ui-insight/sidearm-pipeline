import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { articlesApi } from "../api/articles";
import type {
  ArticleBrief,
  ArticleDraftBlock,
  ArticleEvidenceChange,
  ArticleGenerationJob,
  ArticleStatus,
  ArticleType,
  ArticleValidationFinding,
  ArticleVersion,
} from "../types/article";

type WorkspaceView = "edit" | "side-by-side" | "changes";

function apiErrorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The Article action could not be completed.";
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function articleTypeLabel(value: ArticleType): string {
  return {
    game_recap: "Game recap",
    player_spotlight: "Player spotlight",
    achievement_story: "Achievement story",
  }[value];
}

function articleStatusLabel(status: ArticleStatus): string {
  return {
    brief: "Brief",
    generating: "Generating",
    in_edit: "In edit",
    ready: "Ready",
    needs_revalidation: "Needs revalidation",
    archived: "Archived",
  }[status];
}

function statusClass(status: ArticleStatus): string {
  if (status === "ready") return "bg-green-50 text-green-800 ring-green-200";
  if (status === "needs_revalidation") return "bg-red-50 text-red-800 ring-red-200";
  if (status === "generating") return "bg-yellow-50 text-yellow-900 ring-yellow-200";
  return "bg-gray-100 text-gray-700 ring-gray-200";
}

function gameTitle(brief: ArticleBrief): string {
  return (
    brief.game.title ??
    `${brief.game.away_team ?? "Away"} at ${brief.game.home_team ?? "Home"}`
  );
}

function generationIdempotencyKey(articleId: number): string {
  return `article-draft-${articleId}-${crypto.randomUUID()}`;
}

function revisionIdempotencyKey(articleId: number): string {
  return `article-revision-${articleId}-${crypto.randomUUID()}`;
}

function versionAuthor(version: ArticleVersion): string {
  return version.origin === "human"
    ? version.author ?? "SID editor"
    : version.model ?? "AI writer";
}

function versionLabel(version: ArticleVersion): string {
  return `Version ${version.version}`;
}

function valueRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function evidenceValueSummary(
  change: ArticleEvidenceChange,
  value: unknown,
): string {
  if (value === null || value === undefined) return "Not available";
  if (typeof value === "string") {
    return value.replace(/_/g, " ");
  }
  const record = valueRecord(value);
  if (!record) return String(value);
  if (change.change_type === "fact_changed") {
    return [record.player_name, record.computed_value, record.stat_label]
      .filter(Boolean)
      .join(" · ");
  }
  if (change.change_type === "coverage_changed") {
    return [record.claim_scope, record.completeness]
      .filter(Boolean)
      .join(" · ");
  }
  if (change.change_type === "source_changed") {
    const hash = typeof record.content_hash === "string"
      ? record.content_hash.slice(0, 12)
      : null;
    return [record.source_type, hash ? `SHA ${hash}` : null]
      .filter(Boolean)
      .join(" · ");
  }
  if (change.change_type === "game_changed") {
    const score = record.away_score !== undefined && record.home_score !== undefined
      ? `${String(record.away_score)}–${String(record.home_score)}`
      : null;
    return [record.title, score].filter(Boolean).join(" · ");
  }
  return JSON.stringify(record);
}

interface DiffToken {
  value: string;
  kind: "same" | "added" | "removed";
}

function wordDiff(before: string, after: string): DiffToken[] {
  const left = before.split(/(\s+)/).filter(Boolean);
  const right = after.split(/(\s+)/).filter(Boolean);
  let prefix = 0;
  while (
    prefix < left.length &&
    prefix < right.length &&
    left[prefix] === right[prefix]
  ) {
    prefix += 1;
  }
  let suffix = 0;
  while (
    suffix < left.length - prefix &&
    suffix < right.length - prefix &&
    left[left.length - suffix - 1] === right[right.length - suffix - 1]
  ) {
    suffix += 1;
  }
  return [
    ...left.slice(0, prefix).map((value) => ({ value, kind: "same" as const })),
    ...left
      .slice(prefix, left.length - suffix)
      .map((value) => ({ value, kind: "removed" as const })),
    ...right
      .slice(prefix, right.length - suffix)
      .map((value) => ({ value, kind: "added" as const })),
    ...left
      .slice(left.length - suffix)
      .map((value) => ({ value, kind: "same" as const })),
  ];
}

function ArticleBriefPage() {
  const { id } = useParams();
  const articleId = Number(id);
  const [brief, setBrief] = useState<ArticleBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [generationJob, setGenerationJob] = useState<ArticleGenerationJob | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [view, setView] = useState<WorkspaceView>("edit");
  const [headline, setHeadline] = useState("");
  const [blocks, setBlocks] = useState<ArticleDraftBlock[]>([]);
  const [saving, setSaving] = useState(false);
  const [revisionInstructions, setRevisionInstructions] = useState("");
  const [warningReasons, setWarningReasons] = useState<Record<string, string>>({});
  const [markingReady, setMarkingReady] = useState(false);
  const [refreshingEvidence, setRefreshingEvidence] = useState(false);

  const loadBrief = useCallback(async () => {
    if (!Number.isInteger(articleId) || articleId <= 0) {
      setError("Article not found.");
      setLoading(false);
      return;
    }
    try {
      const result = await articlesApi.get(articleId);
      setBrief(result);
      setGenerationJob(result.latest_generation_job ?? null);
      const latest = result.latest_version ?? null;
      setSelectedVersionId(latest?.id ?? null);
      setHeadline(latest?.headline ?? "");
      setBlocks(latest?.blocks ?? []);
      setError(null);
    } catch (loadError) {
      setError(apiErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [articleId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadBrief();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadBrief]);

  useEffect(() => {
    if (!generationJob || !["queued", "running"].includes(generationJob.state)) {
      return;
    }
    let active = true;
    const timer = window.setTimeout(async () => {
      try {
        const result = await articlesApi.getGenerationJob(articleId, generationJob.id);
        if (!active) return;
        setGenerationJob(result);
        if (result.state === "succeeded" && result.article_version) {
          const version = result.article_version;
          setBrief((current) =>
            current
              ? {
                  ...current,
                  status: "in_edit",
                  latest_generation_job: result,
                  latest_version: version,
                  ready_version: null,
                  versions: [...(current.versions ?? []), version],
                }
              : current,
          );
          setSelectedVersionId(version.id);
          setHeadline(version.headline);
          setBlocks(version.blocks);
          setRevisionInstructions("");
        } else if (result.state === "failed") {
          void loadBrief();
        }
      } catch (pollError) {
        if (active) setActionError(apiErrorMessage(pollError));
      }
    }, 1000);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [articleId, generationJob, loadBrief]);

  const versions = useMemo<ArticleVersion[]>(() => {
    const known = brief?.versions ?? [];
    if (known.length > 0) return known;
    return brief?.latest_version ? [brief.latest_version] : [];
  }, [brief]);
  const latestVersion: ArticleVersion | null =
    brief?.latest_version ?? versions[versions.length - 1] ?? null;
  const selectedVersion =
    versions.find((version) => version.id === selectedVersionId) ?? latestVersion;
  const originalVersion = versions[0] ?? null;
  const isLatestSelected = selectedVersion?.id === latestVersion?.id;
  const activeGeneration = generationJob
    ? ["queued", "running"].includes(generationJob.state)
    : false;
  const findings: ArticleValidationFinding[] =
    selectedVersion?.validation_results ?? [];
  const blockingFindings = findings.filter((finding) => finding.severity === "error");
  const warnings = findings.filter((finding) => finding.severity === "warning");
  const dirty = selectedVersion
    ? headline !== selectedVersion.headline ||
      JSON.stringify(blocks) !== JSON.stringify(selectedVersion.blocks)
    : false;

  function selectVersion(version: ArticleVersion) {
    setSelectedVersionId(version.id);
    setHeadline(version.headline);
    setBlocks(version.blocks);
    setWarningReasons({});
    setActionError(null);
  }

  async function generateDraft() {
    if (!brief) return;
    setActionError(null);
    try {
      const job = await articlesApi.generateDraft(
        brief.id,
        generationIdempotencyKey(brief.id),
      );
      setGenerationJob(job);
      setBrief({ ...brief, status: "generating", latest_generation_job: job });
    } catch (generationFailure) {
      setActionError(apiErrorMessage(generationFailure));
    }
  }

  async function requestRevision() {
    if (!brief || !latestVersion || !revisionInstructions.trim()) return;
    setActionError(null);
    try {
      const job = await articlesApi.generateDraft(
        brief.id,
        revisionIdempotencyKey(brief.id),
        {
          baseVersionId: latestVersion.id,
          editorInstructions: revisionInstructions.trim(),
        },
      );
      setGenerationJob(job);
      setBrief({ ...brief, status: "generating", latest_generation_job: job });
    } catch (revisionError) {
      setActionError(apiErrorMessage(revisionError));
    }
  }

  async function saveVersion() {
    if (!brief || !selectedVersion || !isLatestSelected) return;
    setSaving(true);
    setActionError(null);
    try {
      const saved = await articlesApi.saveVersion(brief.id, {
        base_version_id: selectedVersion.id,
        headline,
        headline_evidence_ids: selectedVersion.headline_evidence_ids,
        blocks,
      });
      setBrief({
        ...brief,
        status: "in_edit",
        latest_version: saved,
        ready_version: null,
        versions: [...versions, saved],
      });
      setSelectedVersionId(saved.id);
      setHeadline(saved.headline);
      setBlocks(saved.blocks);
      setWarningReasons({});
    } catch (saveError) {
      setActionError(apiErrorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  async function markReady() {
    if (!brief || !selectedVersion || !isLatestSelected) return;
    setMarkingReady(true);
    setActionError(null);
    try {
      const result = await articlesApi.markReady(
        brief.id,
        selectedVersion.id,
        warnings.map((warning) => ({
          finding_code: warning.code,
          reason: warningReasons[warning.code]?.trim() ?? "",
        })),
      );
      setBrief({
        ...brief,
        status: "ready",
        ready_version: result.ready_version,
        latest_version: result.ready_version,
        versions: versions.map((version) =>
          version.id === result.ready_version.id ? result.ready_version : version,
        ),
        readiness_history: [...(brief.readiness_history ?? []), result.decision],
      });
      setSelectedVersionId(result.ready_version.id);
    } catch (readyError) {
      setActionError(apiErrorMessage(readyError));
    } finally {
      setMarkingReady(false);
    }
  }

  async function refreshEvidence() {
    if (!brief) return;
    setRefreshingEvidence(true);
    setActionError(null);
    try {
      const refreshed = await articlesApi.refreshEvidence(brief.id);
      setBrief(refreshed);
      const latest = refreshed.latest_version ?? null;
      setSelectedVersionId(latest?.id ?? null);
      setHeadline(latest?.headline ?? "");
      setBlocks(latest?.blocks ?? []);
      setGenerationJob(refreshed.latest_generation_job ?? null);
      setWarningReasons({});
    } catch (refreshError) {
      setActionError(apiErrorMessage(refreshError));
    } finally {
      setRefreshingEvidence(false);
    }
  }

  if (loading) {
    return (
      <div aria-label="Loading Article Brief" className="mx-auto max-w-7xl animate-pulse px-4 py-10 sm:px-6 lg:px-8">
        <div className="h-8 w-2/3 bg-gray-200" />
        <div className="mt-6 h-96 bg-gray-100" />
      </div>
    );
  }

  if (error || !brief) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center sm:px-6">
        <h1 className="text-2xl font-black text-gray-950">Article Brief unavailable</h1>
        <p role="alert" className="mt-3 text-sm text-red-700">{error ?? "Article not found."}</p>
        <Link to="/articles" className="mt-6 inline-block text-sm font-semibold text-gray-900 underline decoration-yellow-500 decoration-2 underline-offset-4">
          Return to Article desk
        </Link>
      </div>
    );
  }

  const warningReasonsComplete = warnings.every(
    (warning) => (warningReasons[warning.code]?.trim().length ?? 0) >= 8,
  );
  const canMarkReady = Boolean(
    selectedVersion &&
      isLatestSelected &&
      !dirty &&
      !activeGeneration &&
      blockingFindings.length === 0 &&
      warningReasonsComplete &&
      brief.status !== "needs_revalidation" &&
      brief.ready_version?.id !== selectedVersion.id,
  );
  const evidenceBlocked = brief.status === "needs_revalidation";

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <nav aria-label="Breadcrumb" className="mb-6 text-sm text-gray-600">
        <Link to="/articles" className="font-semibold underline decoration-gray-300 underline-offset-4 hover:text-gray-950">Article desk</Link>
        <span aria-hidden="true" className="mx-2">/</span>
        Article {brief.id}
      </nav>

      <header className="border-b border-gray-300 pb-7">
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-yellow-700">Editorial Article</p>
          <span className={`rounded-full px-2.5 py-1 text-xs font-bold ring-1 ring-inset ${statusClass(brief.status)}`}>
            {articleStatusLabel(brief.status)}
          </span>
          {brief.ready_version ? (
            <span className="text-xs font-semibold text-green-800">Version {brief.ready_version.version} approved</span>
          ) : null}
        </div>
        <h1 className="mt-3 max-w-4xl text-3xl font-black tracking-tight text-gray-950">{brief.angle}</h1>
        <p className="mt-3 text-sm text-gray-600">
          {articleTypeLabel(brief.article_type)} for {brief.audience}. Owned by <span className="font-semibold text-gray-800">{brief.created_by}</span>.
        </p>
      </header>

      {actionError ? (
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <p role="alert" className="font-semibold">{actionError}</p>
          {actionError.toLowerCase().includes("stale") ? (
            <button type="button" onClick={() => void loadBrief()} className="font-bold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500">Load latest version</button>
          ) : null}
        </div>
      ) : null}

      {brief.active_revalidation ? (
        <section
          aria-labelledby="evidence-change-heading"
          className="mt-6 border-y border-red-300 bg-red-50 px-5 py-6 sm:px-7"
        >
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs font-bold uppercase tracking-[0.08em] text-red-800">
                Editorial hold
              </p>
              <h2 id="evidence-change-heading" className="mt-2 text-2xl font-black text-gray-950">
                Source evidence changed
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-700">
                This Article is locked against new drafts, edits, readiness, and
                distribution. Review the changed suggestions, renew the SID
                approvals, then refresh the evidence for a new review checkpoint.
              </p>
              <p className="mt-2 text-xs text-gray-600">
                Detected {formatDateTime(brief.active_revalidation.detected_at)}
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <Link
                to="/achievements"
                className="rounded-md border border-gray-300 bg-white px-4 py-2.5 text-sm font-bold text-gray-800 hover:border-gray-400 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
              >
                Review source suggestions
              </Link>
              <button
                type="button"
                onClick={() => void refreshEvidence()}
                disabled={refreshingEvidence}
                className="rounded-md bg-yellow-400 px-4 py-2.5 text-sm font-black text-gray-950 hover:bg-yellow-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-wait disabled:bg-gray-200 disabled:text-gray-500"
              >
                {refreshingEvidence ? "Refreshing evidence" : "Refresh approved evidence"}
              </button>
            </div>
          </div>

          <div className="mt-6 border-t border-red-200">
            {brief.active_revalidation.changes.map((change, index) => (
              <div
                key={`${change.change_type}-${change.suggestion_key ?? "game"}-${index}`}
                className="grid gap-3 border-b border-red-200 py-4 md:grid-cols-[minmax(12rem,0.7fr)_minmax(0,1fr)]"
              >
                <div>
                  <p className="text-sm font-bold text-gray-950">{change.label}</p>
                  {change.suggestion_key ? (
                    <p className="mt-1 break-all font-mono text-[11px] text-gray-600">
                      {change.suggestion_key}
                    </p>
                  ) : null}
                </div>
                <dl className="grid gap-3 text-xs sm:grid-cols-2">
                  <div>
                    <dt className="font-bold uppercase tracking-[0.06em] text-gray-500">Frozen</dt>
                    <dd className="mt-1 leading-5 text-gray-800">
                      {evidenceValueSummary(change, change.previous_value)}
                    </dd>
                  </div>
                  <div>
                    <dt className="font-bold uppercase tracking-[0.06em] text-red-800">Current</dt>
                    <dd className="mt-1 leading-5 text-gray-950">
                      {evidenceValueSummary(change, change.current_value)}
                    </dd>
                  </div>
                </dl>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {latestVersion && generationJob?.state === "failed" ? (
        <div className="mt-5 border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <p role="alert" className="font-semibold">
            {generationJob.error_message ?? "The AI revision failed."}
          </p>
          <p className="mt-1 text-xs leading-5">
            Your current Article Version is unchanged. Update the instructions and
            retry when ready.
          </p>
        </div>
      ) : null}

      {!latestVersion ? (
        <div className="mt-7 grid gap-7 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <section className="border-y border-gray-300 bg-white px-5 py-8 sm:px-7">
            <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">Frozen evidence</p>
            <h2 className="mt-2 text-2xl font-black text-gray-950">Brief ready for a first draft</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-gray-600">The writer receives only the approved facts shown here and the active versioned athletics Style Guide.</p>
            <button type="button" onClick={() => void generateDraft()} disabled={activeGeneration || evidenceBlocked} className="mt-6 rounded-md bg-gray-950 px-4 py-2.5 text-sm font-bold text-white hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:bg-gray-400">
              {activeGeneration ? "Generating draft" : generationJob?.state === "failed" ? "Retry draft" : "Generate draft"}
            </button>
            {activeGeneration ? (
              <p role="status" className="mt-4 text-sm font-semibold text-gray-800">
                {generationJob?.state === "queued"
                  ? "Draft queued"
                  : "Generating evidence-bound copy"}
              </p>
            ) : null}
            {generationJob?.state === "failed" ? (
              <div className="mt-5 border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                <p className="font-semibold">{generationJob.error_message ?? "Draft generation failed."}</p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs">
                  {generationJob.validation_results.map((finding, index) => <li key={`${finding.code}-${index}`}>{finding.message}</li>)}
                </ul>
              </div>
            ) : null}
          </section>
          <aside className="border-y border-gray-200 bg-white p-5">
            <h2 className="text-sm font-black text-gray-950">Brief evidence</h2>
            <p className="mt-2 text-sm leading-6 text-gray-600">{brief.evidence_bundle.suggestions.length} approved suggestion{brief.evidence_bundle.suggestions.length === 1 ? "" : "s"} from {gameTitle(brief)}.</p>
            <div className="mt-4 space-y-4 border-t border-gray-200 pt-4">
              {brief.evidence_bundle.suggestions.map((suggestion) => (
                <div key={suggestion.evidence_item_id} className="text-xs leading-5 text-gray-600">
                  <p className="font-semibold text-gray-900">
                    {suggestion.phrasing ?? `${suggestion.player_name}: ${suggestion.computed_value} ${suggestion.stat_label}`}
                  </p>
                  <p className="mt-2">{suggestion.coverage_window.claim_scope}</p>
                  {suggestion.coverage_window.known_limitations ? (
                    <p>{suggestion.coverage_window.known_limitations}</p>
                  ) : null}
                  <p className="mt-2">Created by {brief.created_by} · Evidence bundle v{brief.evidence_bundle.version}</p>
                  <a href={suggestion.source.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-block font-semibold text-gray-800 underline decoration-gray-300 underline-offset-2 hover:text-gray-950">
                    Inspect source snapshot
                  </a>
                </div>
              ))}
            </div>
          </aside>
        </div>
      ) : (
        <div className="mt-7 grid gap-6 xl:grid-cols-[14rem_minmax(0,1fr)_20rem]">
          <aside aria-label="Article version history" className="self-start border-y border-gray-300 bg-white xl:sticky xl:top-4">
            <div className="border-b border-gray-200 px-4 py-4">
              <h2 className="text-sm font-black text-gray-950">Version history</h2>
              <p className="mt-1 text-xs text-gray-500">Append-only checkpoints</p>
            </div>
            <ol className="divide-y divide-gray-200">
              {[...versions].reverse().map((version) => (
                <li key={version.id}>
                  <button type="button" onClick={() => selectVersion(version)} aria-current={selectedVersion?.id === version.id ? "true" : undefined} className={`w-full px-4 py-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-yellow-500 ${selectedVersion?.id === version.id ? "bg-yellow-50" : "hover:bg-gray-50"}`}>
                    <span className="flex items-center justify-between gap-2">
                      <span className="text-sm font-bold text-gray-950">{versionLabel(version)}</span>
                      {brief.ready_version?.id === version.id ? <span className="text-[10px] font-bold uppercase tracking-wide text-green-800">Ready</span> : null}
                    </span>
                    <span className="mt-1 block text-xs text-gray-600">{version.origin === "ai" ? "AI" : "Human"} by {versionAuthor(version)}</span>
                    <span className="mt-1 block text-[11px] text-gray-500">{formatDateTime(version.created_at)}</span>
                  </button>
                </li>
              ))}
            </ol>
          </aside>

          <main className="min-w-0 border-y border-gray-300 bg-white">
            <h2 className="sr-only">{selectedVersion?.headline}</h2>
            <div className="flex flex-col gap-4 border-b border-gray-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.08em] text-yellow-700">{selectedVersion ? versionLabel(selectedVersion) : "Current version"}</p>
                <p className="mt-1 text-xs text-gray-500">{selectedVersion ? `${selectedVersion.origin === "ai" ? "AI" : "Human"} checkpoint by ${versionAuthor(selectedVersion)}` : ""}</p>
              </div>
              <div className="flex gap-1 rounded-md bg-gray-100 p-1" aria-label="Editor view">
                {(["edit", "side-by-side", "changes"] as const).map((mode) => (
                  <button key={mode} type="button" aria-pressed={view === mode} onClick={() => setView(mode)} className={`rounded px-3 py-1.5 text-xs font-bold capitalize focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 ${view === mode ? "bg-white text-gray-950 shadow-sm" : "text-gray-600 hover:text-gray-950"}`}>
                    {mode === "side-by-side" ? "Side by side" : mode}
                  </button>
                ))}
              </div>
            </div>

            {view === "edit" ? (
              <div className="px-5 py-6 sm:px-7">
                {!isLatestSelected ? (
                  <p className="mb-5 border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700">This historical version is read-only. Select the latest version to continue editing.</p>
                ) : null}
                <label className="block text-xs font-bold uppercase tracking-[0.06em] text-gray-600" htmlFor="article-headline">Headline</label>
                <textarea id="article-headline" value={headline} onChange={(event) => setHeadline(event.target.value)} disabled={!isLatestSelected || activeGeneration || evidenceBlocked} rows={2} className="mt-2 w-full resize-y rounded-md border border-gray-300 bg-white px-3 py-2 text-2xl font-black leading-tight text-gray-950 focus:border-gray-950 focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:ring-offset-2 disabled:bg-gray-50 disabled:text-gray-600" />
                <p className="mt-2 font-mono text-[11px] text-gray-500">Evidence: {selectedVersion?.headline_evidence_ids.join(", ")}</p>

                <div className="mt-7 space-y-6">
                  {blocks.map((block, index) => (
                    <div key={`${block.kind}-${index}`} className="border-t border-gray-200 pt-5">
                      <div className="flex items-center justify-between gap-3">
                        <label className="text-xs font-bold uppercase tracking-[0.06em] text-gray-600" htmlFor={`article-block-${index}`}>{block.kind}</label>
                        <span className="font-mono text-[11px] text-gray-500">Evidence: {block.evidence_ids.join(", ")}</span>
                      </div>
                      <textarea id={`article-block-${index}`} value={block.text} onChange={(event) => setBlocks((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, text: event.target.value } : item))} disabled={!isLatestSelected || activeGeneration || evidenceBlocked} rows={Math.max(5, Math.ceil(block.text.length / 80))} className="mt-2 w-full resize-y rounded-md border border-gray-300 bg-white px-3 py-3 text-base leading-7 text-gray-800 focus:border-gray-950 focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:ring-offset-2 disabled:bg-gray-50 disabled:text-gray-600" />
                    </div>
                  ))}
                </div>
                {isLatestSelected ? (
                  <div className="mt-7 flex flex-wrap items-center gap-3 border-t border-gray-200 pt-5">
                    <button type="button" onClick={() => void saveVersion()} disabled={!dirty || saving || activeGeneration || evidenceBlocked || !headline.trim() || blocks.some((block) => !block.text.trim())} className="rounded-md bg-gray-950 px-4 py-2.5 text-sm font-bold text-white hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:bg-gray-300 disabled:text-gray-600">
                      {saving ? "Saving checkpoint" : "Save new version"}
                    </button>
                    <p className="text-xs text-gray-500">Saving creates a new immutable checkpoint. Version {selectedVersion?.version} never changes.</p>
                  </div>
                ) : null}
              </div>
            ) : view === "side-by-side" ? (
              <div className="grid divide-y divide-gray-200 md:grid-cols-2 md:divide-x md:divide-y-0">
                {[originalVersion, selectedVersion].map((version, column) => (
                  <article key={`${version?.id ?? column}-${column}`} className="min-w-0 px-5 py-6">
                    <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">{column === 0 ? "Original" : "Selected"} · v{version?.version}</p>
                    <h2 className="mt-3 text-xl font-black text-gray-950">{version?.headline}</h2>
                    <div className="mt-5 space-y-5">{version?.blocks.map((block, index) => <p key={`${block.kind}-${index}`} className="whitespace-pre-wrap text-sm leading-7 text-gray-700">{block.text}</p>)}</div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="px-5 py-6 sm:px-7">
                <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">Inline diff · original to selected</p>
                <div className="mt-4 text-xl font-black leading-8 text-gray-950">
                  {wordDiff(originalVersion?.headline ?? "", selectedVersion?.headline ?? "").map((token, index) => token.kind === "removed" ? <del key={index} className="bg-red-100 text-red-900">{token.value}</del> : token.kind === "added" ? <ins key={index} className="bg-green-100 text-green-900 no-underline">{token.value}</ins> : <span key={index}>{token.value}</span>)}
                </div>
                <div className="mt-6 space-y-5 text-sm leading-7 text-gray-700">
                  {(selectedVersion?.blocks ?? []).map((block, index) => {
                    const originalText = originalVersion?.blocks[index]?.text ?? "";
                    return <p key={`${block.kind}-${index}`}>{wordDiff(originalText, block.text).map((token, tokenIndex) => token.kind === "removed" ? <del key={tokenIndex} className="bg-red-100 text-red-900">{token.value}</del> : token.kind === "added" ? <ins key={tokenIndex} className="bg-green-100 text-green-900 no-underline">{token.value}</ins> : <span key={tokenIndex}>{token.value}</span>)}</p>;
                  })}
                </div>
                <div className="mt-6 flex flex-wrap gap-4 text-xs text-gray-600"><span><span className="mr-1 inline-block size-3 bg-green-100 align-middle" />Added</span><span><span className="mr-1 inline-block size-3 bg-red-100 align-middle" />Removed</span></div>
              </div>
            )}
          </main>

          <aside className="space-y-5 self-start xl:sticky xl:top-4">
            <section className="border-y border-gray-300 bg-white p-5">
              <h2 className="text-sm font-black text-gray-950">Validation</h2>
              {findings.length === 0 ? (
                <div className="mt-3 text-sm text-green-800">
                  <p className="font-semibold">Draft validated</p>
                  <p className="mt-1 text-xs">No fact or Style Guide findings</p>
                </div>
              ) : (
                <ul className="mt-3 space-y-3">
                  {findings.map((finding, index) => (
                    <li key={`${finding.code}-${index}`} className={`border p-3 text-xs leading-5 ${finding.severity === "error" ? "border-red-200 bg-red-50 text-red-800" : "border-yellow-200 bg-yellow-50 text-yellow-900"}`}>
                      <p className="font-bold uppercase tracking-wide">{finding.severity}</p>
                      <p className="mt-1">{finding.message}</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {selectedVersion && isLatestSelected ? (
              <section className="border-y border-gray-300 bg-white p-5">
                <h2 className="text-sm font-black text-gray-950">Ready for distribution</h2>
                <p className="mt-2 text-sm leading-6 text-gray-600">This approves the exact immutable version. It does not publish or contact a channel.</p>
                {warnings.map((warning: ArticleValidationFinding) => (
                  <label key={warning.code} className="mt-4 block text-xs font-bold text-gray-700">
                    Reason for {warning.code}
                    <textarea value={warningReasons[warning.code] ?? ""} onChange={(event) => setWarningReasons((current) => ({ ...current, [warning.code]: event.target.value }))} rows={3} placeholder="Record why this warning is acceptable" className="mt-2 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal text-gray-800 focus:border-gray-950 focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:ring-offset-2" />
                  </label>
                ))}
                {blockingFindings.length > 0 ? <p className="mt-4 text-xs font-semibold leading-5 text-red-800">Resolve {blockingFindings.length} blocking finding{blockingFindings.length === 1 ? "" : "s"} in a new version first.</p> : null}
                {dirty ? <p className="mt-4 text-xs font-semibold leading-5 text-yellow-900">Save your edits before marking a version ready.</p> : null}
                <button type="button" onClick={() => void markReady()} disabled={!canMarkReady || markingReady} className="mt-5 w-full rounded-md bg-yellow-400 px-4 py-2.5 text-sm font-black text-gray-950 transition-colors hover:bg-yellow-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-500">
                  {brief.ready_version?.id === selectedVersion.id ? "Version approved" : markingReady ? "Recording approval" : `Mark version ${selectedVersion.version} ready`}
                </button>
              </section>
            ) : null}

            {latestVersion && isLatestSelected ? (
              <section className="border-y border-gray-200 bg-white p-5">
                <h2 className="text-sm font-black text-gray-950">Request AI revision</h2>
                <p className="mt-2 text-xs leading-5 text-gray-600">Instructions and the current copy go to the writer. The evidence boundary stays frozen.</p>
                <label htmlFor="revision-instructions" className="sr-only">AI revision instructions</label>
                <textarea id="revision-instructions" value={revisionInstructions} onChange={(event) => setRevisionInstructions(event.target.value)} rows={4} maxLength={2000} placeholder="For example: tighten the lead and move the score to the second paragraph." className="mt-3 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 focus:border-gray-950 focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:ring-offset-2" />
                <button type="button" onClick={() => void requestRevision()} disabled={activeGeneration || evidenceBlocked || dirty || !revisionInstructions.trim()} className="mt-3 w-full rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-bold text-gray-800 hover:border-gray-400 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:text-gray-400">
                  {activeGeneration ? "AI revision in progress" : "Request evidence-bound revision"}
                </button>
              </section>
            ) : null}

            <details className="border-y border-gray-200 bg-white p-5">
              <summary className="cursor-pointer text-sm font-black text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500">Evidence and audit</summary>
              <div className="mt-4 space-y-4 text-xs text-gray-600">
                <p><span className="font-bold text-gray-800">Game:</span> {gameTitle(brief)}</p>
                {brief.evidence_bundle.suggestions.map((suggestion) => (
                  <div key={suggestion.evidence_item_id} className="border-t border-gray-200 pt-3">
                    <p className="font-semibold leading-5 text-gray-800">{suggestion.phrasing ?? `${suggestion.player_name}: ${suggestion.computed_value} ${suggestion.stat_label}`}</p>
                    <p className="mt-1">Coverage: {suggestion.coverage_window.claim_scope}</p>
                    <a href={suggestion.source.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-block font-semibold underline decoration-gray-300 underline-offset-2 hover:text-gray-950">Inspect source snapshot</a>
                  </div>
                ))}
                <p className="break-all border-t border-gray-200 pt-3 font-mono text-[10px]">Evidence SHA-256: {brief.evidence_bundle.content_hash}</p>
              </div>
            </details>
          </aside>
        </div>
      )}
    </div>
  );
}

export default ArticleBriefPage;
