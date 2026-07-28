import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { articlesApi } from "../api/articles";
import type { ArticleQueue, ArticleStatus, ArticleType } from "../types/article";

function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The Article queue could not be loaded.";
}

function statusLabel(status: ArticleStatus): string {
  return {
    brief: "Brief",
    generating: "Generating",
    in_edit: "In edit",
    ready: "Ready",
    needs_revalidation: "Needs revalidation",
    archived: "Archived",
  }[status];
}

function typeLabel(type: ArticleType): string {
  return {
    game_recap: "Game recap",
    player_spotlight: "Player spotlight",
    achievement_story: "Achievement story",
  }[type];
}

function statusClass(status: ArticleStatus): string {
  if (status === "ready") return "bg-green-50 text-green-800 ring-green-200";
  if (status === "needs_revalidation") {
    return "bg-red-50 text-red-800 ring-red-200";
  }
  if (status === "generating") {
    return "bg-yellow-50 text-yellow-900 ring-yellow-200";
  }
  return "bg-gray-100 text-gray-700 ring-gray-200";
}

function formatDate(value: string | null): string {
  if (!value) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function ArticleQueuePage() {
  const [queue, setQueue] = useState<ArticleQueue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"active" | "ready" | "all">("active");

  useEffect(() => {
    let active = true;
    articlesApi
      .list()
      .then((result) => {
        if (active) setQueue(result);
      })
      .catch((loadError: unknown) => {
        if (active) setError(errorMessage(loadError));
      });
    return () => {
      active = false;
    };
  }, []);

  const items = useMemo(() => {
    if (!queue) return [];
    if (filter === "ready") {
      return queue.items.filter((item) => item.status === "ready");
    }
    if (filter === "active") {
      return queue.items.filter((item) => item.status !== "ready");
    }
    return queue.items;
  }, [filter, queue]);

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6">
        <h1 className="text-2xl font-black text-gray-950">Article desk unavailable</h1>
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error}
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <header className="flex flex-col gap-5 border-b border-gray-300 pb-7 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-yellow-700">
            Editorial workflow
          </p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-gray-950">
            Article desk
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
            Review drafts, preserve every checkpoint, and choose the exact version
            that is ready for distribution.
          </p>
        </div>
        <Link
          to="/achievements"
          className="inline-flex w-fit items-center rounded-md bg-gray-950 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
        >
          Start from achievements
        </Link>
      </header>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex gap-1 rounded-md bg-gray-100 p-1" aria-label="Article filters">
          {(["active", "ready", "all"] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setFilter(value)}
              aria-pressed={filter === value}
              className={`rounded px-3 py-1.5 text-sm font-semibold capitalize transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 ${
                filter === value
                  ? "bg-white text-gray-950 shadow-sm"
                  : "text-gray-600 hover:text-gray-950"
              }`}
            >
              {value}
            </button>
          ))}
        </div>
        <p className="text-sm text-gray-600">
          {queue ? `${items.length} of ${queue.total} Articles` : "Loading Articles"}
        </p>
      </div>

      {!queue ? (
        <div aria-label="Loading Article queue" className="mt-5 animate-pulse border-y border-gray-200 bg-white">
          {[0, 1, 2].map((row) => (
            <div key={row} className="h-20 border-b border-gray-100 last:border-0" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <section className="mt-8 border-y border-gray-200 bg-white px-6 py-14 text-center">
          <h2 className="text-lg font-bold text-gray-950">No Articles in this view</h2>
          <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-gray-600">
            Approved Achievement Suggestions become Article Briefs before they enter
            this desk.
          </p>
        </section>
      ) : (
        <div className="mt-5 overflow-x-auto border-y border-gray-300 bg-white">
          <table className="min-w-full text-left text-sm">
            <caption className="sr-only">Current editorial Articles</caption>
            <thead className="bg-gray-50 text-xs font-bold uppercase tracking-[0.06em] text-gray-500">
              <tr>
                <th scope="col" className="px-4 py-3">Article</th>
                <th scope="col" className="px-4 py-3">State</th>
                <th scope="col" className="px-4 py-3">Version</th>
                <th scope="col" className="px-4 py-3">Owner</th>
                <th scope="col" className="px-4 py-3">Game</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {items.map((item) => (
                <tr key={item.id} className="align-top hover:bg-gray-50">
                  <td className="max-w-xl px-4 py-4">
                    <Link
                      to={`/articles/${item.id}`}
                      className="font-bold text-gray-950 underline decoration-gray-300 underline-offset-4 hover:decoration-yellow-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
                    >
                      {item.angle}
                    </Link>
                    <p className="mt-1 text-xs text-gray-500">{typeLabel(item.article_type)}</p>
                  </td>
                  <td className="px-4 py-4">
                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ring-1 ring-inset ${statusClass(item.status)}`}>
                      {statusLabel(item.status)}
                    </span>
                  </td>
                  <td className="px-4 py-4 font-mono text-xs tabular-nums text-gray-700">
                    {item.latest_version ? `v${item.latest_version.version}` : "Not drafted"}
                    {item.ready_version ? (
                      <span className="mt-1 block font-sans text-green-800">
                        v{item.ready_version.version} ready
                      </span>
                    ) : null}
                  </td>
                  <td className="px-4 py-4 text-gray-700">{item.owner}</td>
                  <td className="px-4 py-4 text-gray-700">
                    <span className="block font-medium">{item.game_title ?? "Game"}</span>
                    <span className="mt-1 block text-xs text-gray-500">{formatDate(item.game_date)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default ArticleQueuePage;
