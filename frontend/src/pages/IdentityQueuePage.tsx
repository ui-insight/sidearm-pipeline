import { useEffect, useState } from "react";
import { Link } from "react-router";
import { ApiError } from "../api/client";
import { identityResolutionApi } from "../api/identityResolution";
import type {
  IdentityQueueItem,
  IdentityQueueStatus,
} from "../types/identityResolution";

const PAGE_SIZE = 25;

const STATUS_OPTIONS: { value: IdentityQueueStatus; label: string }[] = [
  { value: "open", label: "Open review" },
  { value: "resolved", label: "Resolved" },
];

function detailText(item: IdentityQueueItem, key: string): string | null {
  const value = item.details[key];
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number") return String(value);
  return null;
}

function displayPlayerName(item: IdentityQueueItem): string {
  const sourceName = detailText(item, "player_name") ?? "Unnamed source row";
  if (!sourceName.includes(",")) return sourceName;
  const [lastName, ...rest] = sourceName.split(",");
  return `${rest.join(",").trim()} ${(lastName ?? "").trim()}`.trim();
}

function formatDetectedAt(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.data === "object" && error.data && "detail" in error.data) {
      return String(error.data.detail);
    }
    return error.message;
  }
  return error instanceof Error ? error.message : "The review queue could not be loaded.";
}

function IdentityQueuePage() {
  const [status, setStatus] = useState<IdentityQueueStatus>("open");
  const [items, setItems] = useState<IdentityQueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [season, setSeason] = useState("");
  const [institution, setInstitution] = useState("");
  const [gameId, setGameId] = useState("");
  const [availableSeasons, setAvailableSeasons] = useState<string[]>([]);
  const [availableInstitutions, setAvailableInstitutions] = useState<string[]>([]);
  const [reloadKey, setReloadKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadQueue() {
      try {
        const loadedPage = await identityResolutionApi.list({
          status,
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
          season: season || undefined,
          institution: institution || undefined,
          gameId: gameId || undefined,
        });
        if (active) {
          setItems(loadedPage.items);
          setTotal(loadedPage.total);
          setAvailableSeasons(loadedPage.available_seasons);
          setAvailableInstitutions(loadedPage.available_institutions);
        }
      } catch (loadError) {
        if (active) setError(apiErrorMessage(loadError));
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadQueue();
    return () => {
      active = false;
    };
  }, [gameId, institution, page, reloadKey, season, status]);

  function changeStatus(nextStatus: IdentityQueueStatus) {
    setLoading(true);
    setError(null);
    setStatus(nextStatus);
    setPage(0);
    setSeason("");
    setInstitution("");
    setGameId("");
    setSuccess(null);
  }

  function changeSeason(nextSeason: string) {
    setLoading(true);
    setPage(0);
    setSeason(nextSeason);
  }

  function changeInstitution(nextInstitution: string) {
    setLoading(true);
    setPage(0);
    setInstitution(nextInstitution);
  }

  function changeGameId(nextGameId: string) {
    setLoading(true);
    setPage(0);
    setGameId(nextGameId);
  }

  function clearFilters() {
    setLoading(true);
    setPage(0);
    setSeason("");
    setInstitution("");
    setGameId("");
  }

  function refreshAfterDecision() {
    if (items.length === 1 && page > 0) {
      setPage((current) => current - 1);
    } else {
      setReloadKey((current) => current + 1);
    }
  }

  async function resolveItem(
    item: IdentityQueueItem,
    playerId: number,
    resolutionNotes: string,
  ) {
    setError(null);
    setSuccess(null);
    try {
      await identityResolutionApi.resolve(item.id, playerId, resolutionNotes);
      setSuccess(`${displayPlayerName(item)} was linked to a canonical player.`);
      refreshAfterDecision();
    } catch (resolveError) {
      setError(apiErrorMessage(resolveError));
    }
  }

  async function createPlayer(
    item: IdentityQueueItem,
    displayName: string,
    resolutionNotes: string,
  ) {
    setError(null);
    setSuccess(null);
    try {
      await identityResolutionApi.createPlayer(item.id, {
        displayName,
        resolutionNotes,
      });
      setSuccess(
        `${displayName} was created and linked. Future ingests will use this identity.`,
      );
      refreshAfterDecision();
    } catch (createError) {
      setError(apiErrorMessage(createError));
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <header className="mb-8 max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-yellow-700">
          Data desk
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-gray-950">
          Identity review queue
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
          Review player rows the deterministic resolver would not guess. Source
          evidence and roster candidates stay attached to each decision.
        </p>
      </header>

      <div
        role="tablist"
        aria-label="Queue status"
        className="mb-4 flex gap-1 border-b border-gray-200"
      >
        {STATUS_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            role="tab"
            id={`queue-tab-${option.value}`}
            aria-controls="identity-queue-panel"
            aria-selected={status === option.value}
            onClick={() => changeStatus(option.value)}
            className={`border-b-2 px-3 py-2 text-sm font-medium transition-colors focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 ${
              status === option.value
                ? "border-gray-950 text-gray-950"
                : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-950"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="mb-5 grid gap-3 border-y border-gray-200 bg-white px-4 py-4 sm:grid-cols-2 sm:px-6 lg:grid-cols-[minmax(0,0.7fr)_minmax(0,1fr)_9rem_auto] lg:items-end">
        <label className="grid gap-1.5 text-xs font-semibold uppercase tracking-[0.06em] text-gray-600">
          Season
          <select
            value={season}
            onChange={(event) => changeSeason(event.target.value)}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-gray-950 outline-none focus:border-gray-950 focus:ring-2 focus:ring-yellow-400 focus:ring-offset-2"
          >
            <option value="">All seasons</option>
            {availableSeasons.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1.5 text-xs font-semibold uppercase tracking-[0.06em] text-gray-600">
          Institution
          <select
            value={institution}
            onChange={(event) => changeInstitution(event.target.value)}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-gray-950 outline-none focus:border-gray-950 focus:ring-2 focus:ring-yellow-400 focus:ring-offset-2"
          >
            <option value="">All institutions</option>
            {availableInstitutions.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1.5 text-xs font-semibold uppercase tracking-[0.06em] text-gray-600">
          Game ID
          <input
            type="number"
            min="1"
            inputMode="numeric"
            value={gameId}
            onChange={(event) => changeGameId(event.target.value)}
            placeholder="Any game"
            className="min-w-0 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-gray-950 outline-none placeholder:text-gray-400 focus:border-gray-950 focus:ring-2 focus:ring-yellow-400 focus:ring-offset-2"
          />
        </label>
        <button
          type="button"
          onClick={clearFilters}
          disabled={!season && !institution && !gameId}
          className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:border-gray-400 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:text-gray-400"
        >
          Clear filters
        </button>
      </div>

      {error && (
        <p
          role="alert"
          className="mb-4 border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {error}
        </p>
      )}
      {success && (
        <p
          role="status"
          className="mb-4 border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800"
        >
          {success}
        </p>
      )}

      <section
        id="identity-queue-panel"
        role="tabpanel"
        aria-labelledby={`queue-tab-${status}`}
        aria-busy={loading}
        className="overflow-hidden rounded-lg border border-gray-200 bg-white"
      >
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 sm:px-6">
          <h2 id="queue-heading" className="text-sm font-semibold text-gray-950">
            {status === "open" ? "Needs SID review" : "Resolved decisions"}
          </h2>
          {!loading && (
            <span className="text-xs tabular-nums text-gray-500">
              {total} item{total === 1 ? "" : "s"}
            </span>
          )}
        </div>

        {loading ? (
          <QueueSkeleton />
        ) : items.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="text-sm font-semibold text-gray-950">
              {status === "open" ? "The queue is clear" : "No resolved decisions yet"}
            </p>
            <p className="mx-auto mt-1 max-w-lg text-sm text-gray-500">
              {status === "open"
                ? "New uncertain player rows will appear here after ingestion."
                : "Completed identity decisions will remain available here for audit."}
            </p>
          </div>
        ) : (
          <ol className="divide-y divide-gray-200">
            {items.map((item) => (
              <IdentityQueueRow
                key={item.id}
                item={item}
                onResolve={resolveItem}
                onCreatePlayer={createPlayer}
              />
            ))}
          </ol>
        )}
        {!loading && total > 0 && (
          <div className="flex flex-col gap-3 border-t border-gray-200 bg-gray-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <p className="text-xs tabular-nums text-gray-600">
              Showing {page * PAGE_SIZE + 1}–
              {Math.min((page + 1) * PAGE_SIZE, total)} of {total}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setLoading(true);
                  setPage((current) => current - 1);
                }}
                disabled={page === 0}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:border-gray-400 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:text-gray-400"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => {
                  setLoading(true);
                  setPage((current) => current + 1);
                }}
                disabled={(page + 1) * PAGE_SIZE >= total}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:border-gray-400 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:text-gray-400"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function QueueSkeleton() {
  return (
    <div className="animate-pulse divide-y divide-gray-100" aria-label="Loading review queue">
      {[0, 1, 2].map((row) => (
        <div key={row} className="grid gap-4 px-6 py-5 md:grid-cols-3">
          <div className="h-4 w-36 rounded bg-gray-200" />
          <div className="h-4 w-48 rounded bg-gray-100" />
          <div className="h-8 w-full rounded bg-gray-100" />
        </div>
      ))}
    </div>
  );
}

function IdentityQueueRow({
  item,
  onResolve,
  onCreatePlayer,
}: {
  item: IdentityQueueItem;
  onResolve: (
    item: IdentityQueueItem,
    playerId: number,
    resolutionNotes: string,
  ) => Promise<void>;
  onCreatePlayer: (
    item: IdentityQueueItem,
    displayName: string,
    resolutionNotes: string,
  ) => Promise<void>;
}) {
  const [playerId, setPlayerId] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const sourceUrl = detailText(item, "source_url");
  const institution = detailText(item, "institution");
  const season = detailText(item, "season");
  const jerseyNumber = detailText(item, "jersey_number");
  const reason = detailText(item, "reason");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!playerId || !notes.trim()) return;
    setSubmitting(true);
    try {
      await onResolve(item, Number(playerId), notes.trim());
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <li className="grid gap-5 px-4 py-5 sm:px-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(18rem,1.2fr)]">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-semibold text-gray-950">{displayPlayerName(item)}</h3>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-yellow-200 bg-yellow-50 px-2 py-0.5 text-xs font-medium text-yellow-800">
            <span aria-hidden="true" className="size-1.5 rounded-full bg-yellow-500" />
            {reason === "ambiguous"
              ? "Ambiguous"
              : reason === "unmatched"
                ? "Unmatched"
                : item.status.replace("_", " ")}
          </span>
        </div>
        <p className="mt-1 text-sm leading-5 text-gray-600">{item.summary}</p>
        <p className="mt-2 text-xs text-gray-500">
          Detected {formatDetectedAt(item.detected_at)}
        </p>
      </div>

      <dl className="grid grid-cols-[auto_1fr] content-start gap-x-3 gap-y-1 text-sm">
        <dt className="text-gray-500">Institution</dt>
        <dd className="font-medium text-gray-800">{institution ?? "Unknown"}</dd>
        <dt className="text-gray-500">Season</dt>
        <dd className="font-mono text-xs text-gray-800">{season ?? "Unknown"}</dd>
        <dt className="text-gray-500">Jersey</dt>
        <dd className="font-mono text-xs text-gray-800">{jerseyNumber ?? "Not supplied"}</dd>
        {item.game_id && (
          <>
            <dt className="text-gray-500">Game</dt>
            <dd>
              <Link
                to={`/games/${item.game_id}`}
                className="font-medium text-gray-900 underline decoration-gray-300 underline-offset-2 hover:decoration-yellow-500 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
              >
                Open game {item.game_id}
              </Link>
            </dd>
          </>
        )}
        {sourceUrl && (
          <>
            <dt className="text-gray-500">Evidence</dt>
            <dd>
              <a
                href={sourceUrl}
                target="_blank"
                rel="noreferrer"
                className="font-medium text-gray-900 underline decoration-gray-300 underline-offset-2 hover:decoration-yellow-500 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
              >
                View source
              </a>
            </dd>
          </>
        )}
      </dl>

      {item.status === "resolved" ? (
        <div className="border-l border-gray-200 pl-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Canonical player
          </p>
          <p className="mt-1 text-sm font-semibold text-gray-950">
            {item.resolved_player_name ?? `Player ${item.player_id}`}
          </p>
          {item.resolution_notes && (
            <p className="mt-2 text-sm leading-5 text-gray-600">{item.resolution_notes}</p>
          )}
        </div>
      ) : item.candidate_players.length > 0 ? (
        <form onSubmit={handleSubmit} className="grid gap-3">
          <label className="grid gap-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Canonical player
            <select
              required
              value={playerId}
              onChange={(event) => setPlayerId(event.target.value)}
              className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-gray-950 focus:border-gray-950 focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:ring-offset-2"
            >
              <option value="">Select a roster candidate</option>
              {item.candidate_players.map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.display_name}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Decision note
            <textarea
              required
              rows={2}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Record the evidence used for this match"
              className="resize-y rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-gray-950 placeholder:text-gray-400 focus:border-gray-950 focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:ring-offset-2"
            />
          </label>
          <button
            type="submit"
            disabled={submitting}
            className="justify-self-start rounded-md bg-gray-950 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-gray-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Saving decision..." : "Confirm identity"}
          </button>
        </form>
      ) : (
        <CreatePlayerForm item={item} onCreatePlayer={onCreatePlayer} />
      )}
    </li>
  );
}

function CreatePlayerForm({
  item,
  onCreatePlayer,
}: {
  item: IdentityQueueItem;
  onCreatePlayer: (
    item: IdentityQueueItem,
    displayName: string,
    resolutionNotes: string,
  ) => Promise<void>;
}) {
  const [displayName, setDisplayName] = useState(displayPlayerName(item));
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const helpId = `create-player-help-${item.id}`;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!displayName.trim() || !notes.trim()) return;
    setSubmitting(true);
    try {
      await onCreatePlayer(item, displayName.trim(), notes.trim());
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-3">
      <div>
        <p className="text-sm font-semibold text-gray-950">Create canonical player</p>
        <p id={helpId} className="mt-1 text-sm leading-5 text-gray-600">
          No roster candidate exists. Confirm the name from the attached evidence.
        </p>
      </div>
      <label className="grid gap-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
        Canonical name
        <input
          required
          maxLength={255}
          value={displayName}
          aria-describedby={helpId}
          onChange={(event) => setDisplayName(event.target.value)}
          className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-gray-950 focus:border-gray-950 focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:ring-offset-2"
        />
      </label>
      <label className="grid gap-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
        Decision note
        <textarea
          required
          maxLength={2000}
          rows={2}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="Record the evidence used to create this player"
          className="resize-y rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-gray-950 placeholder:text-gray-400 focus:border-gray-950 focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:ring-offset-2"
        />
      </label>
      <button
        type="submit"
        disabled={submitting}
        className="justify-self-start rounded-md bg-gray-950 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-gray-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? "Creating player..." : "Create and resolve"}
      </button>
    </form>
  );
}

export default IdentityQueuePage;
