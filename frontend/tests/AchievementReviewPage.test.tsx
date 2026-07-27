import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AchievementReviewPage from "../src/pages/AchievementReviewPage";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), { ...init, headers });
}

const suggestion = {
  id: 17,
  game_id: 61,
  player_id: 9,
  player_name: "Avery Adams",
  stat_key: "points",
  stat_label: "Points",
  suggestion_key: "career_high:9:points",
  achievement_type: "career_high",
  scope: "career",
  computed_value: "31.000000",
  comparison_value: "27.000000",
  rank: null,
  deterministic_notability_score: "4.500",
  context: { previous_high: "27.000000" },
  coverage_context: {
    claim_scope: "since 2023-24",
    known_limitations: "Earlier seasons are not available.",
  },
  phrasing: "Avery Adams set a career high with 31 points since 2023-24.",
  ai_rank: 1,
  ai_model: "qwen/qwen3.6-27b",
  ai_prompt_version: "achievement-ranking-v1",
  ai_output_hash: "hash",
  ai_ranked_at: "2026-07-27T16:00:00Z",
  source_url: "https://govandals.com/boxscore/61",
  reviewed_at: null,
  reviewed_by: null,
  state: "pending",
};

const pendingQueue = {
  items: [
    {
      game_id: 61,
      title: "Idaho at Montana State",
      game_date: "2025-12-01",
      season: "2025-26",
      home_team: "Montana State",
      away_team: "Idaho",
      home_score: 66,
      away_score: 72,
      source_url: "https://govandals.com/boxscore/61",
      suggestions: [suggestion],
    },
  ],
  total_games: 1,
  pending_count: 1,
  approved_count: 0,
  rejected_count: 0,
};

const emptyQueue = {
  items: [],
  total_games: 0,
  pending_count: 0,
  approved_count: 1,
  rejected_count: 0,
};

beforeEach(() => {
  fetchMock.mockReset();
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

describe("AchievementReviewPage", () => {
  it("shows ranked evidence and records an approval", async () => {
    let pendingLoads = 0;
    fetchMock.mockImplementation(async (input, init) => {
      const endpoint = String(input);
      if (endpoint.includes("review-queue?state=pending")) {
        pendingLoads += 1;
        return jsonResponse(pendingLoads === 1 ? pendingQueue : emptyQueue);
      }
      if (
        endpoint.endsWith("/achievement-suggestions/17/verdict") &&
        init?.method === "PATCH"
      ) {
        return jsonResponse({
          ...suggestion,
          state: "approved",
          reviewed_at: "2026-07-27T17:00:00Z",
          reviewed_by: "sid-user",
        });
      }
      return jsonResponse({ detail: "Not found" }, { status: 404 });
    });

    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AchievementReviewPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText(suggestion.phrasing)).toBeInTheDocument();
    expect(screen.getByText("since 2023-24")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Record Book" })).toHaveAttribute(
      "href",
      "/record-book",
    );

    await user.click(screen.getByRole("button", { name: "Approve for use" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/achievement-suggestions/17/verdict",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ state: "approved" }),
        }),
      ),
    );
    expect(
      await screen.findByText("Avery Adams's career high was approved."),
    ).toBeInTheDocument();
    expect(await screen.findByText("The desk is clear")).toBeInTheDocument();
  });

  it("keeps reviewed suggestions available with audit metadata", async () => {
    const approvedSuggestion = {
      ...suggestion,
      state: "approved",
      reviewed_at: "2026-07-27T17:00:00Z",
      reviewed_by: "sid-user",
    };
    fetchMock.mockImplementation(async (input) => {
      const endpoint = String(input);
      if (endpoint.includes("review-queue?state=approved")) {
        return jsonResponse({
          ...pendingQueue,
          pending_count: 0,
          approved_count: 1,
          items: [{ ...pendingQueue.items[0], suggestions: [approvedSuggestion] }],
        });
      }
      return jsonResponse({ ...emptyQueue, approved_count: 1 });
    });

    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AchievementReviewPage />
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole("button", { name: /Approved/ }));

    expect(await screen.findByText(suggestion.phrasing)).toBeInTheDocument();
    expect(screen.getByText(/Approved by/)).toHaveTextContent("sid-user");
  });
});
