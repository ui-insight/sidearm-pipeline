import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ExploratoryWorkspacePage from "../src/pages/ExploratoryWorkspacePage";
import { buildWorkspaceCsv } from "../src/utils/workspaceCsv";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), { ...init, headers });
}

const options = {
  program_slug: "womens-basketball",
  program_name: "Women's Basketball",
  seasons: ["2025-26", "2024-25"],
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
    {
      stat_key: "total_rebounds",
      display_label: "Rebounds",
      value_type: "integer",
      unit: "count",
      aggregation_method: "sum",
      comparison_direction: "higher",
      display_format: "0",
    },
  ],
  leader_limits: [5, 10, 15, 25],
  default_season: "2025-26",
  default_stat_key: "points",
};

const record = {
  program_slug: "womens-basketball",
  program_name: "Women's Basketball",
  season: "2025-26",
  conference_scope: "all",
  games_played: 3,
  wins: 2,
  losses: 1,
  ties: 0,
  open_quality_issue_count: 1,
  coverage: {
    grain: "game",
    first_season: "2025-26",
    last_season: "2025-26",
    completeness: "complete",
    source_systems: ["sidearm"],
    known_limitations: [],
    verified_at: "2026-07-15T20:00:00Z",
    statement: "Verified game evidence covers all three results.",
  },
  games: [
    {
      game_id: 21,
      game_date: "2025-11-06",
      opponent: "Washington State",
      venue: "home",
      conference_event: false,
      idaho_score: 72,
      opponent_score: 64,
      result: "win",
      source_url: "https://govandals.com/boxscore/21",
    },
    {
      game_id: 22,
      game_date: "2025-11-10",
      opponent: "Gonzaga",
      venue: "away",
      conference_event: false,
      idaho_score: 59,
      opponent_score: 68,
      result: "loss",
      source_url: "https://govandals.com/boxscore/22",
    },
    {
      game_id: 23,
      game_date: "2026-01-03",
      opponent: "Montana",
      venue: "home",
      conference_event: true,
      idaho_score: 77,
      opponent_score: 69,
      result: "win",
      source_url: "https://govandals.com/boxscore/23",
    },
  ],
};

const leaderboard = {
  program_slug: "womens-basketball",
  program_name: "Women's Basketball",
  stat_key: "points",
  stat_label: "Points",
  scope: "season",
  season: "2025-26",
  available_seasons: ["2025-26", "2024-25"],
  total_players: 2,
  open_quality_issue_count: 0,
  coverage: {
    first_season: "2025-26",
    last_season: "2025-26",
    completeness: "complete",
    source_systems: ["sidearm"],
    known_limitations: [],
    verified_at: "2026-07-15T20:00:00Z",
    statement: "Verified player totals cover the selected season.",
  },
  leaders: [
    {
      rank: 1,
      player_id: 4,
      player_name: "Alice Adams",
      total: "225",
      seasons_count: 1,
      season_breakdown: [
        {
          season: "2025-26",
          value: "225",
          source_snapshot_id: 12,
          source_url: "https://govandals.com/stats/wbb/2025-26",
        },
      ],
    },
    {
      rank: 2,
      player_id: 8,
      player_name: "Bobbi Brown",
      total: "197",
      seasons_count: 1,
      season_breakdown: [
        {
          season: "2025-26",
          value: "197",
          source_snapshot_id: 12,
          source_url: "https://govandals.com/stats/wbb/2025-26",
        },
      ],
    },
  ],
};

function requestBody(init?: RequestInit): Record<string, unknown> {
  return JSON.parse(String(init?.body)) as Record<string, unknown>;
}

function installSuccessfulFetch() {
  fetchMock.mockImplementation(async (input, init) => {
    if (
      String(input) === "/api/v1/semantic-queries/options" &&
      init?.method === "GET"
    ) {
      return jsonResponse(options);
    }

    if (
      String(input) === "/api/v1/semantic-queries/execute" &&
      init?.method === "POST"
    ) {
      const body = requestBody(init);
      if (body.query_id === "team_season_record") {
        return jsonResponse({
          query_id: "team_season_record",
          result: {
            ...record,
            season: body.season,
            conference_scope: body.conference_scope,
          },
        });
      }
      if (body.query_id === "stat_leaders") {
        const rebounds = body.stat_key === "total_rebounds";
        return jsonResponse({
          query_id: "stat_leaders",
          result: {
            ...leaderboard,
            season: body.season,
            stat_key: body.stat_key,
            stat_label: rebounds ? "Rebounds" : "Points",
          },
        });
      }
    }

    return jsonResponse({ detail: "Not found" }, { status: 404 });
  });
}

beforeEach(() => {
  fetchMock.mockReset();
  installSuccessfulFetch();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("localStorage", { getItem: vi.fn(() => null) });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ExploratoryWorkspacePage", () => {
  it("assembles the default season record, leaders, and source evidence", async () => {
    render(
      <MemoryRouter>
        <ExploratoryWorkspacePage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Idaho finished 2–1 in 2025-26.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Season")).toHaveValue("2025-26");
    expect(screen.getByLabelText("Statistic")).toHaveValue("points");
    expect(
      screen.getByRole("progressbar", {
        name: "Alice Adams: 225 Points",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Washington State")).toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: "View source for Idaho versus Washington State",
      }),
    ).toHaveAttribute("href", "https://govandals.com/boxscore/21");
    expect(screen.getByText("1 open quality issue")).toBeInTheDocument();
    expect(screen.getByText("No open quality issues")).toBeInTheDocument();

    const postBodies = fetchMock.mock.calls
      .filter(([, init]) => init?.method === "POST")
      .map(([, init]) => requestBody(init));
    expect(postBodies).toContainEqual({
      query_id: "team_season_record",
      season: "2025-26",
      conference_scope: "all",
    });
    expect(postBodies).toContainEqual({
      query_id: "stat_leaders",
      stat_key: "points",
      scope: "season",
      season: "2025-26",
      limit: 10,
    });
  });

  it("reruns the governed queries when workspace filters change", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ExploratoryWorkspacePage />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", {
      name: "Idaho finished 2–1 in 2025-26.",
    });

    await user.selectOptions(screen.getByLabelText("Statistic"), "total_rebounds");
    await user.selectOptions(screen.getByLabelText("Record scope"), "conference");
    await user.selectOptions(screen.getByLabelText("Leaders"), "5");

    await waitFor(() => {
      const postBodies = fetchMock.mock.calls
        .filter(([, init]) => init?.method === "POST")
        .map(([, init]) => requestBody(init));
      expect(postBodies).toContainEqual({
        query_id: "team_season_record",
        season: "2025-26",
        conference_scope: "conference",
      });
      expect(postBodies).toContainEqual({
        query_id: "stat_leaders",
        stat_key: "total_rebounds",
        scope: "season",
        season: "2025-26",
        limit: 5,
      });
    });
    expect(
      await screen.findByRole("heading", { name: "2025-26 Rebounds" }),
    ).toBeInTheDocument();
  });

  it("builds a spreadsheet-ready export with both evidence sections", () => {
    const csv = buildWorkspaceCsv(record, leaderboard);

    expect(csv).toContain("Record,2-1-0");
    expect(csv).toContain(
      "Game,2025-11-06,Washington State,home,No,win,72,64,https://govandals.com/boxscore/21",
    );
    expect(csv).toContain(
      "Leader,1,Alice Adams,225,https://govandals.com/stats/wbb/2025-26",
    );
  });

  it("recovers after the options request fails", async () => {
    const user = userEvent.setup();
    let optionsAttempts = 0;
    fetchMock.mockImplementation(async (input, init) => {
      if (
        String(input) === "/api/v1/semantic-queries/options" &&
        init?.method === "GET"
      ) {
        optionsAttempts += 1;
        if (optionsAttempts === 1) {
          return jsonResponse(
            { detail: "Warehouse unavailable" },
            { status: 503 },
          );
        }
      }
      installSuccessfulFetch();
      return fetchMock(input, init);
    });

    render(
      <MemoryRouter>
        <ExploratoryWorkspacePage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Warehouse unavailable",
    );
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", {
        name: "Idaho finished 2–1 in 2025-26.",
      }),
    ).toBeInTheDocument();
  });

  it("directs an empty workspace to the backfill workflow", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ...options,
        seasons: [],
        metrics: [],
        default_season: null,
        default_stat_key: null,
      }),
    );

    render(
      <MemoryRouter>
        <ExploratoryWorkspacePage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", {
        name: "No season evidence is ready yet",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open backfills" })).toHaveAttribute(
      "href",
      "/backfills",
    );
  });
});
