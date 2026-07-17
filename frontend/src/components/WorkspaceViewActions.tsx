import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
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

function WorkspaceViewActions({ view, params }: WorkspaceViewActionsProps) {
  const navigate = useNavigate();
  const [savedViews, setSavedViews] = useState<SavedWorkspaceView[]>(() =>
    loadSavedWorkspaceViews(),
  );
  const [selectedId, setSelectedId] = useState("");
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [viewName, setViewName] = useState("");
  const [status, setStatus] = useState("");
  const [saveError, setSaveError] = useState("");

  const selectedView = savedViews.find((saved) => saved.id === selectedId);

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

  function saveCurrentView(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaveError("");
    try {
      const next = createSavedWorkspaceView(
        viewName,
        view,
        params,
        savedViews,
      );
      setSavedViews(next);
      setSelectedId(next[0]?.id ?? "");
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

  function removeSelectedView() {
    if (!selectedView) return;
    try {
      setSavedViews(deleteSavedWorkspaceView(selectedView.id, savedViews));
      setSelectedId("");
      setStatus(`Deleted ${selectedView.name}.`);
    } catch {
      setStatus("The saved view could not be deleted.");
    }
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

        {savedViews.length > 0 ? (
          <div className="col-span-2 grid w-full grid-cols-2 gap-2 sm:ml-auto sm:flex sm:min-w-0 sm:flex-1 sm:flex-wrap sm:items-end sm:justify-end">
            <div className="col-span-2 min-w-0 sm:min-w-52 sm:flex-1 sm:max-w-xs">
              <label className="block text-xs font-bold uppercase tracking-[0.06em] text-gray-600">
                Saved in this browser
                <select
                  value={selectedId}
                  onChange={(event) => setSelectedId(event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-gray-950 focus:border-yellow-500 focus:outline-2 focus:outline-offset-1 focus:outline-yellow-500"
                >
                  <option value="">Choose a saved view</option>
                  {savedViews.map((saved) => (
                    <option key={saved.id} value={saved.id}>
                      {saved.view === "season" ? "Season" : "Comparison"}: {saved.name}
                    </option>
                  ))}
                </select>
              </label>
              <p className="mt-1 text-xs text-gray-500">
                Stored only here, not account-synced.
              </p>
            </div>
            <button
              type="button"
              onClick={openSelectedView}
              disabled={!selectedView}
              className="rounded-md bg-gray-950 px-3 py-2 text-sm font-bold text-white hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:bg-gray-300 disabled:text-gray-500"
            >
              Open
            </button>
            <button
              type="button"
              onClick={removeSelectedView}
              disabled={!selectedView}
              className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-bold text-gray-600 hover:border-red-300 hover:text-red-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:text-gray-300"
            >
              Delete
            </button>
          </div>
        ) : (
          <p className="col-span-2 text-xs leading-5 text-gray-500">
            Saved views stay in this browser and are not account-synced.
          </p>
        )}
      </div>

      {showSaveForm ? (
        <form
          onSubmit={saveCurrentView}
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
          <button
            type="submit"
            className="rounded-md bg-gray-950 px-3 py-2 text-sm font-bold text-white hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
          >
            Save
          </button>
          <button
            type="button"
            onClick={() => {
              setShowSaveForm(false);
              setViewName("");
              setSaveError("");
            }}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-bold text-gray-600 hover:border-gray-500 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
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
