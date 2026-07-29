import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ArticleBriefPage from "../src/pages/ArticleBriefPage";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), { ...init, headers });
}

const brief = {
  id: 401,
  status: "brief",
  article_type: "achievement_story",
  angle: "Lead with the verified career high.",
  audience: "Vandal fans",
  constraints: "Keep the opening concise.",
  created_by: "sid-user",
  created_at: "2026-07-27T18:00:00Z",
  game: {
    id: 61,
    canonical_uid: "sidearm:womens-basketball:61",
    sport: "womens-basketball",
    season: "2025-26",
    game_date: "2025-12-01",
    title: "Idaho at Montana State",
    home_team: "Montana State",
    away_team: "Idaho",
    home_score: 66,
    away_score: 72,
    source_url: "https://govandals.com/boxscore/61",
  },
  evidence_bundle: {
    id: 700,
    version: 1,
    schema_version: "article-evidence-bundle-v1",
    content_hash: "a".repeat(64),
    created_by: "sid-user",
    created_at: "2026-07-27T18:00:00Z",
    suggestions: [
      {
        evidence_item_id: "achievement-suggestion:17",
        id: 17,
        suggestion_key: "career_high:9:points",
        player_id: 9,
        player_name: "Avery Adams",
        stat_definition_id: 2,
        notability_policy_id: 3,
        notability_policy_version: 1,
        stat_key: "points",
        stat_label: "Points",
        achievement_type: "career_high",
        scope: "career",
        computed_value: "31.000000",
        comparison_value: "27.000000",
        rank: null,
        phrasing:
          "Avery Adams set a career high with 31 points since 2023-24.",
        context: {},
        source: {
          snapshot_id: 80,
          source_system: "sidearm",
          source_type: "boxscore_html",
          source_url: "https://govandals.com/boxscore/61",
          content_hash: "source-hash",
          fetched_at: "2026-07-27T15:00:00Z",
        },
        coverage_window: {
          id: 5,
          grain: "game",
          first_season: "2023-24",
          last_season: "2025-26",
          completeness: "partial",
          known_limitations: "Earlier seasons are not available.",
          claim_scope: "since 2023-24",
        },
        verdict: {
          state: "approved",
          reviewed_at: "2026-07-27T17:00:00Z",
          reviewed_by: "sid-user",
        },
        fact_hash: "fact-hash",
      },
    ],
  },
};

const articleVersion = {
  id: 900,
  article_id: 401,
  version: 1,
  origin: "ai",
  parent_version_id: null,
  headline: "Avery Adams reaches 31 points since 2023-24",
  headline_evidence_ids: ["achievement-suggestion:17"],
  body: "Avery Adams set a career high with 31 points since 2023-24.",
  blocks: [
    {
      kind: "lead",
      text: "Avery Adams set a career high with 31 points since 2023-24.",
      evidence_ids: ["achievement-suggestion:17"],
    },
  ],
  evidence_bundle_id: 700,
  evidence_hash: "a".repeat(64),
  style_guide_version_id: 5,
  style_snapshot: {},
  style_hash: "b".repeat(64),
  prompt_version: "article-writer-v1",
  editor_instructions: null,
  provider: "anthropic-messages",
  model: "test-model",
  output_hash: "c".repeat(64),
  validation_results: [],
  author: null,
  created_at: "2026-07-28T18:00:00Z",
  warning_overrides: [],
};

const humanVersion = {
  ...articleVersion,
  id: 901,
  version: 2,
  origin: "human",
  parent_version_id: 900,
  headline: "Avery Adams records 31 points since 2023-24",
  author: "sid-user",
  provider: null,
  model: null,
  prompt_version: null,
  output_hash: "f".repeat(64),
  created_at: "2026-07-28T18:05:00Z",
};

const queuedJob = {
  id: 800,
  article_id: 401,
  state: "queued",
  requested_by: "sid-user",
  attempt_count: 0,
  evidence_bundle_id: 700,
  style_guide_version_id: 5,
  style_snapshot: {
    versions: [
      {
        id: 5,
        guide_key: "athletics-default",
        version: 1,
        name: "Vandals Athletics seed guide",
        scope_type: "shared_athletics",
        scope_value: null,
        content_hash: "d".repeat(64),
      },
    ],
  },
  style_hash: "b".repeat(64),
  provider: "anthropic-messages",
  model: "test-model",
  prompt_version: "article-writer-v1",
  input_hash: "e".repeat(64),
  output_hash: null,
  validation_results: [],
  error_code: null,
  error_message: null,
  created_at: "2026-07-28T18:00:00Z",
  started_at: null,
  completed_at: null,
  article_version: null,
};

const activeRevalidation = {
  id: 77,
  article_id: 401,
  previous_evidence_bundle_id: 700,
  refreshed_evidence_bundle_id: null,
  change_hash: "9".repeat(64),
  detected_at: "2026-07-29T16:00:00Z",
  resolved_at: null,
  resolved_by: null,
  changes: [
    {
      change_type: "fact_changed",
      suggestion_key: "career_high:9:points",
      label: "The verified achievement fact changed.",
      previous_value: {
        player_name: "Avery Adams",
        computed_value: "31.000000",
        stat_label: "Points",
      },
      current_value: {
        player_name: "Avery Adams",
        computed_value: "36.000000",
        stat_label: "Points",
      },
    },
    {
      change_type: "approval_changed",
      suggestion_key: "career_high:9:points",
      label: "The current evidence no longer has a valid SID approval.",
      previous_value: "approved",
      current_value: "pending",
    },
  ],
};

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(jsonResponse(brief));
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("localStorage", {
    getItem: vi.fn(() => null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ArticleBriefPage", () => {
  it("shows editorial intent, frozen evidence, and audit metadata", async () => {
    render(
      <MemoryRouter initialEntries={["/articles/401"]}>
        <Routes>
          <Route path="/articles/:id" element={<ArticleBriefPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Lead with the verified career high." }),
    ).toBeInTheDocument();
    expect(screen.getByText(brief.evidence_bundle.suggestions[0].phrasing)).toBeInTheDocument();
    expect(screen.getByText("since 2023-24")).toBeInTheDocument();
    expect(screen.getByText(/Earlier seasons are not available/)).toBeInTheDocument();
    expect(screen.getByText(/Created by sid-user/)).toBeInTheDocument();
    expect(screen.getByText(/Evidence bundle v1/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Inspect source snapshot" })).toHaveAttribute(
      "href",
      "https://govandals.com/boxscore/61",
    );
  });

  it("queues a durable evidence-bound draft from the brief", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(brief))
      .mockResolvedValueOnce(jsonResponse(queuedJob, { status: 202 }));
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/articles/401"]}>
        <Routes>
          <Route path="/articles/:id" element={<ArticleBriefPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(
      await screen.findByRole("button", { name: "Generate draft" }),
    );

    expect(await screen.findByText("Draft queued")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/articles/401/generation-jobs",
      expect.objectContaining({ method: "POST" }),
    );
    const request = fetchMock.mock.calls[1][1];
    expect(JSON.parse(String(request?.body))).toMatchObject({
      idempotency_key: expect.stringContaining("article-draft-401-"),
    });
  });

  it("shows the validated immutable AI draft and its evidence references", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ...brief,
        status: "in_edit",
        latest_version: articleVersion,
      }),
    );
    render(
      <MemoryRouter initialEntries={["/articles/401"]}>
        <Routes>
          <Route path="/articles/:id" element={<ArticleBriefPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: articleVersion.headline }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("Evidence: achievement-suggestion:17"),
    ).toHaveLength(2);
    expect(screen.getByText(/Draft validated/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Generate draft" })).not.toBeInTheDocument();
  });

  it("keeps a failed brief retryable and shows deterministic findings", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ...brief,
        latest_generation_job: {
          ...queuedJob,
          state: "failed",
          error_code: "validation_failed",
          error_message: "The generated draft failed validation.",
          validation_results: [
            {
              code: "unsupported_numeral",
              severity: "error",
              message: "Unsupported numeral: 99.",
              block_index: 0,
              evidence_ids: ["achievement-suggestion:17"],
            },
          ],
          completed_at: "2026-07-28T18:01:00Z",
        },
      }),
    );
    render(
      <MemoryRouter initialEntries={["/articles/401"]}>
        <Routes>
          <Route path="/articles/:id" element={<ArticleBriefPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("The generated draft failed validation."),
    ).toBeInTheDocument();
    expect(screen.getByText("Unsupported numeral: 99.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry draft" })).toBeInTheDocument();
  });

  it("saves human edits as a new version based on the latest checkpoint", async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          ...brief,
          status: "in_edit",
          latest_version: articleVersion,
          versions: [articleVersion],
          readiness_history: [],
        }),
      )
      .mockResolvedValueOnce(jsonResponse(humanVersion, { status: 201 }));
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/articles/401"]}>
        <Routes>
          <Route path="/articles/:id" element={<ArticleBriefPage />} />
        </Routes>
      </MemoryRouter>,
    );

    const headline = await screen.findByLabelText("Headline");
    await user.clear(headline);
    await user.type(headline, humanVersion.headline);
    await user.click(screen.getByRole("button", { name: "Save new version" }));

    expect((await screen.findAllByText("Version 2")).length).toBeGreaterThan(0);
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/articles/401/versions",
      expect.objectContaining({ method: "POST" }),
    );
    const request = fetchMock.mock.calls[1][1];
    expect(JSON.parse(String(request?.body))).toMatchObject({
      base_version_id: articleVersion.id,
      headline: humanVersion.headline,
    });
  });

  it("compares the original and current versions side by side and inline", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ...brief,
        status: "in_edit",
        latest_version: humanVersion,
        versions: [articleVersion, humanVersion],
        readiness_history: [],
      }),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/articles/401"]}>
        <Routes>
          <Route path="/articles/:id" element={<ArticleBriefPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole("button", { name: "Side by side" }));
    expect(screen.getByText(/Original · v1/)).toBeInTheDocument();
    expect(screen.getByText(/Selected · v2/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: articleVersion.headline })).toBeInTheDocument();
    expect(
      screen.getAllByRole("heading", { name: humanVersion.headline }).length,
    ).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "changes" }));
    expect(screen.getByText(/Inline diff/)).toBeInTheDocument();
    expect(document.querySelector("ins")).toBeInTheDocument();
    expect(document.querySelector("del")).toBeInTheDocument();
  });

  it("records a warning reason before marking the exact version ready", async () => {
    const warningVersion = {
      ...humanVersion,
      headline: `${humanVersion.headline}!`,
      validation_results: [
        {
          code: "style:no-exclamation",
          severity: "warning",
          message: "Forbidden Style Guide term(s): !.",
          block_index: null,
          evidence_ids: [],
        },
      ],
    };
    const decision = {
      id: 300,
      article_id: 401,
      article_version_id: warningVersion.id,
      action: "ready",
      actor: "sid-user",
      reason: "Acknowledged 1 nonblocking warning(s).",
      created_at: "2026-07-28T18:10:00Z",
    };
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          ...brief,
          status: "in_edit",
          latest_version: warningVersion,
          versions: [articleVersion, warningVersion],
          readiness_history: [],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          article_id: 401,
          status: "ready",
          ready_version: {
            ...warningVersion,
            warning_overrides: [
              {
                id: 200,
                article_version_id: warningVersion.id,
                finding_code: "style:no-exclamation",
                reason: "Approved punctuation for this prototype story.",
                overridden_by: "sid-user",
                created_at: "2026-07-28T18:10:00Z",
              },
            ],
          },
          decision,
        }),
      );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/articles/401"]}>
        <Routes>
          <Route path="/articles/:id" element={<ArticleBriefPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await user.type(
      await screen.findByLabelText("Reason for style:no-exclamation"),
      "Approved punctuation for this prototype story.",
    );
    await user.click(
      screen.getByRole("button", { name: "Mark version 2 ready" }),
    );

    expect(await screen.findByText("Version 2 approved")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/articles/401/versions/901/ready",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("explains changed evidence and refreshes only after deliberate review", async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          ...brief,
          status: "needs_revalidation",
          latest_version: articleVersion,
          versions: [articleVersion],
          readiness_history: [],
          active_revalidation: activeRevalidation,
          revalidation_history: [activeRevalidation],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          ...brief,
          status: "in_edit",
          evidence_bundle: {
            ...brief.evidence_bundle,
            id: 701,
            version: 2,
            content_hash: "2".repeat(64),
          },
          latest_version: humanVersion,
          versions: [articleVersion, humanVersion],
          readiness_history: [],
          active_revalidation: null,
          revalidation_history: [
            {
              ...activeRevalidation,
              refreshed_evidence_bundle_id: 701,
              resolved_at: "2026-07-29T16:10:00Z",
              resolved_by: "sid-user",
            },
          ],
        }),
      );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/articles/401"]}>
        <Routes>
          <Route path="/articles/:id" element={<ArticleBriefPage />} />
          <Route path="/achievements" element={<p>Achievement review queue</p>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Source evidence changed" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Avery Adams · 31.000000 · Points")).toBeInTheDocument();
    expect(screen.getByText("Avery Adams · 36.000000 · Points")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByLabelText("Headline")).toBeDisabled();
    expect(
      screen.getByRole("link", { name: "Review source suggestions" }),
    ).toHaveAttribute("href", "/achievements");

    await user.click(
      screen.getByRole("button", { name: "Refresh approved evidence" }),
    );

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/articles/401/revalidation/refresh",
      expect.objectContaining({ method: "POST" }),
    );
    expect(
      await screen.findByRole("heading", { name: humanVersion.headline }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Source evidence changed" }),
    ).not.toBeInTheDocument();
  });
});
