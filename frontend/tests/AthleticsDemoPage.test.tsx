import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AthleticsDemoPage from "../src/pages/AthleticsDemoPage";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const game = (
  gameId: number,
  gameDate: string,
  opponent: string,
  idahoScore: number,
  opponentScore: number,
) => ({
  game_id: gameId,
  game_date: gameDate,
  opponent,
  venue: "home",
  idaho_score: idahoScore,
  opponent_score: opponentScore,
  result: idahoScore > opponentScore ? "win" : "loss",
  source_url: `https://govandals.com/boxscore/${gameId}`,
});

const brief = {
  program_name: "Women's Basketball",
  season: "2025-26",
  as_of_date: "2026-02-04",
  target_game: game(23, "2026-02-05", "Montana State", 73, 70),
  season_record: { games_played: 22, wins: 17, losses: 5, ties: 0 },
  recent_form: [
    game(22, "2026-01-31", "Northern Arizona", 94, 71),
    game(21, "2026-01-29", "Northern Colorado", 62, 55),
    game(20, "2026-01-24", "Portland State", 84, 66),
    game(19, "2026-01-22", "Sacramento State", 62, 55),
    game(18, "2026-01-17", "Weber State", 95, 76),
  ],
  prior_meetings: [game(16, "2026-01-10", "Montana State", 66, 99)],
  scoring_leaders: [
    {
      player_id: 13,
      player_name: "Jordan Example",
      games_played: 22,
      total_points: "330.000000",
      points_per_game: "15.0",
      evidence: [],
    },
  ],
  evidence_game_count: 22,
  methodology: "Uses only games dated through 2026-02-04.",
};

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(jsonResponse(brief));
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
  it("presents a sourced, time-locked historical briefing", async () => {
    render(
      <MemoryRouter>
        <AthleticsDemoPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Montana State at Idaho" }),
    ).toBeInTheDocument();
    expect(screen.getByText("No hindsight: data through February 4, 2026")).toBeInTheDocument();
    expect(screen.getByText("17–5")).toBeInTheDocument();
    expect(screen.getByText("5–0")).toBeInTheDocument();
    expect(screen.getAllByText("Jordan Example")).toHaveLength(2);
    expect(screen.getAllByRole("link", { name: "Box score" })).toHaveLength(5);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/pregame-briefs/historical?season=2025-26&opponent=Montana+State&game_date=2026-02-05",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("keeps the actual result hidden until explicitly revealed", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AthleticsDemoPage />
      </MemoryRouter>,
    );

    const revealButton = await screen.findByRole("button", {
      name: "Reveal result",
    });
    expect(
      screen.queryByText("Idaho 73, Montana State 70"),
    ).not.toBeInTheDocument();

    await user.click(revealButton);

    expect(screen.getByText("Idaho 73, Montana State 70")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the final box score" })).toHaveAttribute(
      "href",
      "https://govandals.com/boxscore/23",
    );
  });

  it("shows a clear failure state when the brief is unavailable", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Historical matchup not found" }, 404),
    );
    render(
      <MemoryRouter>
        <AthleticsDemoPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Brief unavailable")).toBeInTheDocument();
    expect(screen.getByText("Historical matchup not found")).toBeInTheDocument();
  });
});
