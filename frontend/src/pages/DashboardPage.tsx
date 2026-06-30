import { Link, useOutletContext } from "react-router-dom";

import { useAuth } from "../auth/useAuth";
import type { UserRole } from "../shared/types";
import { routes } from "../routes/routePaths";
import type { AppOutletContext } from "../layouts/AppLayout";

type DashboardAction = {
  title: string;
  description: string;
  path: string;
  roles: UserRole[];
};

const actions: DashboardAction[] = [
  {
    title: "Plan sali",
    description: "Otwórz mapę sali i wybierz aktywne stoliki.",
    path: routes.floor,
    roles: ["ADMIN", "MANAGER", "WAITER"],
  },
  {
    title: "Panel kelnera",
    description: "Twórz zamówienia, potwierdzaj zamówienia QR, płatności i paragony.",
    path: routes.waiter,
    roles: ["ADMIN", "MANAGER", "WAITER"],
  },
  {
    title: "Ekran kuchni",
    description: "Śledź zadania kuchenne z przyjętych zamówień.",
    path: routes.kitchen,
    roles: ["ADMIN", "MANAGER", "KITCHEN", "CHEF", "WYDAWKA"],
  },
  {
    title: "Ekran baru",
    description: "Obsługuj zadania baru i aktualizacje w czasie rzeczywistym.",
    path: routes.bar,
    roles: ["ADMIN", "MANAGER", "BARTENDER"],
  },
  {
    title: "Raporty",
    description: "Przeglądaj raporty zmianowe i dzienne operacje.",
    path: routes.reports,
    roles: ["ADMIN", "MANAGER"],
  },
  {
    title: "Rezerwacje",
    description: "Sprawdź gości, stoliki, terminy i przedzamówienia.",
    path: routes.reservations,
    roles: ["ADMIN", "MANAGER", "WAITER", "KITCHEN", "CHEF", "WYDAWKA", "BARTENDER"],
  },
  {
    title: "Magazyn",
    description: "Kontroluj stany, dokumenty PZ, MM i RW oraz alerty niskiego stanu.",
    path: routes.warehouse,
    roles: ["ADMIN", "MANAGER", "WAITER", "KITCHEN", "CHEF", "WYDAWKA", "BARTENDER"],
  },
  {
    title: "Menu",
    description: "Zarządzaj kategoriami, produktami, składnikami i rabatami.",
    path: routes.adminMenu,
    roles: ["ADMIN"],
  },
  {
    title: "Pracownicy",
    description: "Twórz konta pracowników, role, PIN-y i dostęp do sekcji kuchni.",
    path: routes.adminUsers,
    roles: ["ADMIN"],
  },
];

export function DashboardPage() {
  const { user } = useAuth();
  const { hasWarehouseAccess } = useOutletContext<AppOutletContext>();
  const availableActions = user
    ? actions.filter(
        (action) => action.roles.includes(user.role)
          && (action.path !== routes.warehouse || hasWarehouseAccess),
      )
    : [];

  return (
    <section className="page-stack">
      <div>
        <span className="eyebrow">Obszar roboczy</span>
        <h1>Panel główny</h1>
      </div>

      <div className="action-grid">
        {availableActions.map((action) => (
          <Link key={action.path} to={action.path} className="action-card">
            <h2>{action.title}</h2>
            <p>{action.description}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
