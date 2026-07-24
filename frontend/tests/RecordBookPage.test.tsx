import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import RecordBookPage from "../src/pages/RecordBookPage";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();
const clipboardWriteMock = vi.fn<(text: string) => Promise<void>>();

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), { ...init, headers });
}

function setupUser() {
  const user = userEvent.setup();
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: clipboardWriteMock },
  });
  return user;
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

const metricCatalog = {
  program_slug: "womens-basketball",
  program_name: "Women's Basketball",
  metrics: [
    {
      stat_key: "assists",
      display_label: "Assists",
      value_type: "integer",
      unit: "count",
      aggregation_method: "sum",
      comparison_direction: "higher",
      display_format: "0",
    },
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
    {
      stat_key: "steals",
      display_label: "Steals",
      value_type: "integer",
      unit: "count",
      aggregation_method: "sum",
      comparison_direction: "higher",
      display_format: "0",
    },
  ],
};

const seasonLeaderboard = {
  ...careerLeaderboard,
  scope: "season",
  season: "2025-26",
  total_players: 2,
  open_quality_issue_count: 0,
  coverage: {
    ...careerLeaderboard.coverage,
    first_season: "2025-26",
    last_season: "2025-26",
    statement: "Verified season source for 2025-26.",
  },
  leaders: [careerLeaderboard.leaders[1], careerLeaderboard.leaders[0]],
};

const reboundsLeaderboard = {
  ...careerLeaderboard,
  stat_key: "total_rebounds",
  stat_label: "Rebounds",
  open_quality_issue_count: 0,
  leaders: [
    {
      rank: 1,
      player_id: 11,
      player_name: "Renee Rivers",
      total: "287",
      seasons_count: 2,
      season_breakdown: [
        {
          season: "2025-26",
          value: "160",
          source_snapshot_id: 12,
          source_url: "https://govandals.com/stats/wbb/2025-26",
        },
        {
          season: "2024-25",
          value: "127",
          source_snapshot_id: 8,
          source_url: "https://govandals.com/stats/wbb/2024-25",
        },
      ],
    },
  ],
};

beforeEach(() => {
  fetchMock.mockReset();
  clipboardWriteMock.mockReset();
  clipboardWriteMock.mockResolvedValue();
  fetchMock.mockImplementation(async (input, init) => {
    const endpoint = String(input);
    if (
      endpoint === "/api/v1/record-book/metrics" &&
      init?.method === "GET"
    ) {
      return jsonResponse(metricCatalog);
    }
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
    if (
      endpoint ===
        "/api/v1/record-book/leaders/total_rebounds?scope=career&limit=10" &&
      init?.method === "GET"
    ) {
      return jsonResponse(reboundsLeaderboard);
    }
    return jsonResponse({ detail: "Not found" }, { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("localStorage", { getItem: vi.fn(() => null) });
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: clipboardWriteMock },
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("RecordBookPage", () => {
  it("shows a sourced career fact and copies its desk line", async () => {
    const user = setupUser();
    render(
      <MemoryRouter>
        <RecordBookPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Women's basketball leaders",
      }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Statistic")).toHaveValue("points");
    expect(screen.getByRole("option", { name: "Steals" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Career Points" })).toBeInTheDocument();
    await screen.findByRole("button", { name: "Alice Adams" });
    expect(screen.getByText(/not all-time history/i)).toBeInTheDocument();
    expect(screen.getByText("Scoped reviews")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "1" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Alice Adams" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(
      screen.getByText(
        "Alice Adams ranks No. 1 with 225 points across 2 seasons in the verified 2024-25 through 2025-26 coverage window.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "View 2025-26 source" }),
    ).toHaveAttribute("href", "https://govandals.com/stats/wbb/2025-26");

    await user.click(screen.getByRole("button", { name: "Copy fact" }));
    expect(clipboardWriteMock).toHaveBeenCalledWith(
      "Alice Adams ranks No. 1 with 225 points across 2 seasons in the verified 2024-25 through 2025-26 coverage window.",
    );
    expect(screen.getByRole("button", { name: "Copied" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Bobbi Brown" }));
    expect(screen.getByRole("heading", { name: "Bobbi Brown" })).toBeInTheDocument();
  });

  it("switches the leaderboard and fact sheet to rebounds", async () => {
    const user = setupUser();
    render(
      <MemoryRouter>
        <RecordBookPage />
      </MemoryRouter>,
    );

    await screen.findByRole("button", { name: "Alice Adams" });
    await user.selectOptions(screen.getByLabelText("Statistic"), "total_rebounds");

    expect(
      await screen.findByRole("heading", { name: "Career Rebounds" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Renee Rivers" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(
      screen.getByText(
        "Renee Rivers ranks No. 1 with 287 rebounds across 2 seasons in the verified 2024-25 through 2025-26 coverage window.",
      ),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/record-book/leaders/total_rebounds?scope=career&limit=10",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("switches to the latest season leaderboard", async () => {
    const user = setupUser();
    render(
      <MemoryRouter>
        <RecordBookPage />
      </MemoryRouter>,
    );

    await screen.findByRole("button", { name: "Alice Adams" });
    await user.click(screen.getByRole("tab", { name: "Season" }));

    expect(
      await screen.findByRole("heading", { name: "2025-26 Points" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Season")).toHaveValue("2025-26");
    expect(
      screen.getByText("Alice Adams ranks No. 1 in 2025-26 with 225 points."),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/record-book/leaders/points?scope=season&limit=10&season=2025-26",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("offers recovery when the leaderboard request fails", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Warehouse unavailable" }, { status: 503 }),
    );
    const user = setupUser();
    render(
      <MemoryRouter>
        <RecordBookPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Warehouse unavailable",
    );
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("button", { name: "Alice Adams" }),
    ).toBeInTheDocument();
  });
});
