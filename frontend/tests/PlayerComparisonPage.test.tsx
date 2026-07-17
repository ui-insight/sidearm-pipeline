import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import PlayerComparisonPage from "../src/pages/PlayerComparisonPage";
import {
  alignComparisonGames,
  buildPlayerComparisonCsv,
} from "../src/utils/workspaceCsv";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), { ...init, headers });
}

function LocationProbe() {
  const location = useLocation();
  return <output aria-label="Current location">{location.pathname}{location.search}</output>;
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
  players: [
    {
      player_id: 4,
      player_name: "Alice Adams",
      seasons: ["2025-26", "2024-25"],
    },
    {
      player_id: 8,
      player_name: "Bobbi Brown",
      seasons: ["2025-26"],
    },
    {
      player_id: 11,
      player_name: "Renee Rivers",
      seasons: ["2025-26", "2024-25"],
    },
  ],
  opponents: [
    {
      opponent_name: "Montana",
      seasons: ["2025-26", "2024-25"],
    },
    {
      opponent_name: "Montana State",
      seasons: ["2025-26"],
    },
    {
      opponent_name: "Washington State",
      seasons: ["2025-26"],
    },
  ],
  leader_limits: [5, 10, 15, 25],
  default_season: "2025-26",
  default_stat_key: "points",
};

const games = {
  montana: {
    game_id: 21,
    game_date: "2026-01-03",
    season: "2025-26",
    opponent: "Montana",
    venue: "home",
    conference_event: true,
    source_snapshot_id: 21,
    source_url: "https://govandals.com/boxscore/21",
  },
  montanaState: {
    game_id: 22,
    game_date: "2026-01-09",
    season: "2025-26",
    opponent: "Montana State",
    venue: "away",
    conference_event: true,
    source_snapshot_id: 22,
    source_url: "https://govandals.com/boxscore/22",
  },
  washingtonState: {
    game_id: 23,
    game_date: "2026-01-16",
    season: "2025-26",
    opponent: "Washington State",
    venue: "home",
    conference_event: false,
    source_snapshot_id: 23,
    source_url: "https://govandals.com/boxscore/23",
  },
};

const coverage = {
  grain: "game",
  first_season: "2025-26",
  last_season: "2025-26",
  completeness: "complete",
  source_systems: ["sidearm"],
  known_limitations: [],
  verified_at: "2026-07-15T20:00:00Z",
  statement: "Verified game evidence covers the selected season.",
};

function splitFor(playerId: number, overrides: Record<string, unknown> = {}) {
  const isAlice = playerId === 4;
  const playerName =
    playerId === 4
      ? "Alice Adams"
      : playerId === 11
        ? "Renee Rivers"
        : "Bobbi Brown";
  return {
    program_slug: "womens-basketball",
    program_name: "Women's Basketball",
    player_id: playerId,
    player_name: playerName,
    stat_key: "points",
    stat_label: "Points",
    aggregation_method: "sum",
    season: "2025-26",
    conference_scope: "all",
    venue_scope: "all",
    opponent: null,
    value: isAlice ? "35" : "26",
    games_count: 2,
    open_quality_issue_count: isAlice ? 1 : 0,
    coverage,
    games: isAlice
      ? [
          { ...games.montana, value: "20" },
          { ...games.montanaState, value: "15" },
        ]
      : [
          { ...games.montana, value: "12" },
          { ...games.washingtonState, value: "14" },
        ],
    ...overrides,
  };
}

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
      const rebounds = body.stat_key === "total_rebounds";
      return jsonResponse({
        query_id: "player_game_split",
        result: splitFor(Number(body.player_id), {
          season: body.season,
          stat_key: body.stat_key,
          stat_label: rebounds ? "Rebounds" : "Points",
          conference_scope: body.conference_scope,
          venue_scope: body.venue_scope,
          opponent: body.opponent ?? null,
        }),
      });
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

describe("PlayerComparisonPage", () => {
  it("runs the same governed filters for two distinct players", async () => {
    render(
      <MemoryRouter initialEntries={["/workspace/compare"]}>
        <PlayerComparisonPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Alice Adams vs. Bobbi Brown",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("progressbar", { name: "Alice Adams: 35 Points" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("progressbar", { name: "Bobbi Brown: 26 Points" }),
    ).toBeInTheDocument();
    const evidenceTable = screen.getByRole("table");
    expect(within(evidenceTable).getByText("Montana State")).toBeInTheDocument();
    expect(
      within(evidenceTable).getByText("Washington State"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: "View Alice Adams source against Montana",
      }),
    ).toHaveAttribute("href", "https://govandals.com/boxscore/21");
    expect(screen.getByText("1 open quality issue")).toBeInTheDocument();
    expect(screen.getByText("No open quality issues")).toBeInTheDocument();

    const playerA = screen.getByLabelText("Player A");
    const playerB = screen.getByLabelText("Player B");
    expect(playerA).toHaveValue("4");
    expect(playerB).toHaveValue("8");
    expect(
      within(playerA).getByRole("option", { name: "Bobbi Brown" }),
    ).toBeDisabled();
    expect(
      within(playerB).getByRole("option", { name: "Alice Adams" }),
    ).toBeDisabled();

    const bodies = fetchMock.mock.calls
      .filter(([, init]) => init?.method === "POST")
      .map(([, init]) => requestBody(init));
    for (const playerId of [4, 8]) {
      expect(bodies).toContainEqual({
        query_id: "player_game_split",
        player_id: playerId,
        stat_key: "points",
        season: "2025-26",
        conference_scope: "all",
        venue_scope: "all",
      });
    }
  });

  it("reruns both players when a shared comparison filter changes", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/workspace/compare"]}>
        <PlayerComparisonPage />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", {
      name: "Alice Adams vs. Bobbi Brown",
    });

    await user.selectOptions(screen.getByLabelText("Statistic"), "total_rebounds");
    await user.selectOptions(screen.getByLabelText("Competition"), "conference");
    await user.selectOptions(screen.getByLabelText("Venue"), "home");
    await user.selectOptions(screen.getByLabelText("Opponent"), "Montana");

    await waitFor(() => {
      const bodies = fetchMock.mock.calls
        .filter(([, init]) => init?.method === "POST")
        .map(([, init]) => requestBody(init));
      for (const playerId of [4, 8]) {
        expect(bodies).toContainEqual({
          query_id: "player_game_split",
          player_id: playerId,
          stat_key: "total_rebounds",
          season: "2025-26",
          conference_scope: "conference",
          venue_scope: "home",
          opponent: "Montana",
        });
      }
    });
    expect(
      await screen.findByText(
        "Rebounds against Montana from the same governed game filters.",
      ),
    ).toBeInTheDocument();
  });

  it("hydrates a complete player comparison from the URL", async () => {
    render(
      <MemoryRouter
        initialEntries={[
          "/workspace/compare?season=2024-25&stat=points&conference=conference&venue=home&opponent=Montana&left=11&right=4",
        ]}
      >
        <PlayerComparisonPage />
        <LocationProbe />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Renee Rivers vs. Alice Adams",
      }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Player A")).toHaveValue("11");
    expect(screen.getByLabelText("Player B")).toHaveValue("4");
    expect(screen.getByLabelText("Season")).toHaveValue("2024-25");
    expect(screen.getByLabelText("Competition")).toHaveValue("conference");
    expect(screen.getByLabelText("Venue")).toHaveValue("home");
    expect(screen.getByLabelText("Opponent")).toHaveValue("Montana");
    expect(screen.getByLabelText("Current location")).toHaveTextContent(
      "/workspace/compare?season=2024-25&stat=points&conference=conference&venue=home&opponent=Montana&left=11&right=4",
    );

    const bodies = fetchMock.mock.calls
      .filter(([, init]) => init?.method === "POST")
      .map(([, init]) => requestBody(init));
    for (const playerId of [11, 4]) {
      expect(bodies).toContainEqual({
        query_id: "player_game_split",
        player_id: playerId,
        stat_key: "points",
        season: "2024-25",
        conference_scope: "conference",
        venue_scope: "home",
        opponent: "Montana",
      });
    }
  });

  it("falls back when a shared opponent is stale for the selected season", async () => {
    render(
      <MemoryRouter
        initialEntries={[
          "/workspace/compare?season=2024-25&stat=points&conference=all&venue=all&opponent=Washington+State&left=11&right=4",
        ]}
      >
        <PlayerComparisonPage />
        <LocationProbe />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Renee Rivers vs. Alice Adams",
      }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Opponent")).toHaveValue("all");
    await waitFor(() => {
      expect(screen.getByLabelText("Current location")).toHaveTextContent(
        "/workspace/compare?season=2024-25&stat=points&conference=all&venue=all&opponent=all&left=11&right=4",
      );
    });

    const bodies = fetchMock.mock.calls
      .filter(([, init]) => init?.method === "POST")
      .map(([, init]) => requestBody(init));
    expect(bodies).toHaveLength(2);
    expect(bodies.every((body) => body.opponent === undefined)).toBe(true);
  });

  it("aligns unequal game sets and exports the comparison evidence", () => {
    const left = splitFor(4);
    const right = splitFor(8);

    expect(alignComparisonGames(left, right)).toMatchObject([
      { game_id: 21, left_value: "20", right_value: "12" },
      { game_id: 22, left_value: "15", right_value: null },
      { game_id: 23, left_value: null, right_value: "14" },
    ]);
    const csv = buildPlayerComparisonCsv(left, right);
    expect(csv).toContain("Alice Adams,35,2,1");
    expect(csv).toContain("Bobbi Brown,26,2,0");
    expect(csv).toContain("Opponent,all");
    expect(csv).toContain(
      "2026-01-09,Montana State,away,Yes,15,,https://govandals.com/boxscore/22,",
    );
  });

  it("explains when fewer than two players have game evidence", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ...options,
        players: [options.players[0]],
      }),
    );

    render(
      <MemoryRouter initialEntries={["/workspace/compare"]}>
        <PlayerComparisonPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Two-player evidence is not ready yet",
      }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("recovers when a governed comparison request fails", async () => {
    const user = userEvent.setup();
    let shouldFail = true;
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
        if (shouldFail) {
          return jsonResponse(
            { detail: "Comparison service unavailable" },
            { status: 503 },
          );
        }
        const body = requestBody(init);
        return jsonResponse({
          query_id: "player_game_split",
          result: splitFor(Number(body.player_id)),
        });
      }
      return jsonResponse({ detail: "Not found" }, { status: 404 });
    });

    render(
      <MemoryRouter initialEntries={["/workspace/compare"]}>
        <PlayerComparisonPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Comparison service unavailable",
    );
    shouldFail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", {
        name: "Alice Adams vs. Bobbi Brown",
      }),
    ).toBeInTheDocument();
  });
});
