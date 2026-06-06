import { Link } from "react-router-dom";

import { useAuth } from "../auth/useAuth";
import type { UserRole } from "../shared/types";
import { routes } from "../routes/routePaths";

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
    roles: ["ADMIN", "MANAGER", "KITCHEN"],
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
    title: "Admin",
    description: "Zarządzaj użytkownikami, menu i ustawieniami systemu.",
    path: routes.admin,
    roles: ["ADMIN"],
  },
];

export function DashboardPage() {
  const { user } = useAuth();
  const availableActions = user
    ? actions.filter((action) => action.roles.includes(user.role))
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
