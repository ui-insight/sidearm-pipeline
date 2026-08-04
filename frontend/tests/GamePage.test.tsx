import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import GamePage from "../src/pages/GamePage";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), { ...init, headers });
}

const game = {
  id: 42,
  source_url: "https://govandals.com/boxscore/9968",
  canonical_uid: "sidearm:womens-basketball:2025-26:9968",
  source_system: "sidearm",
  source_event_id: "9968",
  sport: "womens-basketball",
  sport_name: "Women's Basketball",
  gender: "women",
  season: "2025-26",
  game_date: "2026-01-17",
  event_shape: "team_contest",
  event_status: "final",
  publish_status: "draft",
  home_team: "Idaho",
  away_team: "Idaho State",
  home_score: 71,
  away_score: 64,
  title: "Idaho State at Idaho",
  start_at: null,
  end_at: null,
  timezone: null,
  location_name: "Moscow, Idaho",
  venue_name: "ICC Arena",
  home_away_neutral: "home",
  conference_event: true,
  exhibition: false,
  first_seen_at: null,
  last_seen_at: null,
  last_successful_ingest_at: null,
  ingested_at: "2026-07-15T20:00:00Z",
  team_stats: [],
  player_stats: [],
  scoring_plays: [],
  event_sources: [],
  source_snapshots: [
    {
      id: 7,
      source_system: "sidearm",
      source_type: "boxscore_html",
      source_url: "https://govandals.com/boxscore/9968",
      parser_version: "sidearm-html-v2",
      content_hash: "abc123",
      http_status: 200,
      fetched_at: "2026-07-15T20:00:00Z",
    },
  ],
  status_history: [],
  generated_content: [],
};

const facts = [
  {
    player_id: 3,
    player_name: "Gardner, Kyra",
    team_id: 1,
    team_name: "Idaho",
    stat_key: "minutes_played",
    display_label: "Minutes",
    value: "31.000000",
    value_type: "duration",
    display_format: "0",
    source_field: "MIN",
    source_value: "31",
    source_snapshot_id: 7,
  },
  {
    player_id: 3,
    player_name: "Gardner, Kyra",
    team_id: 1,
    team_name: "Idaho",
    stat_key: "points",
    display_label: "Points",
    value: "13.000000",
    value_type: "integer",
    display_format: "0",
    source_field: "PTS",
    source_value: "13",
    source_snapshot_id: 7,
  },
];

const suggestion = {
  id: 17,
  game_id: 42,
  player_id: 3,
  player_name: "Kyra Gardner",
  stat_key: "points",
  stat_label: "Points",
  suggestion_key: "career_high:3:points",
  achievement_type: "career_high",
  scope: "career",
  computed_value: "31.000000",
  comparison_value: "27.000000",
  rank: null,
  deterministic_notability_score: "4.500",
  context: {},
  coverage_context: { claim_scope: "since 2023-24" },
  phrasing: "Kyra Gardner set a career high with 31 points since 2023-24.",
  ai_rank: 1,
  ai_model: "qwen/qwen3.6-27b",
  ai_prompt_version: "achievement-ranking-v1",
  ai_output_hash: "hash",
  ai_ranked_at: "2026-07-27T16:00:00Z",
  source_url: game.source_url,
  reviewed_at: null,
  reviewed_by: null,
  reviewed_fact_hash: null,
  state: "pending",
};

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (input) => {
    if (String(input) === "/api/v1/games/42/player-stats") {
      return jsonResponse(facts);
    }
    if (String(input) === "/api/v1/games/42") {
      return jsonResponse(game);
    }
    if (String(input) === "/api/v1/achievement-suggestions/games/42") {
      return jsonResponse([suggestion]);
    }
    return jsonResponse({}, { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("localStorage", {
    getItem: vi.fn(() => null),
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("GamePage", () => {
  it("renders normalized player facts and latest-snapshot provenance", async () => {
    render(
      <MemoryRouter initialEntries={["/games/42"]}>
        <Routes>
          <Route path="/games/:id" element={<GamePage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Idaho State at Idaho" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Normalized player stats" }),
    ).toBeInTheDocument();
    const playerRow = screen.getByRole("row", { name: /Kyra Gardner/i });
    expect(within(playerRow).getByRole("cell", { name: "13" })).toBeInTheDocument();
    expect(screen.getByText("Verified against latest snapshot")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open original boxscore" }),
    ).toHaveAttribute("href", game.source_url);
    expect(
      screen.getByRole("heading", { name: "Suggested story themes" }),
    ).toBeInTheDocument();
    expect(screen.getByText(suggestion.phrasing)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review theme" })).toHaveAttribute(
      "href",
      "/achievements?state=pending&game=42",
    );
  });

  it("marks the internal game as the next step from the pregame replay", async () => {
    render(
      <MemoryRouter initialEntries={["/games/42?from=pregame-demo"]}>
        <Routes>
          <Route path="/games/:id" element={<GamePage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Now viewing the verified result" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Return to pregame brief" }),
    ).toHaveAttribute("href", "/demo/pregame-brief");
  });
});
