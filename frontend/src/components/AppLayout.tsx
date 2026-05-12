import { NavLink, Outlet } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/operator", label: "Operator", end: false },
  { to: "/agent-runs", label: "AI Runs", end: false },
  { to: "/ingest-runs", label: "Ingest Runs", end: false },
  { to: "/query", label: "Query", end: false },
];

function AppLayout() {
  return (
    <>
      <nav className="fixed top-0 inset-x-0 z-50 bg-gray-950 h-14 flex items-center px-6 gap-8">
        <span className="text-yellow-400 font-bold text-sm tracking-tight select-none">
          ■ Vandals Stats
        </span>
        <div className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `px-3 py-1 text-sm transition border-b-2 pb-0.5 ${
                  isActive
                    ? "text-white border-yellow-400"
                    : "text-gray-400 hover:text-white border-transparent"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="pt-14 min-h-screen bg-gray-50">
        <Outlet />
      </main>
    </>
  );
}

export default AppLayout;
