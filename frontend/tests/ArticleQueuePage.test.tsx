import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ArticleQueuePage from "../src/pages/ArticleQueuePage";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
}

const version = {
  id: 900,
  article_id: 401,
  version: 2,
  origin: "human",
  parent_version_id: 899,
  headline: "Avery Adams records 31 points since 2023-24",
  headline_evidence_ids: ["achievement-suggestion:17"],
  body: "Avery Adams set a career high with 31 points since 2023-24.",
  blocks: [
    {
      kind: "lead",
      text: "Avery Adams set a career high with 31 points since 2023-24.",
      evidence_ids: ["achievement-suggestion:17"],
    },
  ],
  evidence_bundle_id: 700,
  evidence_hash: "a".repeat(64),
  style_guide_version_id: 5,
  style_snapshot: {},
  style_hash: "b".repeat(64),
  prompt_version: null,
  editor_instructions: null,
  provider: null,
  model: null,
  output_hash: "c".repeat(64),
  validation_results: [],
  author: "sid-user",
  created_at: "2026-07-28T18:00:00Z",
  warning_overrides: [],
};

const queue = {
  total: 2,
  items: [
    {
      id: 401,
      status: "in_edit",
      article_type: "achievement_story",
      angle: "Lead with the verified career high.",
      owner: "sid-user",
      created_at: "2026-07-28T17:00:00Z",
      game_date: "2025-12-01",
      game_title: "Idaho at Montana State",
      latest_version: version,
      ready_version: null,
    },
    {
      id: 402,
      status: "ready",
      article_type: "game_recap",
      angle: "Idaho closes the game with a road win.",
      owner: "sid-user",
      created_at: "2026-07-28T16:00:00Z",
      game_date: "2025-11-20",
      game_title: "Idaho at Washington State",
      latest_version: { ...version, id: 901, article_id: 402 },
      ready_version: { ...version, id: 901, article_id: 402 },
    },
  ],
};

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(jsonResponse(queue));
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("localStorage", {
    getItem: vi.fn(() => null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ArticleQueuePage", () => {
  it("shows active Article ownership and version state by default", async () => {
    render(
      <MemoryRouter>
        <ArticleQueuePage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Article desk" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Lead with the verified career high." }),
    ).toHaveAttribute("href", "/articles/401");
    expect(screen.getByText("sid-user")).toBeInTheDocument();
    expect(screen.getByText("v2")).toBeInTheDocument();
    expect(
      screen.queryByText("Idaho closes the game with a road win."),
    ).not.toBeInTheDocument();
  });

  it("filters the queue to ready Articles", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ArticleQueuePage />
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole("button", { name: "ready" }));
    expect(
      screen.getByRole("link", {
        name: "Idaho closes the game with a road win.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("v2 ready")).toBeInTheDocument();
  });
});
