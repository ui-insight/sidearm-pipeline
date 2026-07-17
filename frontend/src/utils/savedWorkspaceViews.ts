export type WorkspaceViewKind = "season" | "comparison";

export interface SavedWorkspaceView {
  id: string;
  name: string;
  view: WorkspaceViewKind;
  params: Record<string, string>;
  created_at: string;
}

export const SAVED_WORKSPACE_VIEWS_KEY =
  "vandals.workspace.savedViews.v1";
export const MAX_SAVED_WORKSPACE_VIEWS = 20;

const WORKSPACE_VIEW_PARAM_KEYS: Record<WorkspaceViewKind, readonly string[]> = {
  season: ["season", "stat", "scope", "opponent", "limit"],
  comparison: [
    "season",
    "stat",
    "conference",
    "venue",
    "opponent",
    "left",
    "right",
  ],
};

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isWorkspaceView(value: unknown): value is SavedWorkspaceView {
  if (!isObject(value) || !isObject(value.params)) return false;
  if (
    typeof value.id !== "string" ||
    value.id.length === 0 ||
    value.id.length > 80 ||
    typeof value.name !== "string" ||
    value.name.trim().length === 0 ||
    value.name.length > 60 ||
    (value.view !== "season" && value.view !== "comparison") ||
    typeof value.created_at !== "string" ||
    value.created_at.length > 40 ||
    Number.isNaN(Date.parse(value.created_at))
  ) {
    return false;
  }
  const allowedKeys = WORKSPACE_VIEW_PARAM_KEYS[value.view];
  const requiredKeys = allowedKeys.filter(
    (key) => key !== "opponent",
  );
  const paramEntries = Object.entries(value.params);
  return (
    paramEntries.length >= requiredKeys.length &&
    paramEntries.length <= allowedKeys.length &&
    requiredKeys.every((key) =>
      Object.prototype.hasOwnProperty.call(value.params, key),
    ) &&
    paramEntries.every(
      ([key, param]) =>
        allowedKeys.includes(key) &&
        typeof param === "string" &&
        param.length > 0 &&
        param.length <= 160,
    )
  );
}

export function loadSavedWorkspaceViews(
  storage: Pick<Storage, "getItem"> = localStorage,
): SavedWorkspaceView[] {
  try {
    const stored = storage.getItem(SAVED_WORKSPACE_VIEWS_KEY);
    if (!stored) return [];
    const parsed: unknown = JSON.parse(stored);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isWorkspaceView).slice(0, MAX_SAVED_WORKSPACE_VIEWS);
  } catch {
    return [];
  }
}

export function storeSavedWorkspaceViews(
  views: SavedWorkspaceView[],
  storage: Pick<Storage, "setItem"> = localStorage,
): SavedWorkspaceView[] {
  const bounded = views
    .filter(isWorkspaceView)
    .slice(0, MAX_SAVED_WORKSPACE_VIEWS);
  storage.setItem(SAVED_WORKSPACE_VIEWS_KEY, JSON.stringify(bounded));
  return bounded;
}

export function createSavedWorkspaceView(
  name: string,
  view: WorkspaceViewKind,
  params: Record<string, string>,
  existing: SavedWorkspaceView[],
  storage: Pick<Storage, "setItem"> = localStorage,
): SavedWorkspaceView[] {
  const trimmedName = name.trim();
  if (!trimmedName || trimmedName.length > 60) {
    throw new Error("Enter a view name between 1 and 60 characters.");
  }
  const nextView: SavedWorkspaceView = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
    name: trimmedName,
    view,
    params: { ...params },
    created_at: new Date().toISOString(),
  };
  if (
    !isWorkspaceView(nextView) ||
    Object.keys(params).length !== WORKSPACE_VIEW_PARAM_KEYS[view].length
  ) {
    throw new Error("The workspace view contains invalid filters.");
  }
  return storeSavedWorkspaceViews([nextView, ...existing], storage);
}

export function deleteSavedWorkspaceView(
  id: string,
  existing: SavedWorkspaceView[],
  storage: Pick<Storage, "setItem"> = localStorage,
): SavedWorkspaceView[] {
  return storeSavedWorkspaceViews(
    existing.filter((view) => view.id !== id),
    storage,
  );
}

export function workspaceViewPath(view: WorkspaceViewKind): string {
  return view === "season" ? "/workspace" : "/workspace/compare";
}

export function buildWorkspaceViewUrl(
  view: WorkspaceViewKind,
  params: Record<string, string>,
  origin: string,
): string {
  const search = new URLSearchParams(params).toString();
  return `${origin}${workspaceViewPath(view)}${search ? `?${search}` : ""}`;
}
