import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import StyleGuidesPage from "../src/pages/StyleGuidesPage";
import type { StyleGuideVersion } from "../src/types/styleGuide";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const seed: StyleGuideVersion = {
  id: 1,
  guide_key: "athletics-default",
  version: 1,
  predecessor_version_id: null,
  name: "Vandals Athletics seed guide",
  scope_type: "shared_athletics",
  scope_value: null,
  instructions: "Use AP style and measured language.",
  rules: [
    {
      key: "headline-length",
      category: "length",
      severity: "error",
      enforcement: "headline_max_chars",
      value: 90,
      override: false,
      description: null,
    },
  ],
  content_hash: "a".repeat(64),
  lifecycle_state: "active",
  created_by: "system-seed",
  created_at: "2026-07-28T12:00:00Z",
  effective_at: "2026-07-28T12:00:00Z",
  activated_at: "2026-07-28T12:00:00Z",
  activated_by: "system-seed",
  retired_at: null,
  retired_by: null,
};

beforeEach(() => {
  let guides: StyleGuideVersion[] = [seed];
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.endsWith("/api/v1/style-guides") && method === "GET") {
      return jsonResponse(guides);
    }
    if (url.endsWith("/api/v1/style-guides/preview")) {
      return jsonResponse({
        sport: "womens-basketball",
        article_type: "game_recap",
        channel: null,
        versions: guides
          .filter((guide) => guide.lifecycle_state !== "retired")
          .map((guide) => ({
            id: guide.id,
            guide_key: guide.guide_key,
            version: guide.version,
            name: guide.name,
            scope_type: guide.scope_type,
            scope_value: guide.scope_value,
            content_hash: guide.content_hash,
          })),
        instructions: guides.map((guide) => guide.instructions),
        rules: [],
        style_hash: "b".repeat(64),
        valid_for_activation: true,
        issues: [],
      });
    }
    if (url.endsWith("/api/v1/style-guides/1/successors")) {
      const request = JSON.parse(String(init?.body));
      const successor: StyleGuideVersion = {
        ...seed,
        ...request,
        id: 2,
        version: 2,
        predecessor_version_id: 1,
        lifecycle_state: "draft",
        created_by: "style-user",
        created_at: "2026-07-29T12:00:00Z",
        effective_at: null,
        activated_at: null,
        activated_by: null,
        content_hash: "c".repeat(64),
      };
      guides = [successor, seed];
      return jsonResponse(successor, 201);
    }
    if (url.endsWith("/api/v1/style-guides/2/activate")) {
      const active = {
        ...guides[0],
        lifecycle_state: "active" as const,
        effective_at: "2026-07-29T12:05:00Z",
        activated_at: "2026-07-29T12:05:00Z",
        activated_by: "style-user",
      };
      guides = [
        active,
        {
          ...seed,
          lifecycle_state: "retired",
          retired_at: "2026-07-29T12:05:00Z",
          retired_by: "style-user",
        },
      ];
      return jsonResponse(active);
    }
    if (url.endsWith("/api/v1/style-guides") && method === "POST") {
      const request = JSON.parse(String(init?.body));
      const created: StyleGuideVersion = {
        ...seed,
        ...request,
        id: 3,
        version: 1,
        predecessor_version_id: null,
        lifecycle_state: "draft",
        created_by: "style-user",
        created_at: "2026-07-29T13:00:00Z",
        effective_at: null,
        activated_at: null,
        activated_by: null,
        content_hash: "d".repeat(64),
      };
      guides = [created, ...guides];
      return jsonResponse(created, 201);
    }
    return jsonResponse({ detail: `Unhandled ${method} ${url}` }, 500);
  });
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

describe("StyleGuidesPage", () => {
  it("previews resolution and completes the successor activation workflow", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <StyleGuidesPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Athletics Style Guides" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Shared athletics").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "Resolve preview" }));
    expect(await screen.findByText("Resolution is valid")).toBeInTheDocument();
    expect(screen.getByText("Ready to activate")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Create successor" }));
    expect(
      screen.getByRole("heading", { name: "Create v2" }),
    ).toBeInTheDocument();
    await user.clear(screen.getByLabelText("Guide name"));
    await user.type(screen.getByLabelText("Guide name"), "Vandals Athletics guide");
    await user.click(screen.getByRole("button", { name: "Save immutable draft" }));

    expect(
      await screen.findByText(
        "Vandals Athletics guide v2 is saved as an immutable draft.",
      ),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Activate version" }));
    expect(
      await screen.findByText(
        "Vandals Athletics guide v2 is active. Its prior active version was retired.",
      ),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/style-guides/2/activate",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("authors a new sport-scoped immutable draft", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <StyleGuidesPage />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", { name: "Athletics Style Guides" });

    await user.click(screen.getByRole("button", { name: "New scoped guide" }));
    await user.type(screen.getByLabelText("Stable guide key"), "wbb-editorial");
    await user.type(screen.getByLabelText("Guide name"), "WBB editorial guide");
    await user.selectOptions(screen.getByLabelText("Scope"), "sport");
    await user.type(screen.getByLabelText("Scope value"), "womens-basketball");
    await user.type(
      screen.getByLabelText("Writer instructions"),
      "Use approved women's basketball terminology.",
    );
    await user.type(screen.getByLabelText("Stable key"), "measured-voice");
    await user.type(screen.getByLabelText("Value"), "Keep the voice measured.");
    await user.click(screen.getByRole("button", { name: "Save immutable draft" }));

    expect(
      await screen.findByText(
        "WBB editorial guide v1 is saved as an immutable draft.",
      ),
    ).toBeInTheDocument();
    const createCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/api/v1/style-guides") && init?.method === "POST",
    );
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      guide_key: "wbb-editorial",
      scope_type: "sport",
      scope_value: "womens-basketball",
    });
  });
});
