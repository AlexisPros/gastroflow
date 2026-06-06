import { NavLink, Outlet } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../api/apiClient";
import {
  closeCurrentShift,
  getCurrentShift,
  startShift,
  type EmployeeShift,
} from "../api/shiftApi";
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
  { label: "Reports", path: routes.reports, roles: ["ADMIN", "MANAGER", "WAITER"] },
  { label: "Admin", path: routes.admin, roles: ["ADMIN"] },
];

export function AppLayout() {
  const { token, user, logout } = useAuth();
  const [currentShift, setCurrentShift] = useState<EmployeeShift | null>(null);
  const [shiftError, setShiftError] = useState<string | null>(null);
  const [isShiftChanging, setIsShiftChanging] = useState(false);
  const [isNavigationOpen, setIsNavigationOpen] = useState(false);
  const availableItems = user
    ? navItems.filter((item) => item.roles.includes(user.role))
    : [];
  const canUseShift = user?.role === "ADMIN" || user?.role === "MANAGER" || user?.role === "WAITER";

  const loadCurrentShift = useCallback(async () => {
    if (!token) {
      return;
    }

    try {
      setShiftError(null);
      setCurrentShift(await getCurrentShift(token));
    } catch (exc) {
      setShiftError(exc instanceof ApiError ? exc.message : "Could not load shift.");
    }
  }, [token]);

  useEffect(() => {
    if (!token || !canUseShift) {
      return;
    }

    void loadCurrentShift();
  }, [canUseShift, loadCurrentShift, token]);

  return (
    <div className={`app-shell ${isNavigationOpen ? "navigation-open" : ""}`}>
      <aside className={`sidebar ${isNavigationOpen ? "open" : ""}`}>
        <button
          type="button"
          className="navigation-toggle"
          aria-label={isNavigationOpen ? "Zwiń menu" : "Rozwiń menu"}
          title={isNavigationOpen ? "Zwiń menu" : "Rozwiń menu"}
          onClick={() => setIsNavigationOpen((isOpen) => !isOpen)}
        >
          <span className="navigation-toggle-icon" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
        </button>

        {isNavigationOpen && (
          <>
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
          </>
        )}
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
            <span className="eyebrow">Zalogowano</span>
            <strong>
              {user?.first_name} {user?.last_name}
            </strong>
          </div>
          <div className="topbar-actions">
            {shiftError && <span className="topbar-error">{shiftError}</span>}
            {canUseShift && (
              <button
                type="button"
                className={`shift-button ${currentShift ? "ending" : ""}`}
                onClick={() => {
                  void toggleShift();
                }}
                disabled={isShiftChanging}
              >
                {currentShift ? "Zakończ zmianę" : "Rozpocznij zmianę"}
              </button>
            )}
            <span className="role-pill">{user?.role}</span>
            <button type="button" className="ghost-button" onClick={logout}>
              Wyloguj
            </button>
          </div>
        </header>

        <main className="page-surface">
          <Outlet />
        </main>
      </div>
    </div>
  );

  async function toggleShift() {
    if (!token) {
      return;
    }

    setIsShiftChanging(true);
    setShiftError(null);
    try {
      if (currentShift) {
        await closeCurrentShift(token);
        setCurrentShift(null);
      } else {
        setCurrentShift(await startShift(token));
      }
    } catch (exc) {
      setShiftError(exc instanceof ApiError ? exc.message : "Could not update shift.");
    } finally {
      setIsShiftChanging(false);
    }
  }
}
