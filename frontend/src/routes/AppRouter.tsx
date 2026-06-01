import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { AppLayout } from "../layouts/AppLayout";
import { DashboardPage } from "../pages/DashboardPage";
import { LoginPage } from "../pages/LoginPage";
import { PlaceholderPage } from "../pages/PlaceholderPage";
import { ProtectedRoute } from "./ProtectedRoute";
import { routes } from "./routePaths";

const router = createBrowserRouter([
  {
    path: routes.login,
    element: <LoginPage />,
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
                element: (
                  <PlaceholderPage
                    title="Floor Plan"
                    description="Room map, table selection and live table statuses."
                  />
                ),
              },
              {
                path: routes.waiter,
                element: (
                  <PlaceholderPage
                    title="Waiter POS"
                    description="Order creation, QR confirmation, payments and receipts."
                  />
                ),
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
            element: <ProtectedRoute allowedRoles={["ADMIN", "MANAGER"]} />,
            children: [
              {
                path: routes.reports,
                element: (
                  <PlaceholderPage
                    title="Reports"
                    description="Shift reports, daily sales, kitchen and bar reporting."
                  />
                ),
              },
            ],
          },
          {
            element: <ProtectedRoute allowedRoles={["ADMIN"]} />,
            children: [
              {
                path: routes.admin,
                element: (
                  <PlaceholderPage
                    title="Admin"
                    description="Users, resources, menu data and system configuration."
                  />
                ),
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
