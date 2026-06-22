import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../api/apiClient";
import {
  closeCurrentShift,
  getCurrentShift,
  startShift,
  type EmployeeShift,
} from "../api/shiftApi";
import { useAuth } from "../auth/useAuth";
import { connectLiveUpdates } from "../ws/liveUpdates";
import type { UserRole } from "../shared/types";
import { routes } from "../routes/routePaths";

type NavItem = {
  label: string;
  path: string;
  roles: UserRole[];
};

type ReadyDepartment = "KITCHEN" | "BAR";

type DepartmentReadyAlert = {
  key: string;
  orderId: number;
  tableNumber: string;
  department: ReadyDepartment;
};

const navItems: NavItem[] = [
  { label: "Układ sali", path: routes.floor, roles: ["ADMIN", "MANAGER", "WAITER"] },
  { label: "Kelner", path: routes.waiter, roles: ["ADMIN", "MANAGER", "WAITER"] },
  { label: "Kuchnia", path: routes.kitchen, roles: ["ADMIN", "MANAGER", "KITCHEN", "CHEF", "WYDAWKA"] },
  { label: "Bar", path: routes.bar, roles: ["ADMIN", "MANAGER", "BARTENDER"] },
  { label: "Raporty", path: routes.reports, roles: ["ADMIN", "MANAGER", "WAITER"] },
  { label: "Panel Admina", path: routes.admin, roles: ["ADMIN"] },
];

export function AppLayout() {
  const { token, user, logout } = useAuth();
  const navigate = useNavigate();
  const [currentShift, setCurrentShift] = useState<EmployeeShift | null>(null);
  const [shiftError, setShiftError] = useState<string | null>(null);
  const [isShiftChanging, setIsShiftChanging] = useState(false);
  const [isNavigationOpen, setIsNavigationOpen] = useState(false);
  const [qrOrderAlert, setQrOrderAlert] = useState<{
    orderId: number;
    tableNumber: string;
    guestCount: number;
    totalAmount: string;
  } | null>(null);
  const [departmentReadyAlerts, setDepartmentReadyAlerts] = useState<DepartmentReadyAlert[]>([]);
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
      setShiftError(exc instanceof ApiError ? exc.message : "Nie udało się załadować zmiany.");
    }
  }, [token]);

  useEffect(() => {
    if (!token || !canUseShift) {
      return;
    }

    void loadCurrentShift();
  }, [canUseShift, loadCurrentShift, token]);

  useEffect(() => {
    if (
      !token
      || !currentShift
      || (user?.role !== "WAITER" && user?.role !== "MANAGER")
    ) {
      setQrOrderAlert(null);
      setDepartmentReadyAlerts([]);
      return;
    }

    return connectLiveUpdates({
      channel: "waiters",
      token,
      onMessage: (message) => {
        const data = message.data as {
          order_id?: unknown;
          table_number?: unknown;
          guest_count?: unknown;
          total_amount?: unknown;
          waiter_id?: unknown;
          department?: unknown;
          departments?: unknown;
        };
        const orderId = Number(data.order_id);

        if (message.event === "qr_order_created" && Number.isFinite(orderId)) {
          setQrOrderAlert({
            orderId,
            tableNumber: String(data.table_number ?? data.order_id ?? ""),
            guestCount: Number(data.guest_count ?? 0),
            totalAmount: String(data.total_amount ?? "0"),
          });
        }

        if (
          message.event === "qr_order_confirmed"
          || message.event === "qr_order_rejected"
          || message.event === "order_cancelled"
        ) {
          setQrOrderAlert((current) => current?.orderId === orderId ? null : current);
          setDepartmentReadyAlerts((current) =>
            current.filter((alert) => alert.orderId !== orderId)
          );
        }

        if (message.event === "order_items_added" && Number.isFinite(orderId)) {
          const departments = Array.isArray(data.departments)
            ? new Set(
                data.departments.filter(
                  (department): department is ReadyDepartment =>
                    department === "KITCHEN" || department === "BAR",
                ),
              )
            : new Set<ReadyDepartment>(["KITCHEN", "BAR"]);

          setDepartmentReadyAlerts((current) =>
            current.filter(
              (alert) =>
                alert.orderId !== orderId || !departments.has(alert.department),
            ),
          );
        }

        if (
          (message.event === "kitchen_order_ready" || message.event === "bar_order_ready")
          && Number.isFinite(orderId)
        ) {
          const waiterId = Number(data.waiter_id);
          if (
            user?.role === "WAITER"
            && Number.isFinite(waiterId)
            && waiterId !== user.id
          ) {
            return;
          }

          const department: ReadyDepartment =
            message.event === "bar_order_ready" ? "BAR" : "KITCHEN";
          const alert: DepartmentReadyAlert = {
            key: `${department}-${orderId}`,
            orderId,
            tableNumber: String(data.table_number ?? "Bez stolika"),
            department,
          };

          playReadyChime();
          setDepartmentReadyAlerts((current) => [
            ...current.filter((item) => item.key !== alert.key),
            alert,
          ].slice(-4));
        }
      },
    });
  }, [currentShift, token, user?.id, user?.role]);

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

      {(qrOrderAlert || departmentReadyAlerts.length > 0) && (
        <div className="live-alert-stack">
          {qrOrderAlert && (
            <aside className="qr-order-alert" role="alert" aria-live="assertive">
              <div className="qr-order-alert-heading">
                <span className="qr-order-alert-icon">QR</span>
                <div>
                  <span className="eyebrow">Nowe zamówienie</span>
                  <strong>Oczekuje na potwierdzenie</strong>
                </div>
                <button
                  type="button"
                  className="qr-order-alert-close"
                  aria-label="Zamknij powiadomienie"
                  onClick={() => setQrOrderAlert(null)}
                />
              </div>
              <div className="qr-order-alert-details">
                <span>Stolik {qrOrderAlert.tableNumber}</span>
                <span>{qrOrderAlert.guestCount} os.</span>
                <strong>{formatAlertMoney(qrOrderAlert.totalAmount)}</strong>
              </div>
              <button
                type="button"
                className="qr-order-alert-open"
                onClick={() => {
                  sessionStorage.setItem("gastroflow:open-qr-order-id", String(qrOrderAlert.orderId));
                  window.dispatchEvent(new Event("gastroflow:open-qr-order"));
                  setQrOrderAlert(null);
                  navigate(routes.waiter);
                }}
              >
                Zobacz zamówienie
              </button>
            </aside>
          )}

          {departmentReadyAlerts.map((alert) => {
            const isBar = alert.department === "BAR";
            return (
              <aside
                key={alert.key}
                className={`qr-order-alert department-ready-alert ${isBar ? "bar" : "kitchen"}`}
                role="alert"
                aria-live="assertive"
              >
                <div className="qr-order-alert-heading">
                  <span className="qr-order-alert-icon">
                    {isBar ? "BAR" : "K"}
                  </span>
                  <div>
                    <span className="eyebrow">
                      {isBar ? "Bar gotowy" : "Kuchnia gotowa"}
                    </span>
                    <strong>
                      {isBar
                        ? "Wszystkie napoje są gotowe"
                        : "Wszystkie dania są gotowe"}
                    </strong>
                  </div>
                  <button
                    type="button"
                    className="qr-order-alert-close"
                    aria-label="Zamknij powiadomienie"
                    onClick={() =>
                      setDepartmentReadyAlerts((current) =>
                        current.filter((item) => item.key !== alert.key)
                      )
                    }
                  />
                </div>
                <div className="qr-order-alert-details">
                  <span>Stolik {alert.tableNumber}</span>
                  <span>Zam. #{alert.orderId}</span>
                </div>
                <button
                  type="button"
                  className="qr-order-alert-open"
                  onClick={() => {
                    sessionStorage.setItem("gastroflow:open-order-id", String(alert.orderId));
                    window.dispatchEvent(new Event("gastroflow:open-order"));
                    setDepartmentReadyAlerts((current) =>
                      current.filter((item) => item.key !== alert.key)
                    );
                    navigate(routes.waiter);
                  }}
                >
                  Zobacz rachunek
                </button>
              </aside>
            );
          })}
        </div>
      )}
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
      setShiftError(exc instanceof ApiError ? exc.message : "Nie udało się zaktualizować zmiany.");
    } finally {
      setIsShiftChanging(false);
    }
  }
}

function formatAlertMoney(value: string): string {
  return new Intl.NumberFormat("pl-PL", {
    style: "currency",
    currency: "PLN",
  }).format(Number(value));
}

const playReadyChime = () => {
  try {
    const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    
    osc.type = "sine";
    osc.frequency.setValueAtTime(523.25, audioCtx.currentTime); // C5
    osc.frequency.setValueAtTime(659.25, audioCtx.currentTime + 0.15); // E5
    
    gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.5);
    
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    
    osc.start();
    osc.stop(audioCtx.currentTime + 0.5);
  } catch (e) {
    console.error("Failed playing ready chime", e);
  }
};
