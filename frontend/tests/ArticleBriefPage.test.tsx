import { cleanup, render, screen } from "@testing-library/react";
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
});
