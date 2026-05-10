import { useState } from "react";
import { gamesApi } from "../api/games";
import { agentRunsApi } from "../api/agentRuns";
import { ApiError } from "../api/client";
import type { AgentRunRead } from "../types/agentRun";
import type { GeneratedContent } from "../types/game";

interface Props {
  gameId: number;
  approvedContent: GeneratedContent | null;
  onContentApproved: (content: GeneratedContent) => void;
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs uppercase tracking-wide text-gray-500 mb-1">
      {children}
    </p>
  );
}

function CopyableBlock({
  label,
  text,
  children,
}: {
  label: string;
  text: string;
  children: React.ReactNode;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <Label>{label}</Label>
        <button onClick={copy} className="text-xs text-gray-500 hover:text-gray-900">
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {children}
    </div>
  );
}

function EvalChip({
  name,
  passed,
  score,
}: {
  name: string;
  passed: boolean | null;
  score: number | null;
}) {
  const ok = passed ?? (score != null && score >= 0.5);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${
        ok
          ? "border-green-200 bg-green-50 text-green-700"
          : "border-red-200 bg-red-50 text-red-700"
      }`}
    >
      {ok ? "✓" : "✗"} {name}
      {score != null && ` ${Math.round(score * 100)}%`}
    </span>
  );
}

type EditFields = {
  headline: string;
  recap: string;
  spotlight_player: string;
  spotlight_body: string;
  social_post: string;
};

function CoverageReviewPanel({ gameId, approvedContent, onContentApproved }: Props) {
  const [pendingRun, setPendingRun] = useState<AgentRunRead | null>(null);
  const [generating, setGenerating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [edits, setEdits] = useState<EditFields>({
    headline: "",
    recap: "",
    spotlight_player: "",
    spotlight_body: "",
    social_post: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function extractString(run: AgentRunRead, key: string): string {
    return run.output_payload
      ? String((run.output_payload[key] as string | undefined) ?? "")
      : "";
  }

  async function handleGenerate() {
    setError(null);
    setGenerating(true);
    try {
      const run = await gamesApi.generate(gameId);
      setPendingRun(run);
    } catch (err) {
      setError(apiErrorMsg(err, "Generation failed"));
    } finally {
      setGenerating(false);
    }
  }

  async function handleEvaluate() {
    if (!pendingRun) return;
    setError(null);
    setEvaluating(true);
    try {
      const updated = await agentRunsApi.evaluate(pendingRun.id);
      setPendingRun(updated);
    } catch (err) {
      setError(apiErrorMsg(err, "Evaluation failed"));
    } finally {
      setEvaluating(false);
    }
  }

  async function handleApprove() {
    if (!pendingRun) return;
    setError(null);
    setApproving(true);
    try {
      const content = await agentRunsApi.approve(pendingRun.id);
      onContentApproved(content);
      setPendingRun(null);
    } catch (err) {
      setError(apiErrorMsg(err, "Approval failed"));
    } finally {
      setApproving(false);
    }
  }

  async function handleReject() {
    if (!pendingRun) return;
    setError(null);
    setRejecting(true);
    try {
      await agentRunsApi.reject(pendingRun.id);
      setPendingRun(null);
    } catch (err) {
      setError(apiErrorMsg(err, "Rejection failed"));
    } finally {
      setRejecting(false);
    }
  }

  function handleEnterEditMode() {
    if (!pendingRun) return;
    setEdits({
      headline: extractString(pendingRun, "headline"),
      recap: extractString(pendingRun, "recap"),
      spotlight_player: extractString(pendingRun, "spotlight_player"),
      spotlight_body: extractString(pendingRun, "spotlight_body"),
      social_post: extractString(pendingRun, "social_post"),
    });
    setEditMode(true);
  }

  async function handleSaveEdits() {
    if (!pendingRun) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await agentRunsApi.updateOutput(pendingRun.id, edits);
      setPendingRun(updated);
      setEditMode(false);
    } catch (err) {
      setError(apiErrorMsg(err, "Save failed"));
    } finally {
      setSaving(false);
    }
  }

  const busy = generating || approving || rejecting || evaluating || saving;

  return (
    <section className="bg-white rounded-lg shadow-sm p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">AI Coverage</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Generated from the boxscore using Claude. Human approval required
            before publishing.
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={busy}
          className="bg-gray-900 hover:bg-gray-800 disabled:opacity-50 text-white font-medium px-4 py-2 rounded-md text-sm transition"
        >
          {generating
            ? "Generating…"
            : pendingRun || approvedContent
              ? "Regenerate"
              : "Generate Coverage"}
        </button>
      </div>

      {error && (
        <p className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
          {error}
        </p>
      )}

      {/* Pending agent run — awaiting human review */}
      {pendingRun && pendingRun.status === "succeeded" && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
            <span className="text-xs font-medium text-yellow-900">
              Pending review — run #{pendingRun.id}
            </span>
            {pendingRun.evaluations.length > 0 ? (
              pendingRun.evaluations.map((ev) => (
                <EvalChip
                  key={ev.id}
                  name={ev.metric_name}
                  passed={ev.passed}
                  score={ev.score}
                />
              ))
            ) : (
              <button
                onClick={handleEvaluate}
                disabled={evaluating}
                className="text-xs text-yellow-700 hover:text-yellow-900 underline disabled:opacity-50"
              >
                {evaluating ? "Evaluating…" : "Run eval checks"}
              </button>
            )}
            {!editMode && (
              <button
                onClick={handleEnterEditMode}
                disabled={busy}
                className="ml-auto text-xs text-yellow-700 hover:text-yellow-900 underline disabled:opacity-50"
              >
                Edit
              </button>
            )}
          </div>

          {editMode ? (
            <>
              <div>
                <Label>Headline</Label>
                <input
                  type="text"
                  value={edits.headline}
                  onChange={(e) => setEdits((p) => ({ ...p, headline: e.target.value }))}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-yellow-400"
                />
              </div>

              <div>
                <Label>Recap</Label>
                <textarea
                  rows={8}
                  value={edits.recap}
                  onChange={(e) => setEdits((p) => ({ ...p, recap: e.target.value }))}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-yellow-400 resize-y"
                />
              </div>

              <div>
                <Label>Spotlight Player</Label>
                <input
                  type="text"
                  value={edits.spotlight_player}
                  onChange={(e) =>
                    setEdits((p) => ({ ...p, spotlight_player: e.target.value }))
                  }
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-yellow-400"
                />
              </div>

              <div>
                <Label>Spotlight Body</Label>
                <textarea
                  rows={4}
                  value={edits.spotlight_body}
                  onChange={(e) =>
                    setEdits((p) => ({ ...p, spotlight_body: e.target.value }))
                  }
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-yellow-400 resize-y"
                />
              </div>

              <div>
                <Label>Social Post</Label>
                <textarea
                  rows={3}
                  value={edits.social_post}
                  onChange={(e) =>
                    setEdits((p) => ({ ...p, social_post: e.target.value }))
                  }
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 font-mono focus:outline-none focus:ring-2 focus:ring-yellow-400 resize-y"
                />
                <p className="text-xs text-gray-400 mt-1">{edits.social_post.length} chars</p>
              </div>
            </>
          ) : (
            <>
              {extractString(pendingRun, "headline") && (
                <div>
                  <Label>Headline</Label>
                  <p className="text-xl font-bold text-gray-900 leading-snug">
                    {extractString(pendingRun, "headline")}
                  </p>
                </div>
              )}

              <CopyableBlock label="Recap" text={extractString(pendingRun, "recap")}>
                {extractString(pendingRun, "recap")
                  .split(/\n\n+/)
                  .map((para, i) => (
                    <p key={i} className="text-gray-800 leading-relaxed mb-3 last:mb-0">
                      {para}
                    </p>
                  ))}
              </CopyableBlock>

              <CopyableBlock
                label={`Player Spotlight${
                  extractString(pendingRun, "spotlight_player")
                    ? ` — ${extractString(pendingRun, "spotlight_player")}`
                    : ""
                }`}
                text={extractString(pendingRun, "spotlight_body")}
              >
                <p className="text-gray-800 leading-relaxed">
                  {extractString(pendingRun, "spotlight_body")}
                </p>
              </CopyableBlock>

              <CopyableBlock
                label="Social Post"
                text={extractString(pendingRun, "social_post")}
              >
                <p className="text-gray-800 leading-relaxed font-mono text-sm bg-gray-50 rounded p-3 border border-gray-200">
                  {extractString(pendingRun, "social_post")}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  {extractString(pendingRun, "social_post").length} chars
                </p>
              </CopyableBlock>
            </>
          )}

          <div className="flex gap-3 pt-2 border-t border-gray-100">
            {editMode ? (
              <>
                <button
                  onClick={handleSaveEdits}
                  disabled={saving}
                  className="bg-gray-900 hover:bg-gray-800 disabled:opacity-50 text-white font-medium px-4 py-2 rounded-md text-sm transition"
                >
                  {saving ? "Saving…" : "Save changes"}
                </button>
                <button
                  onClick={() => setEditMode(false)}
                  disabled={saving}
                  className="border border-gray-300 hover:bg-gray-50 disabled:opacity-50 text-gray-700 font-medium px-4 py-2 rounded-md text-sm transition"
                >
                  Cancel
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={handleApprove}
                  disabled={busy || editMode}
                  className="bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white font-medium px-4 py-2 rounded-md text-sm transition"
                >
                  {approving ? "Approving…" : "Approve"}
                </button>
                <button
                  onClick={handleReject}
                  disabled={busy}
                  className="border border-gray-300 hover:bg-gray-50 disabled:opacity-50 text-gray-700 font-medium px-4 py-2 rounded-md text-sm transition"
                >
                  {rejecting ? "Rejecting…" : "Reject"}
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Failed run */}
      {pendingRun && pendingRun.status === "failed" && (
        <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
          Generation failed. Check agent run #{pendingRun.id} for details.
        </p>
      )}

      {/* Approved content */}
      {!pendingRun && approvedContent && (
        <div className="space-y-5">
          {approvedContent.headline && (
            <div>
              <Label>Headline</Label>
              <p className="text-xl font-bold text-gray-900 leading-snug">
                {approvedContent.headline}
              </p>
            </div>
          )}

          <CopyableBlock label="Recap" text={approvedContent.recap}>
            {approvedContent.recap.split(/\n\n+/).map((para, i) => (
              <p key={i} className="text-gray-800 leading-relaxed mb-3 last:mb-0">
                {para}
              </p>
            ))}
          </CopyableBlock>

          <CopyableBlock
            label={`Player Spotlight${
              approvedContent.spotlight_player
                ? ` — ${approvedContent.spotlight_player}`
                : ""
            }`}
            text={approvedContent.spotlight_body}
          >
            <p className="text-gray-800 leading-relaxed">
              {approvedContent.spotlight_body}
            </p>
          </CopyableBlock>

          <CopyableBlock label="Social Post" text={approvedContent.social_post}>
            <p className="text-gray-800 leading-relaxed font-mono text-sm bg-gray-50 rounded p-3 border border-gray-200">
              {approvedContent.social_post}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              {approvedContent.social_post.length} chars
            </p>
          </CopyableBlock>

          <p className="text-xs text-gray-400 pt-2 border-t border-gray-100">
            Approved · Generated{" "}
            {new Date(approvedContent.generated_at).toLocaleString()}
            {approvedContent.model && ` · ${approvedContent.model}`}
          </p>
        </div>
      )}

      {/* Nothing yet */}
      {!pendingRun && !approvedContent && !generating && !error && (
        <p className="text-sm text-gray-500">
          No coverage yet. Click the button to produce a headline, recap, player
          spotlight, and social post from this boxscore.
        </p>
      )}
    </section>
  );
}

function apiErrorMsg(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (
      typeof err.data === "object" &&
      err.data &&
      "detail" in err.data
    ) {
      return String(err.data.detail);
    }
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return fallback;
}

export default CoverageReviewPanel;
