import { NavLink } from "react-router-dom";

function viewClass({ isActive }: { isActive: boolean }): string {
  return [
    "border-b-2 px-1 py-3 text-sm font-bold transition-colors",
    "focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500",
    isActive
      ? "border-yellow-500 text-gray-950"
      : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-950",
  ].join(" ");
}

function WorkspaceViewNav() {
  return (
    <nav
      aria-label="Workspace views"
      className="mt-6 flex gap-6 border-b border-gray-200"
    >
      <NavLink to="/workspace" end className={viewClass}>
        Season desk
      </NavLink>
      <NavLink to="/workspace/compare" className={viewClass}>
        Player comparison
      </NavLink>
    </nav>
  );
}

export default WorkspaceViewNav;
