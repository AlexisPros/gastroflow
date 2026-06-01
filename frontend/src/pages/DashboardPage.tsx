import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
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
    title: "Floor Plan",
    description: "Open the room map and select active tables.",
    path: routes.floor,
    roles: ["ADMIN", "MANAGER", "WAITER"],
  },
  {
    title: "Waiter POS",
    description: "Create orders, confirm QR orders, payments and receipts.",
    path: routes.waiter,
    roles: ["ADMIN", "MANAGER", "WAITER"],
  },
  {
    title: "Kitchen Display",
    description: "Track production tasks from accepted orders.",
    path: routes.kitchen,
    roles: ["ADMIN", "MANAGER", "KITCHEN"],
  },
  {
    title: "Bar Display",
    description: "Handle drink tasks and live bar updates.",
    path: routes.bar,
    roles: ["ADMIN", "MANAGER", "BARTENDER"],
  },
  {
    title: "Reports",
    description: "Review shift reports and daily operations.",
    path: routes.reports,
    roles: ["ADMIN", "MANAGER"],
  },
  {
    title: "Admin",
    description: "Manage users, menu resources and system settings.",
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
        <span className="eyebrow">Workspace</span>
        <h1>Dashboard</h1>
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
