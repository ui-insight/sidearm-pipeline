import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";

function navClass({ isActive }: { isActive: boolean }): string {
  return [
    "border-b-2 px-1 py-5 text-sm font-medium transition-colors",
    "focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-500",
    isActive
      ? "border-yellow-500 text-gray-950"
      : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-950",
  ].join(" ");
}

function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-950">
      <a
        href="#main-content"
        className="sr-only z-50 bg-gray-950 px-4 py-2 text-sm font-semibold text-white focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to main content
      </a>
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 sm:px-6 lg:px-8">
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
          <nav aria-label="Primary" className="flex items-center gap-4 sm:gap-6">
            <NavLink to="/" end className={navClass}>
              Games
            </NavLink>
            <NavLink to="/identity-queue" className={navClass}>
              Identity queue
            </NavLink>
            <NavLink to="/backfills" className={navClass}>
              Backfills
            </NavLink>
          </nav>
        </div>
      </header>
      <main id="main-content">{children}</main>
    </div>
  );
}

export default AppShell;
