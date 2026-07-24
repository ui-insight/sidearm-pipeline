import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import IdentityQueuePage from "../src/pages/IdentityQueuePage";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), { ...init, headers });
}

function queuePage(items: unknown[], total = items.length) {
  return {
    items,
    total,
    limit: 25,
    offset: 0,
    available_seasons: ["2023-24", "2025-26"],
    available_institutions: ["Idaho State University", "University of Idaho"],
  };
}

const queueItem = {
  id: 9,
  sport_program_id: 3,
  game_id: 42,
  player_id: null,
  team_id: 1,
  source_snapshot_id: 7,
  status: "open",
  severity: "warning",
  summary: "Player row 'K. Gardner' is ambiguous within the 2025-26 roster",
  details: {
    reason: "ambiguous",
    institution: "University of Idaho",
    season: "2025-26",
    player_name: "K. Gardner",
    jersey_number: "3",
    source_url: "https://govandals.com/boxscore/9968",
  },
  detected_at: "2026-07-15T20:00:00Z",
  resolved_at: null,
  resolution_notes: null,
  candidate_players: [
    { id: 3, display_name: "Kyra Gardner" },
    { id: 8, display_name: "Gardner, Kyra" },
  ],
  resolved_player_name: null,
};

const unmatchedQueueItem = {
  ...queueItem,
  id: 10,
  summary: "Player row 'Reynolds, Maria' did not match the 2025-26 roster",
  details: {
    reason: "unmatched",
    institution: "Idaho State University",
    season: "2025-26",
    player_name: "Reynolds, Maria",
    jersey_number: "12",
    source_url: "https://isubengals.com/roster/maria-reynolds/9912",
  },
  candidate_players: [],
};

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (input, init) => {
    const endpoint = String(input);
    if (
      endpoint ===
        "/api/v1/identity-resolution/queue/page?status=open&limit=25&offset=0" &&
      init?.method === "GET"
    ) {
      return jsonResponse(queuePage([queueItem]));
    }
    if (
      endpoint === "/api/v1/identity-resolution/queue/9/resolve" &&
      init?.method === "POST"
    ) {
      return jsonResponse({
        issue_id: 9,
        player_id: 3,
        match_key: "identity-key",
        status: "resolved",
      });
    }
    return jsonResponse([]);
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

describe("IdentityQueuePage", () => {
  it("shows source evidence and records an ambiguous identity decision", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <IdentityQueuePage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "K. Gardner" })).toBeInTheDocument();
    expect(screen.getAllByText("University of Idaho")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "View source" })).toHaveAttribute(
      "href",
      "https://govandals.com/boxscore/9968",
    );

    await user.selectOptions(screen.getByLabelText("Canonical player"), "3");
    await user.type(
      screen.getByLabelText("Decision note"),
      "SID confirmed the roster and source bio.",
    );
    await user.click(screen.getByRole("button", { name: "Confirm identity" }));

    expect(
      await screen.findByText("K. Gardner was linked to a canonical player."),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/identity-resolution/queue/9/resolve",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          player_id: 3,
          resolution_notes: "SID confirmed the roster and source bio.",
        }),
      }),
    );
  });

  it("creates and resolves a canonical player for an unmatched source row", async () => {
    fetchMock.mockImplementation(async (input, init) => {
      const endpoint = String(input);
      if (
        endpoint ===
          "/api/v1/identity-resolution/queue/page?status=open&limit=25&offset=0" &&
        init?.method === "GET"
      ) {
        return jsonResponse(queuePage([unmatchedQueueItem]));
      }
      if (
        endpoint === "/api/v1/identity-resolution/queue/10/create-player" &&
        init?.method === "POST"
      ) {
        return jsonResponse(
          {
            issue_id: 10,
            player_id: 27,
            match_key: "identity-key",
            status: "resolved",
          },
          { status: 201 },
        );
      }
      return jsonResponse([]);
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <IdentityQueuePage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Maria Reynolds" }),
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue("Maria Reynolds")).toBeInTheDocument();

    await user.type(
      screen.getByLabelText("Decision note"),
      "SID verified the opponent bio and jersey number.",
    );
    await user.click(screen.getByRole("button", { name: "Create and resolve" }));

    expect(
      await screen.findByText(
        "Maria Reynolds was created and linked. Future ingests will use this identity.",
      ),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/identity-resolution/queue/10/create-player",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          display_name: "Maria Reynolds",
          resolution_notes: "SID verified the opponent bio and jersey number.",
        }),
      }),
    );
  });

  it("filters the full queue and moves between pages", async () => {
    fetchMock.mockImplementation(async (_input, init) => {
      if (init?.method === "GET") {
        return jsonResponse(queuePage([queueItem], 26));
      }
      return jsonResponse({});
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <IdentityQueuePage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Showing 1–25 of 26")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Season"), "2025-26");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/identity-resolution/queue/page?status=open&limit=25&offset=0&season=2025-26",
      expect.objectContaining({ method: "GET" }),
    );

    await user.selectOptions(
      screen.getByLabelText("Institution"),
      "University of Idaho",
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/identity-resolution/queue/page?status=open&limit=25&offset=0&season=2025-26&institution=University+of+Idaho",
      expect.objectContaining({ method: "GET" }),
    );

    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/identity-resolution/queue/page?status=open&limit=25&offset=25",
      expect.objectContaining({ method: "GET" }),
    );
  });
});
