import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AthleticsDemoPage from "../src/pages/AthleticsDemoPage";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
}

const coverage = {
  grain: "game",
  first_season: "2025-26",
  last_season: "2025-26",
  completeness: "complete",
  source_systems: ["sidearm"],
  known_limitations: [],
  verified_at: "2026-07-24T18:00:00Z",
  statement: "Complete verified coverage.",
};

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (input, init) => {
    if (String(input) === "/api/v1/semantic-queries/options") {
      return jsonResponse({
        program_slug: "womens-basketball",
        program_name: "Women's Basketball",
        seasons: ["2025-26"],
        metrics: [
          {
            stat_key: "points",
            display_label: "Points",
            value_type: "integer",
            unit: "count",
            aggregation_method: "sum",
            comparison_direction: "higher",
            display_format: "0",
          },
        ],
        players: [
          { player_id: 4, player_name: "Alice Adams", seasons: ["2025-26"] },
          { player_id: 8, player_name: "Bobbi Brown", seasons: ["2025-26"] },
        ],
        opponents: [{ opponent_name: "Montana", seasons: ["2025-26"] }],
        leader_limits: [10],
        default_season: "2025-26",
        default_stat_key: "points",
      });
    }

    const body = JSON.parse(String(init?.body)) as { query_id: string };
    if (body.query_id === "team_season_record") {
      return jsonResponse({
        query_id: "team_season_record",
        result: {
          program_slug: "womens-basketball",
          program_name: "Women's Basketball",
          season: "2025-26",
          conference_scope: "all",
          opponent: null,
          games_played: 2,
          wins: 2,
          losses: 0,
          ties: 0,
          open_quality_issue_count: 0,
          coverage,
          games: [
            {
              game_id: 21,
              game_date: "2025-11-06",
              opponent: "Montana",
              venue: "home",
              conference_event: true,
              idaho_score: 72,
              opponent_score: 64,
              result: "win",
              source_url: "https://govandals.com/boxscore/21",
            },
            {
              game_id: 22,
              game_date: "2026-01-03",
              opponent: "Montana",
              venue: "away",
              conference_event: true,
              idaho_score: 70,
              opponent_score: 63,
              result: "win",
              source_url: "https://govandals.com/boxscore/22",
            },
          ],
        },
      });
    }

    return jsonResponse({
      query_id: "stat_leaders",
      result: {
        program_slug: "womens-basketball",
        program_name: "Women's Basketball",
        stat_key: "points",
        stat_label: "Points",
        scope: "season",
        season: "2025-26",
        available_seasons: ["2025-26"],
        total_players: 2,
        open_quality_issue_count: 0,
        coverage,
        leaders: [],
      },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("localStorage", {
    clear: vi.fn(),
    getItem: vi.fn(() => null),
    removeItem: vi.fn(),
    setItem: vi.fn(),
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AthleticsDemoPage", () => {
  it("reports readiness and builds walkthrough links from warehouse options", async () => {
    render(
      <MemoryRouter>
        <AthleticsDemoPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Ready to present")).toBeInTheDocument();
    expect(screen.getAllByText("Ready")).toHaveLength(4);
    expect(screen.getByRole("link", { name: "Open season desk" })).toHaveAttribute(
      "href",
      "/workspace?season=2025-26&stat=points&scope=all&opponent=all&limit=10",
    );
    expect(screen.getByRole("link", { name: "Open opponent view" })).toHaveAttribute(
      "href",
      "/workspace?season=2025-26&stat=points&scope=all&opponent=Montana&limit=10",
    );
    expect(screen.getByRole("link", { name: "Open comparison" })).toHaveAttribute(
      "href",
      "/workspace/compare?season=2025-26&stat=points&conference=all&venue=all&opponent=all&left=4&right=8",
    );
  });

  it("directs the operator to season sync when no demo data exists", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        program_slug: "womens-basketball",
        program_name: "Women's Basketball",
        seasons: [],
        metrics: [],
        players: [],
        opponents: [],
        leader_limits: [10],
        default_season: null,
        default_stat_key: null,
      }),
    );

    render(
      <MemoryRouter>
        <AthleticsDemoPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Preparation required")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to season sync" })).toHaveAttribute(
      "href",
      "/",
    );
  });
});
