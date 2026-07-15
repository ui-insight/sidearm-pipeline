import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
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

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (input, init) => {
    const endpoint = String(input);
    if (
      endpoint === "/api/v1/identity-resolution/queue?status=open" &&
      init?.method === "GET"
    ) {
      return jsonResponse([queueItem]);
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
    expect(screen.getByText("University of Idaho")).toBeInTheDocument();
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
});
