import type { ReactNode } from "react";
import { Link, NavLink } from "react-router";

function navClass({ isActive }: { isActive: boolean }): string {
  return [
    "shrink-0 whitespace-nowrap border-b-2 px-1 py-5 text-sm font-medium transition-colors",
    "focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-500",
    isActive
      ? "border-yellow-500 text-gray-950"
      : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-950",
  ].join(" ");
}

interface AppShellProps {
  children: ReactNode;
  username: string;
  roles: string[];
  logoutPending: boolean;
  logoutError: string | null;
  onLogout: () => Promise<void>;
}

function AppShell({
  children,
  username,
  roles,
  logoutPending,
  logoutError,
  onLogout,
}: AppShellProps) {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-950">
      <a
        href="#main-content"
        className="sr-only z-50 bg-gray-950 px-4 py-2 text-sm font-semibold text-white focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to main content
      </a>
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 px-4 sm:flex-nowrap sm:px-6 lg:px-8">
          <Link
            to="/"
            className="mr-auto flex items-center gap-3 py-4 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-500"
          >
            <span
              aria-hidden="true"
              className="grid size-8 place-items-center bg-gray-950 text-sm font-black text-yellow-400"
            >
              V
            </span>
            <span className="hidden leading-tight sm:block">
              <span className="block text-xs font-black uppercase tracking-[0.12em] text-gray-950">
                Vandals
              </span>
              <span className="block text-xs font-medium text-gray-500">
                Stats desk
              </span>
            </span>
          </Link>
          <nav
            aria-label="Primary"
            className="order-3 flex w-full min-w-0 items-center gap-3 overflow-x-auto border-t border-gray-100 sm:order-none sm:w-auto sm:gap-6 sm:border-0"
          >
            <NavLink to="/" end className={navClass}>
              Games
            </NavLink>
            <NavLink to="/workspace" className={navClass}>
              Workspace
            </NavLink>
            <NavLink to="/ask" className={navClass}>
              Ask
            </NavLink>
            <NavLink to="/achievements" className={navClass}>
              Achievements
            </NavLink>
            <NavLink to="/articles" className={navClass}>
              Articles
            </NavLink>
            {roles.includes("style_steward") ? (
              <NavLink to="/style-guides" className={navClass}>
                Style Guides
              </NavLink>
            ) : null}
            <NavLink to="/record-book" className={navClass}>
              Record Book
            </NavLink>
            <NavLink to="/identity-queue" className={navClass}>
              Identity queue
            </NavLink>
            <NavLink to="/backfills" className={navClass}>
              Backfills
            </NavLink>
            <NavLink to="/demo" className={navClass}>
              Demo
            </NavLink>
          </nav>
          <div className="flex items-center gap-3 border-l border-gray-200 pl-4">
            <span className="hidden text-right leading-tight md:block">
              <span className="block text-[11px] font-bold uppercase tracking-[0.08em] text-gray-400">
                Signed in
              </span>
              <span className="block max-w-32 truncate text-xs font-semibold text-gray-700">
                {username}
              </span>
            </span>
            <button
              type="button"
              onClick={() => void onLogout()}
              disabled={logoutPending}
              className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-semibold text-gray-700 transition-colors hover:border-gray-400 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-wait disabled:text-gray-400"
            >
              {logoutPending ? "Signing out…" : "Sign out"}
            </button>
          </div>
        </div>
      </header>
      {logoutError ? (
        <p
          role="alert"
          className="mx-auto max-w-7xl border-b border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-800 sm:px-6 lg:px-8"
        >
          {logoutError}
        </p>
      ) : null}
      <main id="main-content">{children}</main>
    </div>
  );
}

export default AppShell;
