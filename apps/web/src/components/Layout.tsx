import { NavLink, Outlet, useLocation } from "react-router-dom";
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
  const { pathname } = useLocation();
  const boardMode = pathname === "/kanban";

  return (
    <div
      className={clsx(
        boardMode
          ? "flex h-dvh flex-col overflow-hidden lg:grid lg:grid-cols-[200px_1fr]"
          : "min-h-screen lg:grid lg:grid-cols-[200px_1fr]",
      )}
    >
      <aside
        className={clsx(
          "border-b border-slate-800 bg-slate-950 text-slate-100 lg:border-b-0 lg:border-r lg:border-slate-800",
          boardMode ? "shrink-0 lg:h-dvh lg:overflow-y-auto" : "lg:min-h-screen",
        )}
      >
        <div className={clsx(boardMode ? "px-4 py-3" : "px-5 py-6")}>
          <div className="flex items-center gap-3">
            <img src="/icon.png" alt="Mankiu" className="h-9 w-9 rounded-xl" />
            <div>
              <div className="brand text-lg font-extrabold tracking-tight">Mankiu</div>
              <div className="text-[11px] font-medium text-slate-400">Multi-agent factory</div>
            </div>
          </div>
          {!boardMode ? (
            <p className="mt-4 text-sm leading-relaxed text-slate-400">
              Multi-agent software factory with a live Kanban board.
            </p>
          ) : null}
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-col lg:overflow-visible">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/"}
              className={({ isActive }) =>
                clsx(
                  "whitespace-nowrap rounded-xl px-3 py-2 text-sm font-semibold transition",
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
      <main
        className={clsx(
          "min-w-0",
          boardMode
            ? "flex min-h-0 flex-1 flex-col overflow-hidden px-3 py-3 sm:px-4"
            : "px-4 py-5 sm:px-6 lg:px-7",
        )}
      >
        <Outlet />
      </main>
    </div>
  );
}
