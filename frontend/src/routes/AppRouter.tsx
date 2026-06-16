import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { AppLayout } from "../layouts/AppLayout";
import { DashboardPage } from "../pages/DashboardPage";
import { FloorPlanPage } from "../pages/FloorPlanPage";
import { GuestQrPage } from "../pages/GuestQrPage";
import { LoginPage } from "../pages/LoginPage";
import { AdminMenuPage } from "../pages/AdminMenuPage";
import { PlaceholderPage } from "../pages/PlaceholderPage";
import { ReportsPage } from "../pages/ReportsPage";
import { WaiterPage } from "../pages/WaiterPage";
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
            element: <ProtectedRoute allowedRoles={["ADMIN", "MANAGER", "KITCHEN"]} />,
            children: [
              {
                path: routes.kitchen,
                element: (
                  <PlaceholderPage
                    title="Kitchen Display"
                    description="Kitchen production board with real-time task updates."
                  />
                ),
              },
            ],
          },
          {
            element: <ProtectedRoute allowedRoles={["ADMIN", "MANAGER", "BARTENDER"]} />,
            children: [
              {
                path: routes.bar,
                element: (
                  <PlaceholderPage
                    title="Bar Display"
                    description="Bar tasks, drink preparation and live order updates."
                  />
                ),
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
