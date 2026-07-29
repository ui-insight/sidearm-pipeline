import { useEffect, useMemo, useState, type FormEvent } from "react";
import { styleGuidesApi } from "../api/styleGuides";
import type {
  ResolvedStyleGuide,
  StyleGuideEnforcement,
  StyleGuideRule,
  StyleGuideScope,
  StyleGuideSeverity,
  StyleGuideVersion,
} from "../types/styleGuide";

type EditorMode = "new" | "successor";

interface RuleDraft {
  key: string;
  category: string;
  severity: StyleGuideSeverity;
  enforcement: StyleGuideEnforcement;
  value: string;
  override: boolean;
  description: string;
}

interface GuideDraft {
  guideKey: string;
  name: string;
  scopeType: StyleGuideScope;
  scopeValue: string;
  instructions: string;
  rules: RuleDraft[];
}

const emptyRule = (): RuleDraft => ({
  key: "",
  category: "tone",
  severity: "guidance",
  enforcement: "prompt_guidance",
  value: "",
  override: false,
  description: "",
});

const emptyGuide = (): GuideDraft => ({
  guideKey: "",
  name: "",
  scopeType: "shared_athletics",
  scopeValue: "",
  instructions: "",
  rules: [emptyRule()],
});

function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The Style Guide request could not be completed.";
}

function scopeLabel(scope: StyleGuideScope, value: string | null): string {
  const label = {
    shared_athletics: "Shared athletics",
    sport: "Sport",
    article_type: "Article type",
    channel: "Channel",
  }[scope];
  return value ? `${label}: ${value.replace(/_/g, " ")}` : label;
}

function stateClass(state: StyleGuideVersion["lifecycle_state"]): string {
  if (state === "active") return "bg-green-50 text-green-800 ring-green-200";
  if (state === "draft") return "bg-yellow-50 text-yellow-900 ring-yellow-200";
  return "bg-gray-100 text-gray-600 ring-gray-200";
}

function severityClass(severity: StyleGuideSeverity): string {
  if (severity === "error") return "bg-red-50 text-red-800 ring-red-200";
  if (severity === "warning") {
    return "bg-yellow-50 text-yellow-900 ring-yellow-200";
  }
  return "bg-blue-50 text-blue-800 ring-blue-200";
}

function formatDateTime(value: string | null): string {
  if (!value) return "Not yet";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function valueText(rule: StyleGuideRule): string {
  return Array.isArray(rule.value) ? rule.value.join("\n") : String(rule.value);
}

function draftFromVersion(version: StyleGuideVersion): GuideDraft {
  return {
    guideKey: version.guide_key,
    name: version.name,
    scopeType: version.scope_type,
    scopeValue: version.scope_value ?? "",
    instructions: version.instructions,
    rules: version.rules.map((rule) => ({
      key: rule.key,
      category: rule.category,
      severity: rule.severity,
      enforcement: rule.enforcement,
      value: valueText(rule),
      override: rule.override,
      description: rule.description ?? "",
    })),
  };
}

function parsedRule(rule: RuleDraft): StyleGuideRule {
  let value: string | number | string[] = rule.value.trim();
  if (
    rule.enforcement === "headline_max_chars" ||
    rule.enforcement === "body_max_chars"
  ) {
    value = Number(rule.value);
  } else if (
    rule.enforcement === "required_terms" ||
    rule.enforcement === "forbidden_terms" ||
    rule.enforcement === "forbidden_fact_classes"
  ) {
    value = rule.value
      .split("\n")
      .map((term) => term.trim())
      .filter(Boolean);
  }
  return {
    key: rule.key.trim(),
    category: rule.category.trim(),
    severity: rule.severity,
    enforcement: rule.enforcement,
    value,
    override: rule.override,
    description: rule.description.trim() || null,
  };
}

function StyleGuidesPage() {
  const [guides, setGuides] = useState<StyleGuideVersion[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [actionPending, setActionPending] = useState(false);
  const [editorMode, setEditorMode] = useState<EditorMode | null>(null);
  const [draft, setDraft] = useState<GuideDraft>(emptyGuide);
  const [formError, setFormError] = useState<string | null>(null);
  const [retireConfirm, setRetireConfirm] = useState(false);
  const [preview, setPreview] = useState<ResolvedStyleGuide | null>(null);
  const [previewPending, setPreviewPending] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewSport, setPreviewSport] = useState("womens-basketball");
  const [previewArticleType, setPreviewArticleType] = useState<
    "game_recap" | "player_spotlight" | "achievement_story"
  >("game_recap");
  const [previewChannel, setPreviewChannel] = useState("");
  const [includeCandidate, setIncludeCandidate] = useState(true);

  const selected = useMemo(
    () => guides.find((guide) => guide.id === selectedId) ?? null,
    [guides, selectedId],
  );

  const lineageLatest = useMemo(() => {
    if (!selected) return false;
    return !guides.some(
      (guide) =>
        guide.guide_key === selected.guide_key &&
        guide.version > selected.version,
    );
  }, [guides, selected]);

  async function loadGuides(preferredId?: number) {
    const result = await styleGuidesApi.list();
    setGuides(result);
    setSelectedId((current) => {
      const requested = preferredId ?? current;
      return result.some((guide) => guide.id === requested)
        ? requested
        : (result[0]?.id ?? null);
    });
  }

  useEffect(() => {
    let active = true;
    styleGuidesApi
      .list()
      .then((result) => {
        if (!active) return;
        setGuides(result);
        setSelectedId(result[0]?.id ?? null);
      })
      .catch((error: unknown) => {
        if (active) setPageError(errorMessage(error));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function openNewGuide() {
    setDraft(emptyGuide());
    setEditorMode("new");
    setFormError(null);
    setNotice(null);
  }

  function openSuccessor() {
    if (!selected) return;
    setDraft(draftFromVersion(selected));
    setEditorMode("successor");
    setFormError(null);
    setNotice(null);
  }

  function updateRule(index: number, patch: Partial<RuleDraft>) {
    setDraft((current) => ({
      ...current,
      rules: current.rules.map((rule, ruleIndex) =>
        ruleIndex === index ? { ...rule, ...patch } : rule,
      ),
    }));
  }

  async function submitGuide(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.name.trim() || !draft.instructions.trim()) {
      setFormError("Name and writer instructions are required.");
      return;
    }
    if (editorMode === "new" && !draft.guideKey.trim()) {
      setFormError("A stable guide key is required.");
      return;
    }
    if (draft.scopeType !== "shared_athletics" && !draft.scopeValue.trim()) {
      setFormError("The selected scope requires a value.");
      return;
    }
    if (draft.rules.some((rule) => !rule.key.trim() || !rule.value.trim())) {
      setFormError("Every rule needs a stable key and value.");
      return;
    }

    setActionPending(true);
    setFormError(null);
    try {
      const content = {
        name: draft.name.trim(),
        instructions: draft.instructions.trim(),
        rules: draft.rules.map(parsedRule),
      };
      const created =
        editorMode === "successor" && selected
          ? await styleGuidesApi.createSuccessor(selected.id, content)
          : await styleGuidesApi.create({
              ...content,
              guide_key: draft.guideKey.trim(),
              scope_type: draft.scopeType,
              scope_value:
                draft.scopeType === "shared_athletics"
                  ? null
                  : draft.scopeValue.trim(),
            });
      await loadGuides(created.id);
      setEditorMode(null);
      setNotice(
        `${created.name} v${created.version} is saved as an immutable draft.`,
      );
    } catch (error: unknown) {
      setFormError(errorMessage(error));
    } finally {
      setActionPending(false);
    }
  }

  async function activateSelected() {
    if (!selected) return;
    setActionPending(true);
    setPageError(null);
    try {
      const activated = await styleGuidesApi.activate(selected.id);
      await loadGuides(activated.id);
      setNotice(
        `${activated.name} v${activated.version} is active. Its prior active version was retired.`,
      );
    } catch (error: unknown) {
      setPageError(errorMessage(error));
    } finally {
      setActionPending(false);
    }
  }

  async function retireSelected() {
    if (!selected) return;
    setActionPending(true);
    setPageError(null);
    try {
      const retired = await styleGuidesApi.retire(selected.id);
      await loadGuides(retired.id);
      setNotice(`${retired.name} v${retired.version} is retired.`);
      setRetireConfirm(false);
    } catch (error: unknown) {
      setPageError(errorMessage(error));
    } finally {
      setActionPending(false);
    }
  }

  async function runPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPreviewPending(true);
    setPreviewError(null);
    try {
      setPreview(
        await styleGuidesApi.preview({
          sport: previewSport.trim() || null,
          article_type: previewArticleType,
          channel: previewChannel.trim() || null,
          candidate_version_id:
            includeCandidate && selected?.lifecycle_state === "draft"
              ? selected.id
              : null,
        }),
      );
    } catch (error: unknown) {
      setPreviewError(errorMessage(error));
    } finally {
      setPreviewPending(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="animate-pulse" aria-label="Loading Style Guides">
          <div className="h-8 w-72 bg-gray-200" />
          <div className="mt-7 h-80 border-y border-gray-200 bg-white" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <header className="flex flex-col gap-5 border-b border-gray-300 pb-7 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-yellow-700">
            Editorial governance
          </p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-gray-950">
            Athletics Style Guides
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-gray-600">
            Review immutable policy versions, test the exact resolved rule set, and
            control when approved guidance takes effect.
          </p>
        </div>
        <button
          type="button"
          onClick={openNewGuide}
          className="inline-flex w-fit items-center rounded-md bg-gray-950 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
        >
          New scoped guide
        </button>
      </header>

      {notice ? (
        <p
          role="status"
          className="mt-5 border border-green-200 bg-green-50 px-4 py-3 text-sm font-medium text-green-800"
        >
          {notice}
        </p>
      ) : null}
      {pageError ? (
        <p
          role="alert"
          className="mt-5 border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-800"
        >
          {pageError}
        </p>
      ) : null}

      {editorMode ? (
        <form
          onSubmit={(event) => void submitGuide(event)}
          className="mt-7 border-y border-gray-300 bg-white py-6"
        >
          <div className="flex flex-wrap items-start justify-between gap-4 px-4 sm:px-6">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.1em] text-gray-500">
                {editorMode === "new" ? "New lineage" : "Immutable successor"}
              </p>
              <h2 className="mt-1 text-xl font-black text-gray-950">
                {editorMode === "new"
                  ? "Author a scoped guide"
                  : `Create v${(selected?.version ?? 0) + 1}`}
              </h2>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-gray-600">
                Saving creates a fixed draft. Changes after review require another
                successor version.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setEditorMode(null)}
              className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold text-gray-700 hover:border-gray-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
            >
              Cancel
            </button>
          </div>

          <div className="mt-6 grid gap-5 px-4 sm:grid-cols-2 sm:px-6 lg:grid-cols-4">
            <label className="text-sm font-semibold text-gray-800">
              Stable guide key
              <input
                value={draft.guideKey}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    guideKey: event.target.value,
                  }))
                }
                disabled={editorMode === "successor"}
                required
                pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
                className="mt-2 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 font-mono text-sm font-normal text-gray-950 focus:border-gray-950 focus:outline-2 focus:outline-offset-2 focus:outline-yellow-500 disabled:bg-gray-100 disabled:text-gray-500"
              />
            </label>
            <label className="text-sm font-semibold text-gray-800 sm:col-span-2">
              Guide name
              <input
                value={draft.name}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, name: event.target.value }))
                }
                required
                className="mt-2 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal text-gray-950 focus:border-gray-950 focus:outline-2 focus:outline-offset-2 focus:outline-yellow-500"
              />
            </label>
            <label className="text-sm font-semibold text-gray-800">
              Scope
              <select
                value={draft.scopeType}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    scopeType: event.target.value as StyleGuideScope,
                    scopeValue:
                      event.target.value === "shared_athletics"
                        ? ""
                        : current.scopeValue,
                  }))
                }
                disabled={editorMode === "successor"}
                className="mt-2 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal text-gray-950 focus:border-gray-950 focus:outline-2 focus:outline-offset-2 focus:outline-yellow-500 disabled:bg-gray-100"
              >
                <option value="shared_athletics">Shared athletics</option>
                <option value="sport">Sport</option>
                <option value="article_type">Article type</option>
                <option value="channel">Channel</option>
              </select>
            </label>
            {draft.scopeType !== "shared_athletics" ? (
              <label className="text-sm font-semibold text-gray-800 sm:col-span-2">
                Scope value
                {draft.scopeType === "article_type" ? (
                  <select
                    value={draft.scopeValue}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        scopeValue: event.target.value,
                      }))
                    }
                    disabled={editorMode === "successor"}
                    required
                    className="mt-2 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal text-gray-950 focus:border-gray-950 focus:outline-2 focus:outline-offset-2 focus:outline-yellow-500 disabled:bg-gray-100"
                  >
                    <option value="">Choose an article type</option>
                    <option value="game_recap">Game recap</option>
                    <option value="player_spotlight">Player spotlight</option>
                    <option value="achievement_story">Achievement story</option>
                  </select>
                ) : (
                  <input
                    value={draft.scopeValue}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        scopeValue: event.target.value,
                      }))
                    }
                    disabled={editorMode === "successor"}
                    required
                    placeholder={
                      draft.scopeType === "sport" ? "womens-basketball" : "website"
                    }
                    className="mt-2 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 font-mono text-sm font-normal text-gray-950 focus:border-gray-950 focus:outline-2 focus:outline-offset-2 focus:outline-yellow-500 disabled:bg-gray-100"
                  />
                )}
              </label>
            ) : null}
            <label className="text-sm font-semibold text-gray-800 sm:col-span-2 lg:col-span-4">
              Writer instructions
              <textarea
                value={draft.instructions}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    instructions: event.target.value,
                  }))
                }
                required
                rows={4}
                className="mt-2 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal leading-6 text-gray-950 focus:border-gray-950 focus:outline-2 focus:outline-offset-2 focus:outline-yellow-500"
              />
            </label>
          </div>

          <div className="mt-7 border-t border-gray-200 px-4 pt-6 sm:px-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-black text-gray-950">Rules</h3>
                <p className="mt-1 text-sm text-gray-600">
                  One value per line for terminology lists. Overrides must be
                  explicit when a more specific scope replaces a stable key.
                </p>
              </div>
              <button
                type="button"
                onClick={() =>
                  setDraft((current) => ({
                    ...current,
                    rules: [...current.rules, emptyRule()],
                  }))
                }
                className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold text-gray-700 hover:border-gray-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
              >
                Add rule
              </button>
            </div>
            <div className="mt-4 divide-y divide-gray-200 border-y border-gray-200">
              {draft.rules.map((rule, index) => (
                <fieldset key={index} className="grid gap-4 py-5 md:grid-cols-2 lg:grid-cols-4">
                  <legend className="sr-only">Rule {index + 1}</legend>
                  <label className="text-xs font-bold uppercase tracking-wide text-gray-600">
                    Stable key
                    <input
                      value={rule.key}
                      onChange={(event) => updateRule(index, { key: event.target.value })}
                      required
                      className="mt-2 block w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-sm font-normal normal-case tracking-normal text-gray-950 focus:border-gray-950 focus:outline-2 focus:outline-offset-2 focus:outline-yellow-500"
                    />
                  </label>
                  <label className="text-xs font-bold uppercase tracking-wide text-gray-600">
                    Category
                    <input
                      value={rule.category}
                      onChange={(event) =>
                        updateRule(index, { category: event.target.value })
                      }
                      required
                      className="mt-2 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-normal normal-case tracking-normal text-gray-950 focus:border-gray-950 focus:outline-2 focus:outline-offset-2 focus:outline-yellow-500"
                    />
                  </label>
                  <label className="text-xs font-bold uppercase tracking-wide text-gray-600">
                    Severity
                    <select
                      value={rule.severity}
                      onChange={(event) =>
                        updateRule(index, {
                          severity: event.target.value as StyleGuideSeverity,
                        })
                      }
                      className="mt-2 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-gray-950 focus:border-gray-950 focus:outline-2 focus:outline-offset-2 focus:outline-yellow-500"
                    >
                      <option value="error">Error</option>
                      <option value="warning">Warning</option>
                      <option value="guidance">Guidance</option>
                    </select>
                  </label>
                  <label className="text-xs font-bold uppercase tracking-wide text-gray-600">
                    Enforcement
                    <select
                      value={rule.enforcement}
                      onChange={(event) => {
                        const enforcement = event.target.value as StyleGuideEnforcement;
                        updateRule(index, {
                          enforcement,
                          severity:
                            enforcement === "prompt_guidance"
                              ? "guidance"
                              : rule.severity,
                          value:
                            enforcement === "deterministic_lint"
                              ? "no_exclamation"
                              : rule.value,
                        });
                      }}
                      className="mt-2 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-gray-950 focus:border-gray-950 focus:outline-2 focus:outline-offset-2 focus:outline-yellow-500"
                    >
                      <option value="prompt_guidance">Prompt guidance</option>
                      <option value="deterministic_lint">Deterministic lint</option>
                      <option value="required_terms">Required terminology</option>
                      <option value="forbidden_terms">Forbidden terminology</option>
                      <option value="headline_max_chars">Headline max length</option>
                      <option value="body_max_chars">Body max length</option>
                      <option value="forbidden_fact_classes">Forbidden fact classes</option>
                    </select>
                  </label>
                  <label className="text-xs font-bold uppercase tracking-wide text-gray-600 md:col-span-2 lg:col-span-3">
                    Value
                    {rule.enforcement === "deterministic_lint" ? (
                      <select
                        value={rule.value}
                        onChange={(event) =>
                          updateRule(index, { value: event.target.value })
                        }
                        className="mt-2 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-gray-950 focus:border-gray-950 focus:outline-2 focus:outline-offset-2 focus:outline-yellow-500"
                      >
                        <option value="no_exclamation">No exclamation marks</option>
                        <option value="no_all_caps">No all-caps words</option>
                        <option value="no_double_space">No double spaces</option>
                      </select>
                    ) : (
                      <textarea
                        value={rule.value}
                        onChange={(event) =>
                          updateRule(index, { value: event.target.value })
                        }
                        required
                        rows={2}
                        className="mt-2 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-normal normal-case tracking-normal text-gray-950 focus:border-gray-950 focus:outline-2 focus:outline-offset-2 focus:outline-yellow-500"
                      />
                    )}
                  </label>
                  <div className="flex items-end justify-between gap-3">
                    <label className="flex items-center gap-2 pb-2 text-sm font-semibold text-gray-700">
                      <input
                        type="checkbox"
                        checked={rule.override}
                        onChange={(event) =>
                          updateRule(index, { override: event.target.checked })
                        }
                        className="size-4 accent-yellow-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
                      />
                      Explicit override
                    </label>
                    {draft.rules.length > 1 ? (
                      <button
                        type="button"
                        onClick={() =>
                          setDraft((current) => ({
                            ...current,
                            rules: current.rules.filter(
                              (_candidate, ruleIndex) => ruleIndex !== index,
                            ),
                          }))
                        }
                        className="pb-2 text-sm font-semibold text-red-700 underline decoration-red-200 underline-offset-4 hover:decoration-red-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
                      >
                        Remove
                      </button>
                    ) : null}
                  </div>
                </fieldset>
              ))}
            </div>
          </div>

          {formError ? (
            <p role="alert" className="mx-4 mt-5 text-sm font-semibold text-red-700 sm:mx-6">
              {formError}
            </p>
          ) : null}
          <div className="mt-5 flex justify-end px-4 sm:px-6">
            <button
              type="submit"
              disabled={actionPending}
              className="rounded-md bg-yellow-400 px-4 py-2.5 text-sm font-black text-gray-950 transition-colors hover:bg-yellow-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-wait disabled:bg-gray-200 disabled:text-gray-500"
            >
              {actionPending ? "Saving…" : "Save immutable draft"}
            </button>
          </div>
        </form>
      ) : null}

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(18rem,0.8fr)_minmax(0,1.7fr)]">
        <aside aria-label="Style Guide version history" className="self-start border-y border-gray-300 bg-white lg:sticky lg:top-4">
          <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-3">
            <h2 className="text-xs font-black uppercase tracking-[0.08em] text-gray-600">
              Version history
            </h2>
            <span className="font-mono text-xs tabular-nums text-gray-500">
              {guides.length}
            </span>
          </div>
          {guides.length === 0 ? (
            <p className="px-4 py-8 text-sm leading-6 text-gray-600">
              No Style Guides have been seeded. Run the warehouse reference seed
              before authoring custom policy.
            </p>
          ) : (
            <div className="divide-y divide-gray-200">
              {guides.map((guide) => (
                <button
                  key={guide.id}
                  type="button"
                  onClick={() => {
                    setSelectedId(guide.id);
                    setPreview(null);
                    setRetireConfirm(false);
                  }}
                  aria-pressed={guide.id === selectedId}
                  className={`block w-full px-4 py-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-yellow-500 ${
                    guide.id === selectedId
                      ? "bg-yellow-50"
                      : "bg-white hover:bg-gray-50"
                  }`}
                >
                  <span className="flex items-start justify-between gap-3">
                    <span>
                      <span className="block text-sm font-black text-gray-950">
                        {guide.name}
                      </span>
                      <span className="mt-1 block text-xs text-gray-500">
                        {scopeLabel(guide.scope_type, guide.scope_value)}
                      </span>
                    </span>
                    <span className="font-mono text-xs font-bold tabular-nums text-gray-700">
                      v{guide.version}
                    </span>
                  </span>
                  <span className="mt-3 flex items-center justify-between gap-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-bold capitalize ring-1 ring-inset ${stateClass(guide.lifecycle_state)}`}
                    >
                      {guide.lifecycle_state}
                    </span>
                    <span className="truncate text-[11px] text-gray-500">
                      {guide.created_by}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          )}
        </aside>

        <div className="min-w-0 space-y-8">
          {selected ? (
            <section aria-labelledby="selected-guide-heading" className="border-y border-gray-300 bg-white">
              <div className="flex flex-col gap-4 border-b border-gray-200 px-5 py-5 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold capitalize ring-1 ring-inset ${stateClass(selected.lifecycle_state)}`}
                    >
                      {selected.lifecycle_state}
                    </span>
                    <span className="font-mono text-xs font-bold tabular-nums text-gray-500">
                      {selected.guide_key} / v{selected.version}
                    </span>
                  </div>
                  <h2 id="selected-guide-heading" className="mt-3 text-2xl font-black tracking-tight text-gray-950">
                    {selected.name}
                  </h2>
                  <p className="mt-1 text-sm font-semibold text-gray-600">
                    {scopeLabel(selected.scope_type, selected.scope_value)}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {lineageLatest ? (
                    <button
                      type="button"
                      onClick={openSuccessor}
                      className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold text-gray-700 hover:border-gray-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
                    >
                      Create successor
                    </button>
                  ) : null}
                  {selected.lifecycle_state === "draft" ? (
                    <button
                      type="button"
                      onClick={() => void activateSelected()}
                      disabled={actionPending}
                      className="rounded-md bg-gray-950 px-3 py-2 text-sm font-bold text-white hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-wait disabled:bg-gray-400"
                    >
                      {actionPending ? "Activating…" : "Activate version"}
                    </button>
                  ) : null}
                  {selected.lifecycle_state === "active" && !retireConfirm ? (
                    <button
                      type="button"
                      onClick={() => setRetireConfirm(true)}
                      className="rounded-md border border-red-300 bg-white px-3 py-2 text-sm font-semibold text-red-700 hover:border-red-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
                    >
                      Retire version
                    </button>
                  ) : null}
                </div>
              </div>

              {retireConfirm ? (
                <div className="flex flex-col gap-3 border-b border-red-200 bg-red-50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm font-semibold text-red-800">
                    Retire this version? Existing Article snapshots remain unchanged.
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setRetireConfirm(false)}
                      className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold text-gray-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
                    >
                      Keep active
                    </button>
                    <button
                      type="button"
                      onClick={() => void retireSelected()}
                      disabled={actionPending}
                      className="rounded-md bg-red-700 px-3 py-2 text-sm font-bold text-white hover:bg-red-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-wait disabled:bg-red-300"
                    >
                      Confirm retirement
                    </button>
                  </div>
                </div>
              ) : null}

              <dl className="grid gap-px bg-gray-200 sm:grid-cols-2 xl:grid-cols-4">
                {[
                  ["Authored", `${selected.created_by}, ${formatDateTime(selected.created_at)}`],
                  ["Effective", formatDateTime(selected.effective_at)],
                  ["Activated by", selected.activated_by ?? "Not yet"],
                  ["Content hash", selected.content_hash.slice(0, 12)],
                ].map(([label, value]) => (
                  <div key={label} className="bg-gray-50 px-4 py-3">
                    <dt className="text-[11px] font-bold uppercase tracking-[0.08em] text-gray-500">
                      {label}
                    </dt>
                    <dd className="mt-1 truncate text-sm font-semibold text-gray-800">
                      {value}
                    </dd>
                  </div>
                ))}
              </dl>

              <div className="px-5 py-5">
                <h3 className="text-xs font-black uppercase tracking-[0.08em] text-gray-500">
                  Writer instructions
                </h3>
                <p className="mt-2 max-w-3xl whitespace-pre-wrap text-sm leading-6 text-gray-800">
                  {selected.instructions}
                </p>
              </div>

              <div className="overflow-x-auto border-t border-gray-200">
                <table className="min-w-full text-left text-sm">
                  <caption className="sr-only">Rules in {selected.name}</caption>
                  <thead className="bg-gray-50 text-xs font-bold uppercase tracking-[0.06em] text-gray-500">
                    <tr>
                      <th scope="col" className="px-4 py-3">Rule</th>
                      <th scope="col" className="px-4 py-3">Severity</th>
                      <th scope="col" className="px-4 py-3">Enforcement</th>
                      <th scope="col" className="px-4 py-3">Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {selected.rules.map((rule) => (
                      <tr key={rule.key} className="align-top">
                        <td className="px-4 py-3">
                          <span className="font-mono text-xs font-bold text-gray-950">
                            {rule.key}
                          </span>
                          <span className="mt-1 block text-xs text-gray-500">
                            {rule.category}{rule.override ? ", explicit override" : ""}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-bold capitalize ring-1 ring-inset ${severityClass(rule.severity)}`}>
                            {rule.severity}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs font-semibold text-gray-700">
                          {rule.enforcement.replace(/_/g, " ")}
                        </td>
                        <td className="max-w-sm px-4 py-3 text-xs leading-5 text-gray-700">
                          {Array.isArray(rule.value)
                            ? rule.value.join(", ")
                            : String(rule.value)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}

          <section aria-labelledby="preview-heading" className="border-y border-gray-300 bg-white">
            <div className="border-b border-gray-200 px-5 py-5">
              <p className="text-xs font-bold uppercase tracking-[0.1em] text-gray-500">
                Resolution check
              </p>
              <h2 id="preview-heading" className="mt-1 text-xl font-black text-gray-950">
                Preview the effective guide
              </h2>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-gray-600">
                Rules resolve in order: shared athletics, sport, article type, then
                channel. Draft candidates can be tested before activation.
              </p>
            </div>
            <form
              onSubmit={(event) => void runPreview(event)}
              className="grid gap-4 bg-gray-50 px-5 py-5 sm:grid-cols-2 xl:grid-cols-4"
            >
              <label className="text-xs font-bold uppercase tracking-wide text-gray-600">
                Sport
                <input
                  value={previewSport}
                  onChange={(event) => setPreviewSport(event.target.value)}
                  placeholder="womens-basketball"
                  className="mt-2 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 font-mono text-sm font-normal normal-case tracking-normal text-gray-950 focus:border-gray-950 focus:outline-2 focus:outline-offset-2 focus:outline-yellow-500"
                />
              </label>
              <label className="text-xs font-bold uppercase tracking-wide text-gray-600">
                Article type
                <select
                  value={previewArticleType}
                  onChange={(event) =>
                    setPreviewArticleType(
                      event.target.value as typeof previewArticleType,
                    )
                  }
                  className="mt-2 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-gray-950 focus:border-gray-950 focus:outline-2 focus:outline-offset-2 focus:outline-yellow-500"
                >
                  <option value="game_recap">Game recap</option>
                  <option value="player_spotlight">Player spotlight</option>
                  <option value="achievement_story">Achievement story</option>
                </select>
              </label>
              <label className="text-xs font-bold uppercase tracking-wide text-gray-600">
                Channel, optional
                <input
                  value={previewChannel}
                  onChange={(event) => setPreviewChannel(event.target.value)}
                  placeholder="website"
                  className="mt-2 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 font-mono text-sm font-normal normal-case tracking-normal text-gray-950 focus:border-gray-950 focus:outline-2 focus:outline-offset-2 focus:outline-yellow-500"
                />
              </label>
              <div className="flex flex-col justify-end gap-3">
                {selected?.lifecycle_state === "draft" ? (
                  <label className="flex items-center gap-2 text-xs font-semibold text-gray-700">
                    <input
                      type="checkbox"
                      checked={includeCandidate}
                      onChange={(event) => setIncludeCandidate(event.target.checked)}
                      className="size-4 accent-yellow-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
                    />
                    Include selected draft v{selected.version}
                  </label>
                ) : null}
                <button
                  type="submit"
                  disabled={previewPending}
                  className="rounded-md bg-gray-950 px-4 py-2.5 text-sm font-bold text-white hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-wait disabled:bg-gray-400"
                >
                  {previewPending ? "Resolving…" : "Resolve preview"}
                </button>
              </div>
            </form>

            {previewError ? (
              <p role="alert" className="border-t border-red-200 bg-red-50 px-5 py-4 text-sm font-semibold text-red-800">
                {previewError}
              </p>
            ) : null}
            {preview ? (
              <div className="border-t border-gray-200">
                <div className="flex flex-col gap-3 px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-black text-gray-950">
                      {preview.valid_for_activation
                        ? "Resolution is valid"
                        : "Resolution needs correction"}
                    </p>
                    <p className="mt-1 font-mono text-xs text-gray-500">
                      Snapshot {preview.style_hash.slice(0, 16)} · {preview.versions.length} versions · {preview.rules.length} rules
                    </p>
                  </div>
                  <span className={`inline-flex w-fit rounded-full px-2.5 py-1 text-xs font-bold ring-1 ring-inset ${
                    preview.valid_for_activation
                      ? "bg-green-50 text-green-800 ring-green-200"
                      : "bg-red-50 text-red-800 ring-red-200"
                  }`}>
                    {preview.valid_for_activation ? "Ready to activate" : "Conflicts found"}
                  </span>
                </div>
                {preview.issues.length ? (
                  <ul className="divide-y divide-red-200 border-y border-red-200 bg-red-50 px-5 text-sm text-red-800">
                    {preview.issues.map((issue, index) => (
                      <li key={`${issue.code}-${index}`} className="py-3">
                        <span className="font-bold">{issue.code.replace(/_/g, " ")}:</span>{" "}
                        {issue.message}
                      </li>
                    ))}
                  </ul>
                ) : null}
                <ol className="divide-y divide-gray-200 px-5">
                  {preview.versions.map((version, index) => (
                    <li key={version.id} className="flex items-center gap-4 py-3 text-sm">
                      <span className="grid size-7 shrink-0 place-items-center rounded-full bg-gray-950 font-mono text-xs font-black text-white">
                        {index + 1}
                      </span>
                      <span>
                        <span className="font-bold text-gray-950">{version.name} v{version.version}</span>
                        <span className="ml-2 text-xs text-gray-500">
                          {scopeLabel(version.scope_type, version.scope_value)}
                        </span>
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  );
}

export default StyleGuidesPage;
