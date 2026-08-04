import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router";

interface WorkspaceLink {
  description: string;
  label: string;
  requiredRole?: string;
  to: string;
}

interface WorkspaceDefinition {
  description: string;
  id: "data" | "communications" | "analytics";
  label: string;
  links: readonly WorkspaceLink[];
  routePrefixes: readonly string[];
}

const WORKSPACES: readonly WorkspaceDefinition[] = [
  {
    id: "data",
    label: "Data operations",
    description: "Bring records in, validate them, and manage coverage.",
    routePrefixes: ["/games", "/identity-queue", "/backfills"],
    links: [
      {
        label: "Games desk",
        description: "Ingest schedules, rosters, and box scores.",
        to: "/games",
      },
      {
        label: "Identity review",
        description: "Resolve uncertain player and team matches.",
        to: "/identity-queue",
      },
      {
        label: "Historical backfills",
        description: "Find and close gaps in season coverage.",
        to: "/backfills",
      },
    ],
  },
  {
    id: "communications",
    label: "Communications",
    description: "Develop verified ideas into approved coverage.",
    routePrefixes: ["/articles", "/style-guides"],
    links: [
      {
        label: "Article desk",
        description: "Review briefs, build drafts, and manage approvals.",
        to: "/articles",
      },
      {
        label: "Style guides",
        description: "Maintain the standards used for Athletics coverage.",
        requiredRole: "style_steward",
        to: "/style-guides",
      },
    ],
  },
  {
    id: "analytics",
    label: "Analytics",
    description: "Explore history, trends, records, and emerging stories.",
    routePrefixes: ["/workspace", "/ask", "/record-book", "/achievements"],
    links: [
      {
        label: "Season explorer",
        description: "Investigate teams, players, games, and comparisons.",
        to: "/workspace",
      },
      {
        label: "Ask the warehouse",
        description: "Put a focused question to the athletics record.",
        to: "/ask",
      },
      {
        label: "Record book",
        description: "Review configured records and historical leaders.",
        to: "/record-book",
      },
      {
        label: "Achievement tracking",
        description: "Review milestones and performances worth following.",
        to: "/achievements",
      },
    ],
  },
] as const;

function routeMatches(pathname: string, prefixes: readonly string[]): boolean {
  return prefixes.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

function directNavClass({ isActive }: { isActive: boolean }): string {
  return [
    "shrink-0 whitespace-nowrap border-b-2 px-1 py-5 text-sm font-semibold transition-colors",
    "focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-500",
    isActive
      ? "border-yellow-500 text-gray-950"
      : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-950",
  ].join(" ");
}

function workspaceTriggerClass(isActive: boolean, isOpen: boolean): string {
  return [
    "inline-flex items-center gap-1.5 whitespace-nowrap border-b-2 px-1 py-5 text-sm font-semibold transition-colors",
    "focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-500",
    isActive || isOpen
      ? "border-yellow-500 text-gray-950"
      : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-950",
  ].join(" ");
}

function workspaceLinkClass({ isActive }: { isActive: boolean }): string {
  return [
    "block px-4 py-3 transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-yellow-500",
    isActive ? "bg-yellow-50" : "hover:bg-gray-50",
  ].join(" ");
}

interface WorkspaceMenuProps {
  definition: WorkspaceDefinition;
  isActive: boolean;
  isOpen: boolean;
  links: readonly WorkspaceLink[];
  onNavigate: () => void;
  onToggle: () => void;
}

function WorkspaceMenu({
  definition,
  isActive,
  isOpen,
  links,
  onNavigate,
  onToggle,
}: WorkspaceMenuProps) {
  const menuId = `${definition.id}-workspace-menu`;

  return (
    <div className="relative">
      <button
        type="button"
        aria-controls={menuId}
        aria-current={isActive ? "page" : undefined}
        aria-expanded={isOpen}
        data-workspace-trigger={definition.id}
        onClick={onToggle}
        className={workspaceTriggerClass(isActive, isOpen)}
      >
        {definition.label}
        <svg
          aria-hidden="true"
          viewBox="0 0 16 16"
          fill="none"
          className={`size-3.5 transition-transform ${isOpen ? "rotate-180" : ""}`}
        >
          <path
            d="m4 6 4 4 4-4"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.5"
          />
        </svg>
      </button>

      {isOpen ? (
        <div
          id={menuId}
          className="absolute left-0 top-full z-30 w-96 overflow-hidden rounded-b-lg border border-gray-200 bg-white shadow-lg"
        >
          <div className="border-b border-gray-200 px-4 py-3">
            <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-950">
              {definition.label}
            </p>
            <p className="mt-1 text-xs leading-5 text-gray-500">
              {definition.description}
            </p>
          </div>
          <ul className="divide-y divide-gray-100">
            {links.map((link) => (
              <li key={link.to}>
                <NavLink
                  to={link.to}
                  onClick={onNavigate}
                  className={workspaceLinkClass}
                >
                  <span className="block text-sm font-semibold text-gray-950">
                    {link.label}
                  </span>
                  <span className="mt-0.5 block text-xs leading-5 text-gray-500">
                    {link.description}
                  </span>
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
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
  const location = useLocation();
  const headerRef = useRef<HTMLElement>(null);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const [openWorkspace, setOpenWorkspace] = useState<
    WorkspaceDefinition["id"] | null
  >(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const visibleWorkspaces = WORKSPACES.map((workspace) => ({
    ...workspace,
    links: workspace.links.filter(
      (link) => !link.requiredRole || roles.includes(link.requiredRole),
    ),
  }));

  useEffect(() => {
    if (!openWorkspace && !mobileMenuOpen) {
      return;
    }

    function handlePointerDown(event: MouseEvent) {
      if (
        headerRef.current &&
        event.target instanceof Node &&
        !headerRef.current.contains(event.target)
      ) {
        setOpenWorkspace(null);
        setMobileMenuOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") {
        return;
      }

      if (openWorkspace) {
        const trigger = headerRef.current?.querySelector<HTMLButtonElement>(
          `[data-workspace-trigger="${openWorkspace}"]`,
        );
        setOpenWorkspace(null);
        trigger?.focus();
      } else if (mobileMenuOpen) {
        setMobileMenuOpen(false);
        mobileMenuButtonRef.current?.focus();
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [mobileMenuOpen, openWorkspace]);

  return (
    <div className="min-h-screen bg-gray-50 text-gray-950">
      <a
        href="#main-content"
        className="sr-only z-50 bg-gray-950 px-4 py-2 text-sm font-semibold text-white focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to main content
      </a>
      <header ref={headerRef} className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 sm:px-6 lg:gap-6 lg:px-8">
          <Link
            to="/"
            onClick={() => {
              setOpenWorkspace(null);
              setMobileMenuOpen(false);
            }}
            className="mr-auto flex shrink-0 items-center gap-3 py-4 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-500 lg:mr-0"
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
            className="hidden min-w-0 flex-1 items-center justify-center gap-5 lg:flex xl:gap-7"
          >
            <NavLink
              to="/"
              end
              onClick={() => setOpenWorkspace(null)}
              className={directNavClass}
            >
              Overview
            </NavLink>
            {visibleWorkspaces.map((workspace) => (
              <WorkspaceMenu
                key={workspace.id}
                definition={workspace}
                links={workspace.links}
                isActive={routeMatches(
                  location.pathname,
                  workspace.routePrefixes,
                )}
                isOpen={openWorkspace === workspace.id}
                onToggle={() =>
                  setOpenWorkspace((current) =>
                    current === workspace.id ? null : workspace.id,
                  )
                }
                onNavigate={() => setOpenWorkspace(null)}
              />
            ))}
            <NavLink
              to="/demo"
              onClick={() => setOpenWorkspace(null)}
              className={directNavClass}
            >
              Demo
            </NavLink>
          </nav>

          <button
            ref={mobileMenuButtonRef}
            type="button"
            aria-controls="mobile-primary-navigation"
            aria-expanded={mobileMenuOpen}
            onClick={() => setMobileMenuOpen((current) => !current)}
            className="inline-flex min-h-10 items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 text-xs font-semibold text-gray-700 transition-colors hover:border-gray-400 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 lg:hidden"
          >
            Menu
            <svg
              aria-hidden="true"
              viewBox="0 0 16 16"
              fill="none"
              className={`size-3.5 transition-transform ${mobileMenuOpen ? "rotate-180" : ""}`}
            >
              <path
                d="m4 6 4 4 4-4"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.5"
              />
            </svg>
          </button>

          <div className="flex items-center gap-3 border-l border-gray-200 pl-4">
            <span className="hidden text-right leading-tight xl:block">
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

        {mobileMenuOpen ? (
          <nav
            id="mobile-primary-navigation"
            aria-label="Primary mobile"
            className="border-t border-gray-200 bg-gray-50 lg:hidden"
          >
            <div className="mx-auto max-w-7xl px-4 py-5 sm:px-6">
              <div className="flex gap-5 border-b border-gray-200 pb-4">
                <NavLink
                  to="/"
                  end
                  onClick={() => setMobileMenuOpen(false)}
                  className="text-sm font-semibold text-gray-700 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-500"
                >
                  Overview
                </NavLink>
                <NavLink
                  to="/demo"
                  onClick={() => setMobileMenuOpen(false)}
                  className="text-sm font-semibold text-gray-700 hover:text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-500"
                >
                  Demo
                </NavLink>
              </div>
              <div className="grid gap-7 pt-5 sm:grid-cols-3">
                {visibleWorkspaces.map((workspace) => (
                  <section
                    key={workspace.id}
                    aria-labelledby={`mobile-${workspace.id}-heading`}
                  >
                    <h2
                      id={`mobile-${workspace.id}-heading`}
                      className="text-xs font-bold uppercase tracking-[0.08em] text-gray-950"
                    >
                      {workspace.label}
                    </h2>
                    <p className="mt-1 text-xs leading-5 text-gray-500">
                      {workspace.description}
                    </p>
                    <ul className="mt-3 border-t border-gray-200">
                      {workspace.links.map((link) => (
                        <li key={link.to} className="border-b border-gray-200">
                          <NavLink
                            to={link.to}
                            onClick={() => setMobileMenuOpen(false)}
                            className="block py-2.5 text-sm font-semibold text-gray-700 hover:text-gray-950 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-yellow-500"
                          >
                            {link.label}
                          </NavLink>
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </div>
            </div>
          </nav>
        ) : null}
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
