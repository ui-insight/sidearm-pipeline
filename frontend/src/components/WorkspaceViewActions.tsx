import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import {
  createSharedWorkspaceView,
  deleteSharedWorkspaceView,
  listSharedWorkspaceViews,
  type SharedWorkspaceView,
} from "../api/workspaceViews";
import {
  buildWorkspaceViewUrl,
  createSavedWorkspaceView,
  deleteSavedWorkspaceView,
  loadSavedWorkspaceViews,
  workspaceViewPath,
  type SavedWorkspaceView,
  type WorkspaceViewKind,
} from "../utils/savedWorkspaceViews";

interface WorkspaceViewActionsProps {
  view: WorkspaceViewKind;
  params: Record<string, string>;
}

type SaveTarget = "shared" | "local";
type SharedLoadState = "loading" | "ready" | "unavailable";
const MAX_SHARED_WORKSPACE_VIEWS = 100;

function formatSavedDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(new Date(value));
}

function WorkspaceViewActions({ view, params }: WorkspaceViewActionsProps) {
  const navigate = useNavigate();
  const [localViews, setLocalViews] = useState<SavedWorkspaceView[]>(() =>
    loadSavedWorkspaceViews(),
  );
  const [sharedViews, setSharedViews] = useState<SharedWorkspaceView[]>([]);
  const [sharedLoadState, setSharedLoadState] =
    useState<SharedLoadState>("loading");
  const [selectedKey, setSelectedKey] = useState("");
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [viewName, setViewName] = useState("");
  const [saveTarget, setSaveTarget] = useState<SaveTarget>("shared");
  const [status, setStatus] = useState("");
  const [saveError, setSaveError] = useState("");
  const [savePending, setSavePending] = useState(false);
  const [deletePending, setDeletePending] = useState(false);
  const [confirmSharedDelete, setConfirmSharedDelete] = useState(false);

  useEffect(() => {
    let active = true;

    void listSharedWorkspaceViews()
      .then((views) => {
        if (!active) return;
        setSharedViews((current) => {
          const loadedIds = new Set(views.map((saved) => saved.id));
          return [
            ...current.filter((saved) => !loadedIds.has(saved.id)),
            ...views,
          ].slice(0, MAX_SHARED_WORKSPACE_VIEWS);
        });
        setSharedLoadState("ready");
      })
      .catch(() => {
        if (!active) return;
        setSharedLoadState("unavailable");
        setSaveTarget("local");
      });

    return () => {
      active = false;
    };
  }, []);

  const selectedSharedView = sharedViews.find(
    (saved) => `shared:${saved.id}` === selectedKey,
  );
  const selectedLocalView = localViews.find(
    (saved) => `local:${saved.id}` === selectedKey,
  );
  const selectedView = selectedSharedView ?? selectedLocalView;
  const hasSavedViews = sharedViews.length > 0 || localViews.length > 0;

  async function copyShareLink() {
    const shareUrl = buildWorkspaceViewUrl(view, params, window.location.origin);
    try {
      if (!navigator.clipboard) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(shareUrl);
      setStatus("Share link copied.");
    } catch {
      setStatus("Share link could not be copied.");
    }
  }

  async function saveCurrentView(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaveError("");
    const trimmedName = viewName.trim();
    if (!trimmedName || trimmedName.length > 60) {
      setSaveError("Enter a view name between 1 and 60 characters.");
      return;
    }

    if (saveTarget === "shared") {
      setSavePending(true);
      try {
        const saved = await createSharedWorkspaceView({
          name: trimmedName,
          view,
          params,
        });
        setSharedViews((current) =>
          [
            saved,
            ...current.filter((item) => item.id !== saved.id),
          ].slice(0, MAX_SHARED_WORKSPACE_VIEWS),
        );
        setSelectedKey(`shared:${saved.id}`);
        setViewName("");
        setShowSaveForm(false);
        setStatus("Shared view saved for everyone signed in.");
      } catch {
        setSaveError(
          "The shared view could not be saved. Choose This browser to keep a local copy.",
        );
      } finally {
        setSavePending(false);
      }
      return;
    }

    try {
      const next = createSavedWorkspaceView(
        trimmedName,
        view,
        params,
        localViews,
      );
      setLocalViews(next);
      setSelectedKey(`local:${next[0]?.id ?? ""}`);
      setViewName("");
      setShowSaveForm(false);
      setStatus("View saved in this browser.");
    } catch (error) {
      setSaveError(
        error instanceof Error ? error.message : "The view could not be saved.",
      );
    }
  }

  function openSelectedView() {
    if (!selectedView) return;
    const search = new URLSearchParams(selectedView.params).toString();
    navigate(
      `${workspaceViewPath(selectedView.view)}${search ? `?${search}` : ""}`,
    );
  }

  async function removeSelectedView() {
    if (!selectedView) return;

    if (selectedSharedView) {
      if (!confirmSharedDelete) {
        setConfirmSharedDelete(true);
        setStatus(
          `Delete ${selectedSharedView.name} for everyone? Select Confirm delete to continue.`,
        );
        return;
      }

      setDeletePending(true);
      try {
        await deleteSharedWorkspaceView(selectedSharedView.id);
        setSharedViews((current) =>
          current.filter((saved) => saved.id !== selectedSharedView.id),
        );
        setSelectedKey("");
        setConfirmSharedDelete(false);
        setStatus(`Deleted shared view ${selectedSharedView.name}.`);
      } catch {
        setConfirmSharedDelete(false);
        setStatus("The shared view could not be deleted.");
      } finally {
        setDeletePending(false);
      }
      return;
    }

    try {
      setLocalViews(deleteSavedWorkspaceView(selectedView.id, localViews));
      setSelectedKey("");
      setStatus(`Deleted ${selectedView.name}.`);
    } catch {
      setStatus("The saved view could not be deleted.");
    }
  }

  function selectionDescription(): string {
    if (selectedSharedView) {
      return `Shared by ${selectedSharedView.created_by} on ${formatSavedDate(
        selectedSharedView.created_at,
      )}. Deleting removes it for everyone signed in.`;
    }
    if (selectedLocalView) return "Stored only in this browser.";
    if (sharedLoadState === "loading") return "Loading shared views...";
    if (sharedLoadState === "unavailable") {
      return "Shared views are unavailable. Browser-local views still work.";
    }
    return "Shared views are available to everyone signed in.";
  }

  return (
    <section
      aria-label="Workspace view actions"
      className="border-b border-gray-200 py-4"
    >
      <div className="grid grid-cols-2 gap-3 sm:flex sm:flex-wrap sm:items-end">
        <button
          type="button"
          onClick={() => void copyShareLink()}
          className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-bold text-gray-700 hover:border-gray-500 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
        >
          Share link
        </button>
        <button
          type="button"
          onClick={() => {
            setShowSaveForm((visible) => !visible);
            setSaveError("");
          }}
          aria-expanded={showSaveForm}
          className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-bold text-gray-700 hover:border-gray-500 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
        >
          Save view
        </button>

        {hasSavedViews ? (
          <div className="col-span-2 grid w-full grid-cols-2 gap-2 sm:ml-auto sm:flex sm:min-w-0 sm:flex-1 sm:flex-wrap sm:items-end sm:justify-end">
            <div className="col-span-2 min-w-0 sm:min-w-52 sm:flex-1 sm:max-w-sm">
              <label className="block text-xs font-bold uppercase tracking-[0.06em] text-gray-600">
                Saved views
                <select
                  value={selectedKey}
                  onChange={(event) => {
                    setSelectedKey(event.target.value);
                    setConfirmSharedDelete(false);
                    setStatus("");
                  }}
                  className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-gray-950 focus:border-yellow-500 focus:outline-2 focus:outline-offset-1 focus:outline-yellow-500"
                >
                  <option value="">Choose a saved view</option>
                  {sharedViews.length > 0 ? (
                    <optgroup label="Shared workspace">
                      {sharedViews.map((saved) => (
                        <option key={saved.id} value={`shared:${saved.id}`}>
                          {saved.view === "season" ? "Season" : "Comparison"}: {saved.name}
                        </option>
                      ))}
                    </optgroup>
                  ) : null}
                  {localViews.length > 0 ? (
                    <optgroup label="This browser">
                      {localViews.map((saved) => (
                        <option key={saved.id} value={`local:${saved.id}`}>
                          {saved.view === "season" ? "Season" : "Comparison"}: {saved.name}
                        </option>
                      ))}
                    </optgroup>
                  ) : null}
                </select>
              </label>
              <p className="mt-1 text-xs leading-5 text-gray-500">
                {selectionDescription()}
              </p>
            </div>
            <button
              type="button"
              onClick={openSelectedView}
              disabled={!selectedView || deletePending}
              className="rounded-md bg-gray-950 px-3 py-2 text-sm font-bold text-white hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:bg-gray-300 disabled:text-gray-500"
            >
              Open
            </button>
            <button
              type="button"
              onClick={() => void removeSelectedView()}
              disabled={!selectedView || deletePending}
              className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-bold text-gray-600 hover:border-red-300 hover:text-red-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:text-gray-300"
            >
              {deletePending
                ? "Deleting..."
                : selectedSharedView && confirmSharedDelete
                  ? "Confirm delete"
                  : "Delete"}
            </button>
          </div>
        ) : (
          <p className="col-span-2 text-xs leading-5 text-gray-500">
            {selectionDescription()}
          </p>
        )}
      </div>

      {showSaveForm ? (
        <form
          onSubmit={(event) => void saveCurrentView(event)}
          className="mt-4 flex flex-col gap-2 border-t border-gray-200 pt-4 sm:flex-row sm:items-end"
        >
          <label className="flex-1 text-xs font-bold uppercase tracking-[0.06em] text-gray-600 sm:max-w-sm">
            View name
            <input
              value={viewName}
              onChange={(event) => setViewName(event.target.value)}
              maxLength={60}
              autoFocus
              aria-describedby={saveError ? "save-view-error" : undefined}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-gray-950 focus:border-yellow-500 focus:outline-2 focus:outline-offset-1 focus:outline-yellow-500"
            />
          </label>
          <label className="text-xs font-bold uppercase tracking-[0.06em] text-gray-600">
            Save to
            <select
              value={saveTarget}
              onChange={(event) =>
                setSaveTarget(event.target.value as SaveTarget)
              }
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-gray-950 focus:border-yellow-500 focus:outline-2 focus:outline-offset-1 focus:outline-yellow-500"
            >
              <option
                value="shared"
                disabled={sharedLoadState === "unavailable"}
              >
                Shared workspace
              </option>
              <option value="local">This browser</option>
            </select>
          </label>
          <button
            type="submit"
            disabled={savePending}
            className="rounded-md bg-gray-950 px-3 py-2 text-sm font-bold text-white hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-wait disabled:bg-gray-400"
          >
            {savePending ? "Saving..." : "Save"}
          </button>
          <button
            type="button"
            onClick={() => {
              setShowSaveForm(false);
              setViewName("");
              setSaveError("");
            }}
            disabled={savePending}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-bold text-gray-600 hover:border-gray-500 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:text-gray-300"
          >
            Cancel
          </button>
          {saveError ? (
            <p id="save-view-error" role="alert" className="text-sm text-red-800">
              {saveError}
            </p>
          ) : null}
        </form>
      ) : null}

      <p aria-live="polite" className="mt-2 min-h-5 text-xs text-gray-500">
        {status}
      </p>
    </section>
  );
}

export default WorkspaceViewActions;
