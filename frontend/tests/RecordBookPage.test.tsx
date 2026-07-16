import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import RecordBookPage from "../src/pages/RecordBookPage";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), { ...init, headers });
}

const careerLeaderboard = {
  program_slug: "womens-basketball",
  program_name: "Women's Basketball",
  stat_key: "points",
  stat_label: "Points",
  scope: "career",
  season: null,
  available_seasons: ["2025-26", "2024-25"],
  total_players: 3,
  open_quality_issue_count: 1,
  coverage: {
    first_season: "2024-25",
    last_season: "2025-26",
    completeness: "complete",
    source_systems: ["sidearm"],
    known_limitations: ["Public HTML fallback; source authority pending."],
    verified_at: "2026-07-15T20:00:00Z",
    statement:
      "Verified season sources cover 2024-25 through 2025-26. Career totals reflect this window, not all-time history.",
  },
  leaders: [
    {
      rank: 1,
      player_id: 4,
      player_name: "Alice Adams",
      total: "225",
      seasons_count: 2,
      season_breakdown: [
        {
          season: "2025-26",
          value: "125",
          source_snapshot_id: 12,
          source_url: "https://govandals.com/stats/wbb/2025-26",
        },
        {
          season: "2024-25",
          value: "100",
          source_snapshot_id: 8,
          source_url: "https://govandals.com/stats/wbb/2024-25",
        },
      ],
    },
    {
      rank: 1,
      player_id: 8,
      player_name: "Bobbi Brown",
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
  ],
};

const seasonLeaderboard = {
  ...careerLeaderboard,
  scope: "season",
  season: "2025-26",
  total_players: 2,
  coverage: {
    ...careerLeaderboard.coverage,
    first_season: "2025-26",
    statement: "Verified season source for 2025-26.",
  },
  leaders: [careerLeaderboard.leaders[1], careerLeaderboard.leaders[0]],
};

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (input, init) => {
    const endpoint = String(input);
    if (
      endpoint === "/api/v1/record-book/leaders/points?scope=career&limit=10" &&
      init?.method === "GET"
    ) {
      return jsonResponse(careerLeaderboard);
    }
    if (
      endpoint ===
        "/api/v1/record-book/leaders/points?scope=season&limit=10&season=2025-26" &&
      init?.method === "GET"
    ) {
      return jsonResponse(seasonLeaderboard);
    }
    return jsonResponse({ detail: "Not found" }, { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("localStorage", { getItem: vi.fn(() => null) });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("RecordBookPage", () => {
  it("shows career points with coverage and source evidence", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <RecordBookPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Points leaders" })).toBeInTheDocument();
    expect(screen.getByText(/not all-time history/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "1" })).toHaveAttribute(
      "href",
      "/identity-queue",
    );
    expect(screen.getByRole("button", { name: "Alice Adams" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getAllByText("225").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "View 2025-26 source" })).toHaveAttribute(
      "href",
      "https://govandals.com/stats/wbb/2025-26",
    );

    await user.click(screen.getByRole("button", { name: "Bobbi Brown" }));
    expect(screen.getByRole("heading", { name: "Bobbi Brown" })).toBeInTheDocument();
  });

  it("switches to the latest season leaderboard", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <RecordBookPage />
      </MemoryRouter>,
    );

    await screen.findByRole("button", { name: "Alice Adams" });
    await user.click(screen.getByRole("tab", { name: "Season" }));

    expect(await screen.findByRole("heading", { name: "2025-26 points" })).toBeInTheDocument();
    expect(screen.getByLabelText("Season")).toHaveValue("2025-26");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/record-book/leaders/points?scope=season&limit=10&season=2025-26",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("offers recovery when the leaderboard request fails", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Warehouse unavailable" }, { status: 503 }),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <RecordBookPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Warehouse unavailable");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("button", { name: "Alice Adams" })).toBeInTheDocument();
  });
});
