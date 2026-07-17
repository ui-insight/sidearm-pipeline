import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import WorkspaceViewActions from "../src/components/WorkspaceViewActions";
import {
  MAX_SAVED_WORKSPACE_VIEWS,
  SAVED_WORKSPACE_VIEWS_KEY,
  createSavedWorkspaceView,
  loadSavedWorkspaceViews,
  storeSavedWorkspaceViews,
  type SavedWorkspaceView,
} from "../src/utils/savedWorkspaceViews";

const clipboardWriteMock = vi.fn<(text: string) => Promise<void>>();

function createMemoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => Array.from(values.keys())[index] ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, value),
  };
}

function LocationProbe() {
  const location = useLocation();
  return (
    <output aria-label="Current location">
      {location.pathname}
      {location.search}
    </output>
  );
}

beforeEach(() => {
  vi.stubGlobal("localStorage", createMemoryStorage());
  clipboardWriteMock.mockReset();
  clipboardWriteMock.mockResolvedValue();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("WorkspaceViewActions", () => {
  it("copies the complete canonical view URL", async () => {
    const user = userEvent.setup();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: clipboardWriteMock },
    });
    render(
      <MemoryRouter initialEntries={["/workspace"]}>
        <WorkspaceViewActions
          view="season"
          params={{
            season: "2025-26",
            stat: "points",
            scope: "conference",
            limit: "10",
          }}
        />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Share link" }));

    expect(clipboardWriteMock).toHaveBeenCalledOnce();
    expect(clipboardWriteMock.mock.calls[0]?.[0]).toMatch(
      /\/workspace\?season=2025-26&stat=points&scope=conference&limit=10$/,
    );
    expect(screen.getByText("Share link copied.")).toBeInTheDocument();
  });

  it("saves, opens, and deletes a browser-local view without a modal", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/workspace/compare"]}>
        <WorkspaceViewActions
          view="comparison"
          params={{
            season: "2025-26",
            stat: "points",
            conference: "all",
            venue: "home",
            opponent: "all",
            left: "4",
            right: "8",
          }}
        />
        <LocationProbe />
      </MemoryRouter>,
    );

    expect(
      screen.getByText(/saved views stay in this browser/i),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save view" }));
    expect(screen.getByRole("textbox", { name: "View name" })).toBeVisible();
    await user.type(
      screen.getByRole("textbox", { name: "View name" }),
      "Home points check",
    );
    await user.click(screen.getByRole("button", { name: "Save", exact: true }));

    const stored = loadSavedWorkspaceViews();
    expect(stored).toHaveLength(1);
    expect(stored[0]).toMatchObject({
      name: "Home points check",
      view: "comparison",
      params: { venue: "home", opponent: "all", left: "4", right: "8" },
    });
    expect(screen.getByLabelText("Saved in this browser")).toHaveValue(
      stored[0]?.id,
    );

    await user.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.getByLabelText("Current location")).toHaveTextContent(
      "/workspace/compare?season=2025-26&stat=points&conference=all&venue=home&opponent=all&left=4&right=8",
    );

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(loadSavedWorkspaceViews()).toEqual([]);
    expect(
      screen.queryByLabelText("Saved in this browser"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Deleted Home points check.")).toBeInTheDocument();
  });

  it("rejects an empty saved-view name inline", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <WorkspaceViewActions view="season" params={{ season: "2025-26" }} />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Save view" }));
    await user.click(screen.getByRole("button", { name: "Save", exact: true }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter a view name between 1 and 60 characters.",
    );
    expect(loadSavedWorkspaceViews()).toEqual([]);
  });
});

describe("saved workspace storage", () => {
  it("keeps comparison views saved before opponent filtering was added", () => {
    localStorage.setItem(
      SAVED_WORKSPACE_VIEWS_KEY,
      JSON.stringify([
        {
          id: "legacy-comparison",
          name: "Legacy comparison",
          view: "comparison",
          params: {
            season: "2025-26",
            stat: "points",
            conference: "all",
            venue: "all",
            left: "4",
            right: "8",
          },
          created_at: "2026-07-17T18:00:00Z",
        },
      ]),
    );

    expect(loadSavedWorkspaceViews()).toMatchObject([
      { id: "legacy-comparison" },
    ]);
  });

  it("rejects incomplete filter configurations before persisting them", () => {
    expect(() =>
      createSavedWorkspaceView(
        "Incomplete",
        "season",
        { season: "2025-26" },
        [],
      ),
    ).toThrow("The workspace view contains invalid filters.");
    expect(loadSavedWorkspaceViews()).toEqual([]);
  });

  it("ignores malformed entries and caps persisted views", () => {
    localStorage.setItem(
      SAVED_WORKSPACE_VIEWS_KEY,
      JSON.stringify([
        { id: 1, name: "Bad id", view: "season", params: {} },
        {
          id: "valid",
          name: "Valid view",
          view: "season",
          params: {
            season: "2025-26",
            stat: "points",
            scope: "all",
            limit: "10",
          },
          created_at: "2026-07-17T18:00:00Z",
        },
        {
          id: "unknown-filter",
          name: "Unknown filter",
          view: "season",
          params: {
            season: "2025-26",
            stat: "points",
            scope: "all",
            limit: "10",
            admin: "true",
          },
          created_at: "2026-07-17T18:00:00Z",
        },
      ]),
    );
    expect(loadSavedWorkspaceViews()).toMatchObject([{ id: "valid" }]);

    const views: SavedWorkspaceView[] = Array.from(
      { length: MAX_SAVED_WORKSPACE_VIEWS + 5 },
      (_, index) => ({
        id: String(index),
        name: `View ${index}`,
        view: "season",
        params: {
          season: "2025-26",
          stat: "points",
          scope: "all",
          limit: "10",
        },
        created_at: "2026-07-17T18:00:00Z",
      }),
    );
    expect(storeSavedWorkspaceViews(views)).toHaveLength(
      MAX_SAVED_WORKSPACE_VIEWS,
    );
  });
});
