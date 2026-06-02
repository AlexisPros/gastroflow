import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/useAuth";
import type { UserRole } from "../shared/types";
import { routes } from "../routes/routePaths";

type NavItem = {
  label: string;
  path: string;
  roles: UserRole[];
};

const navItems: NavItem[] = [
  { label: "Floor", path: routes.floor, roles: ["ADMIN", "MANAGER", "WAITER"] },
  { label: "Waiter", path: routes.waiter, roles: ["ADMIN", "MANAGER", "WAITER"] },
  { label: "Kitchen", path: routes.kitchen, roles: ["ADMIN", "MANAGER", "KITCHEN"] },
  { label: "Bar", path: routes.bar, roles: ["ADMIN", "MANAGER", "BARTENDER"] },
  { label: "Reports", path: routes.reports, roles: ["ADMIN", "MANAGER"] },
  { label: "Admin", path: routes.admin, roles: ["ADMIN"] },
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const availableItems = user
    ? navItems.filter((item) => item.roles.includes(user.role))
    : [];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink to={routes.dashboard} className="brand">
          <img src="/logo.png" alt="GastroFlow" className="brand-logo" />
        </NavLink>

        <nav className="nav-list">
          {availableItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">Signed in</span>
            <strong>
              {user?.first_name} {user?.last_name}
            </strong>
          </div>
          <div className="topbar-actions">
            <span className="role-pill">{user?.role}</span>
            <button type="button" className="ghost-button" onClick={logout}>
              Logout
            </button>
          </div>
        </header>

        <main className="page-surface">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
