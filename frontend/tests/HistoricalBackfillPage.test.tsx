import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import HistoricalBackfillPage from "../src/pages/HistoricalBackfillPage";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), { ...init, headers });
}

const failedRun = {
  id: 21,
  game_id: null,
  trigger_type: "operator_sync",
  source_system: "sidearm",
  source_type: "historical_range_backfill",
  source_url: "https://govandals.com/sports/womens-basketball/schedule",
  source_event_id: null,
  sport: "womens-basketball",
  season: null,
  status: "partial",
  started_at: "2026-07-15T20:00:00Z",
  finished_at: "2026-07-15T20:04:00Z",
  duration_ms: 240000,
  attempt_count: 1,
  max_attempts: 1,
  http_status: null,
  retryable: false,
  error_type: null,
  error_message: null,
  run_metadata: {
    start_season: "2023-24",
    end_season: "2024-25",
    boxscore_delay_seconds: 1,
    season_order: ["2023-24", "2024-25"],
    seasons: [{ season: "2023-24", status: "succeeded" }],
    seasons_failed: 1,
    last_checkpoint_at: "2026-07-15T20:04:00Z",
  },
};

const completedResult = {
  run_id: 21,
  sport_slug: "womens-basketball",
  start_season: "2023-24",
  end_season: "2024-25",
  status: "partial",
  boxscore_delay_seconds: 1,
  resumed: true,
  started_at: "2026-07-15T20:00:00Z",
  finished_at: "2026-07-15T20:08:00Z",
  seasons_total: 2,
  seasons_attempted: 1,
  seasons_skipped: 1,
  seasons_succeeded: 1,
  seasons_partial: 1,
  seasons_failed: 0,
  seasons: [
    {
      season: "2024-25",
      status: "partial",
      season_run_id: 22,
      started_at: "2026-07-15T20:05:00Z",
      finished_at: "2026-07-15T20:08:00Z",
      coverage: {
        schedule_events_seen: 31,
        final_games: 31,
        final_games_with_boxscores: 31,
        final_games_ingested: 31,
        missing_boxscores: 0,
        failed_boxscores: 0,
        open_identity_issues: 18,
        open_quality_issues: 18,
        game_completeness: "partial",
        game_coverage_window_id: 12,
      },
      error_type: null,
      error_message: null,
    },
  ],
};

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (input, init) => {
    const endpoint = String(input);
    if (
      endpoint ===
        "/api/v1/ingest-runs?source_type=historical_range_backfill&sport=womens-basketball&limit=10" &&
      init?.method === "GET"
    ) {
      return jsonResponse([failedRun]);
    }
    if (
      endpoint ===
        "/api/v1/sources/womens-basketball/historical-backfill?start_season=2023-24&end_season=2024-25&boxscore_delay_seconds=1&resume_run_id=21" &&
      init?.method === "POST"
    ) {
      return jsonResponse(completedResult);
    }
    return jsonResponse([]);
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("localStorage", { getItem: vi.fn(() => null) });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("HistoricalBackfillPage", () => {
  it("prepares a failed range for resume and reports its completed evidence", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <HistoricalBackfillPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Historical backfills" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("1 of 2 seasons checkpointed")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Prepare resume" }));
    expect(screen.getByLabelText("Start season")).toHaveValue("2023-24");
    expect(screen.getByLabelText("End season")).toHaveValue("2024-25");
    expect(screen.getByRole("button", { name: "Resume run 21" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Resume run 21" }));

    expect(
      await screen.findByRole("heading", { name: "Run 21 finished" }),
    ).toBeInTheDocument();
    expect(screen.getByText("31 of 31 finals ingested, 18 identity reviews"))
      .toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/sources/womens-basketball/historical-backfill?start_season=2023-24&end_season=2024-25&boxscore_delay_seconds=1&resume_run_id=21",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
