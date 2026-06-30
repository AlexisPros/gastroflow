import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { AppLayout } from "../layouts/AppLayout";
import { DashboardPage } from "../pages/DashboardPage";
import { FloorPlanPage } from "../pages/FloorPlanPage";
import { GuestQrPage } from "../pages/GuestQrPage";
import { LoginPage } from "../pages/LoginPage";
import { AdminMenuPage } from "../pages/AdminMenuPage";
import { AdminUsersPage } from "../pages/AdminUsersPage";
import { ReportsPage } from "../pages/ReportsPage";
import { WaiterPage } from "../pages/WaiterPage";
import { KitchenPage } from "../pages/KitchenPage";
import { BarPage } from "../pages/BarPage";
import { WarehousePage } from "../pages/WarehousePage";
import { ReservationsPage } from "../pages/ReservationsPage";
import { ProtectedRoute } from "./ProtectedRoute";
import { routes } from "./routePaths";

const router = createBrowserRouter([
  {
    path: routes.login,
    element: <LoginPage />,
  },
  {
    path: routes.guestQr,
    element: <GuestQrPage />,
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          {
            path: routes.dashboard,
            element: <DashboardPage />,
          },
          {
            element: <ProtectedRoute allowedRoles={["ADMIN", "MANAGER", "WAITER"]} />,
            children: [
              {
                path: routes.floor,
                element: <FloorPlanPage />,
              },
              {
                path: routes.waiter,
                element: <WaiterPage />,
              },
            ],
          },
          {
            element: <ProtectedRoute allowedRoles={["ADMIN", "MANAGER", "WAITER", "KITCHEN", "CHEF", "WYDAWKA", "BARTENDER"]} />,
            children: [
              {
                path: routes.reservations,
                element: <ReservationsPage />,
              },
              {
                path: routes.warehouse,
                element: <WarehousePage />,
              },
            ],
          },
          {
            element: <ProtectedRoute allowedRoles={["ADMIN", "MANAGER", "KITCHEN", "CHEF", "WYDAWKA"]} />,
            children: [
              {
                path: routes.kitchen,
                element: <KitchenPage />,
              },
            ],
          },
          {
            element: <ProtectedRoute allowedRoles={["ADMIN", "MANAGER", "BARTENDER"]} />,
            children: [
              {
                path: routes.bar,
                element: <BarPage />,
              },
            ],
          },
          {
            element: <ProtectedRoute allowedRoles={["ADMIN", "MANAGER", "WAITER"]} />,
            children: [
              {
                path: routes.reports,
                element: <ReportsPage />,
              },
            ],
          },
          {
            element: <ProtectedRoute allowedRoles={["ADMIN"]} />,
            children: [
              {
                path: routes.admin,
                element: <AdminMenuPage />,
              },
              {
                path: routes.adminMenu,
                element: <AdminMenuPage />,
              },
              {
                path: routes.adminUsers,
                element: <AdminUsersPage />,
              },
            ],
          },
        ],
      },
    ],
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
