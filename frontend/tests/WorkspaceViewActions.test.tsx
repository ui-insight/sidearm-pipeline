import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  createSharedWorkspaceView,
  deleteSharedWorkspaceView,
  listSharedWorkspaceViews,
  type SharedWorkspaceView,
} from "../src/api/workspaceViews";
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

vi.mock("../src/api/workspaceViews", () => ({
  listSharedWorkspaceViews: vi.fn(),
  createSharedWorkspaceView: vi.fn(),
  deleteSharedWorkspaceView: vi.fn(),
}));

const listSharedViewsMock = vi.mocked(listSharedWorkspaceViews);
const createSharedViewMock = vi.mocked(createSharedWorkspaceView);
const deleteSharedViewMock = vi.mocked(deleteSharedWorkspaceView);

const sharedView: SharedWorkspaceView = {
  id: "shared-1",
  name: "Deadline handoff",
  view: "season",
  params: {
    season: "2025-26",
    stat: "points",
    scope: "conference",
    opponent: "all",
    limit: "10",
  },
  created_by: "prototype-user",
  created_at: "2026-07-17T18:00:00Z",
};

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
  vi.clearAllMocks();
  vi.stubGlobal("localStorage", createMemoryStorage());
  clipboardWriteMock.mockResolvedValue();
  listSharedViewsMock.mockResolvedValue([]);
  deleteSharedViewMock.mockResolvedValue();
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
            opponent: "all",
            limit: "10",
          }}
        />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Share link" }));

    expect(clipboardWriteMock).toHaveBeenCalledOnce();
    expect(clipboardWriteMock.mock.calls[0]?.[0]).toMatch(
      /\/workspace\?season=2025-26&stat=points&scope=conference&opponent=all&limit=10$/,
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

    expect(await screen.findByText(/shared views are available/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save view" }));
    expect(screen.getByRole("textbox", { name: "View name" })).toBeVisible();
    await user.selectOptions(screen.getByLabelText("Save to"), "local");
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
    expect(screen.getByLabelText("Saved views")).toHaveValue(
      `local:${stored[0]?.id}`,
    );

    await user.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.getByLabelText("Current location")).toHaveTextContent(
      "/workspace/compare?season=2025-26&stat=points&conference=all&venue=home&opponent=all&left=4&right=8",
    );

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(loadSavedWorkspaceViews()).toEqual([]);
    expect(
      screen.queryByLabelText("Saved views"),
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

  it("saves a deployment-wide view and identifies it as shared", async () => {
    const user = userEvent.setup();
    createSharedViewMock.mockResolvedValue(sharedView);
    render(
      <MemoryRouter>
        <WorkspaceViewActions view="season" params={sharedView.params} />
      </MemoryRouter>,
    );

    await screen.findByText(/shared views are available/i);
    await user.click(screen.getByRole("button", { name: "Save view" }));
    await user.type(screen.getByLabelText("View name"), "Deadline handoff");
    await user.click(screen.getByRole("button", { name: "Save", exact: true }));

    expect(createSharedViewMock).toHaveBeenCalledWith({
      name: "Deadline handoff",
      view: "season",
      params: sharedView.params,
    });
    expect(await screen.findByLabelText("Saved views")).toHaveValue(
      "shared:shared-1",
    );
    expect(
      screen.getByText("Shared view saved for everyone signed in."),
    ).toBeInTheDocument();
    expect(screen.getByText(/shared by prototype-user/i)).toBeInTheDocument();
  });

  it("keeps a new shared save when the initial list resolves afterward", async () => {
    const user = userEvent.setup();
    let resolveInitialList: (views: SharedWorkspaceView[]) => void = () => {};
    listSharedViewsMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveInitialList = resolve;
        }),
    );
    createSharedViewMock.mockResolvedValue(sharedView);
    render(
      <MemoryRouter>
        <WorkspaceViewActions view="season" params={sharedView.params} />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Save view" }));
    await user.type(screen.getByLabelText("View name"), "Deadline handoff");
    await user.click(screen.getByRole("button", { name: "Save", exact: true }));
    expect(await screen.findByLabelText("Saved views")).toHaveValue(
      "shared:shared-1",
    );

    resolveInitialList([{ ...sharedView, id: "shared-older", name: "Older view" }]);

    expect(
      await screen.findByRole("option", { name: "Season: Older view" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Saved views")).toHaveValue("shared:shared-1");
  });

  it("requires inline confirmation before deleting a shared view", async () => {
    const user = userEvent.setup();
    listSharedViewsMock.mockResolvedValue([sharedView]);
    render(
      <MemoryRouter>
        <WorkspaceViewActions view="season" params={sharedView.params} />
      </MemoryRouter>,
    );

    const chooser = await screen.findByLabelText("Saved views");
    await user.selectOptions(chooser, "shared:shared-1");
    expect(screen.getByText(/deleting removes it for everyone/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(deleteSharedViewMock).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "Confirm delete" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/delete deadline handoff for everyone/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(deleteSharedViewMock).toHaveBeenCalledWith("shared-1");
    expect(
      await screen.findByText("Deleted shared view Deadline handoff."),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Saved views")).not.toBeInTheDocument();
  });

  it("falls back to browser storage when shared views are unavailable", async () => {
    const user = userEvent.setup();
    listSharedViewsMock.mockRejectedValue(new Error("offline"));
    render(
      <MemoryRouter>
        <WorkspaceViewActions view="season" params={sharedView.params} />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(/browser-local views still work/i),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save view" }));
    expect(screen.getByLabelText("Save to")).toHaveValue("local");
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
