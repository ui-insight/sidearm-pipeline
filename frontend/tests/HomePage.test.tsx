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
});
