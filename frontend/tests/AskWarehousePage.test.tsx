import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AskWarehousePage from "../src/pages/AskWarehousePage";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), { ...init, headers });
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("localStorage", { getItem: vi.fn(() => null) });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AskWarehousePage", () => {
  it("shows the answer, selected query, and underlying warehouse result", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        status: "answered",
        question: "What was Idaho's record in 2025-26?",
        answer: "Idaho won 2 games and lost 1 in 2025-26.",
        query_id: "team_season_record",
        query: {
          query_id: "team_season_record",
          season: "2025-26",
          conference_scope: "all",
        },
        result: {
          query_id: "team_season_record",
          result: { games_played: 3, wins: 2, losses: 1 },
        },
        model: "qwen/qwen3.6-27b",
        prompt_version: "semantic-question-v1",
      }),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AskWarehousePage />
      </MemoryRouter>,
    );

    await user.click(
      screen.getByRole("button", {
        name: "What was Idaho's record in 2025-26?",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Ask question" }));

    expect(
      await screen.findByText("Idaho won 2 games and lost 1 in 2025-26."),
    ).toBeInTheDocument();
    expect(screen.getByText("Verified answer")).toBeInTheDocument();
    expect(screen.getByText("team_season_record")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/semantic-queries/ask",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          question: "What was Idaho's record in 2025-26?",
        }),
      }),
    );

    await user.click(
      screen.getByText("View underlying warehouse result"),
    );
    expect(screen.getByText(/"games_played": 3/)).toBeInTheDocument();
  });

  it("shows an honest outside-catalog result without evidence", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        status: "unanswerable",
        question: "Which players are injured?",
        answer: "The verified catalog does not include injury reports.",
        query_id: null,
        query: null,
        result: null,
        model: "qwen/qwen3.6-27b",
        prompt_version: "semantic-question-v1",
      }),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AskWarehousePage />
      </MemoryRouter>,
    );

    await user.type(
      screen.getByLabelText("What do you need to know?"),
      "Which players are injured?",
    );
    await user.click(screen.getByRole("button", { name: "Ask question" }));

    expect(await screen.findByText("Outside catalog")).toBeInTheDocument();
    expect(
      screen.getByText("The verified catalog does not include injury reports."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Evidence trail")).not.toBeInTheDocument();
  });

  it("shows API errors and keeps the question available", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: "AI service unavailable" }, { status: 502 }),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AskWarehousePage />
      </MemoryRouter>,
    );

    const input = screen.getByLabelText("What do you need to know?");
    await user.type(input, "Who led Idaho in points?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "AI service unavailable",
    );
    await waitFor(() => expect(input).toHaveValue("Who led Idaho in points?"));
  });
});
