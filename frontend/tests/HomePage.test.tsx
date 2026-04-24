import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "../src/pages/HomePage";

const SAMPLE_BOXSCORE_URL =
  "https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");

  return new Response(JSON.stringify(body), {
    ...init,
    headers,
  });
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(jsonResponse([]));
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

describe("HomePage", () => {
  it("renders the pipeline heading and empty state", async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "Vandals Stats Pipeline" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText(/No games yet/i),
    ).toBeInTheDocument();
  });

  it("fills the ingest form with the sample boxscore", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await user.click(
      screen.getByRole("button", { name: "Use sample boxscore" }),
    );

    expect(screen.getByPlaceholderText(/govandals\.com/i)).toHaveValue(
      SAMPLE_BOXSCORE_URL,
    );
  });

  it("loads discovered schedule events and ingests a boxscore", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (input, init) => {
      const endpoint = String(input);
      if (endpoint === "/api/v1/sources/football/schedule?season=2025") {
        return jsonResponse([
          {
            sport_slug: "football",
            sport_name: "Football",
            gender: null,
            season: "2025",
            source_system: "sidearm",
            schedule_url: "https://govandals.com/sports/football/schedule",
            source_event_id: "8467",
            opponent_source_id: "174",
            opponent_name: "UC Davis",
            event_status: "final",
            home_away_neutral: "home",
            event_date: "2025-11-08",
            date_text: "Nov 8 (Sat)",
            time_text: null,
            location_name: "Moscow, Idaho",
            venue_name: "P1FCU Kibbie Dome",
            conference_name: "Big Sky",
            conference_event: true,
            result_status: "L",
            team_score: 14,
            opponent_score: 28,
            source_urls: { boxscore_html: SAMPLE_BOXSCORE_URL },
            boxscore_url: SAMPLE_BOXSCORE_URL,
          },
        ]);
      }

      if (endpoint === "/api/v1/games" && init?.method === "POST") {
        return jsonResponse({ id: 1 }, { status: 201 });
      }

      return jsonResponse([]);
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Load schedule" }));
    expect(await screen.findByText("UC Davis")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Ingest boxscore" }));

    const ingestCall = fetchMock.mock.calls.find(
      ([input, init]) => input === "/api/v1/games" && init?.method === "POST",
    );
    expect(ingestCall?.[1]?.body).toBe(
      JSON.stringify({ url: SAMPLE_BOXSCORE_URL }),
    );
  });

  it("uses academic-year seasons for basketball schedules", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (input) => {
      const endpoint = String(input);
      if (
        endpoint === "/api/v1/sources/mens-basketball/schedule?season=2025-26"
      ) {
        return jsonResponse([]);
      }

      return jsonResponse([]);
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await user.selectOptions(
      screen.getByLabelText("Sport"),
      "mens-basketball",
    );
    expect(screen.getByLabelText("Season")).toHaveValue("2025-26");

    await user.click(screen.getByRole("button", { name: "Load schedule" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/sources/mens-basketball/schedule?season=2025-26",
      expect.anything(),
    );
  });

  it("imports a selected schedule and refreshes the game list", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (input, init) => {
      const endpoint = String(input);
      if (
        endpoint === "/api/v1/sources/football/schedule/import?season=2025" &&
        init?.method === "POST"
      ) {
        return jsonResponse([
          {
            id: 1,
            source_url: SAMPLE_BOXSCORE_URL,
            canonical_uid: "sidearm:football:2025:8467",
            source_system: "sidearm",
            source_event_id: "8467",
            sport: "football",
            sport_name: "Football",
            gender: null,
            season: "2025",
            game_date: "2025-11-08",
            event_shape: "team_contest",
            event_status: "final",
            publish_status: "draft",
            home_team: "Idaho",
            away_team: "UC Davis",
            home_score: 14,
            away_score: 28,
            title: "Idaho vs UC Davis",
            start_at: null,
            end_at: null,
            timezone: null,
            location_name: "Moscow, Idaho",
            venue_name: "P1FCU Kibbie Dome",
            home_away_neutral: "home",
            conference_event: true,
            exhibition: false,
            first_seen_at: null,
            last_seen_at: null,
            last_successful_ingest_at: null,
            ingested_at: "2026-04-24T12:00:00Z",
          },
        ]);
      }

      return jsonResponse([]);
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Import schedule" }));

    expect(
      await screen.findByText("Imported 1 schedule event."),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/sources/football/schedule/import?season=2025",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
