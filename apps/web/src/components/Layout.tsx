import { NavLink, Outlet } from "react-router-dom";
import clsx from "clsx";

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/kanban", label: "Board" },
  { to: "/portal", label: "Portal" },
  { to: "/swarm", label: "Swarm" },
  { to: "/approvals", label: "Approvals" },
  { to: "/tickets", label: "Tickets" },
  { to: "/agents", label: "Agents" },
  { to: "/projects", label: "Projects" },
];

export function Layout() {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[240px_1fr]">
      <aside className="border-b border-slate-800 bg-slate-950 text-slate-100 lg:min-h-screen lg:border-b-0 lg:border-r lg:border-slate-800">
        <div className="px-5 py-6">
          <div className="flex items-center gap-3">
            <img src="/icon.png" alt="Mankiu" className="h-10 w-10 rounded-xl" />
            <div>
              <div className="brand text-xl font-extrabold tracking-tight">Mankiu</div>
              <div className="text-xs font-medium text-slate-400">Multi-agent factory</div>
            </div>
          </div>
          <p className="mt-4 text-sm leading-relaxed text-slate-400">
            Multi-agent software factory with a live Kanban board.
          </p>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-4 lg:flex-col lg:overflow-visible">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/"}
              className={({ isActive }) =>
                clsx(
                  "whitespace-nowrap rounded-xl px-3 py-2.5 text-sm font-semibold transition",
                  isActive
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-300 hover:bg-white/5 hover:text-white",
                )
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="min-w-0 px-4 py-5 sm:px-6 lg:px-7">
        <Outlet />
      </main>
    </div>
  );
}
