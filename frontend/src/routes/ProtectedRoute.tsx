import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../auth/useAuth";
import type { UserRole } from "../shared/types";
import { routes } from "./routePaths";

type ProtectedRouteProps = {
  allowedRoles?: UserRole[];
};

export function ProtectedRoute({ allowedRoles }: ProtectedRouteProps) {
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to={routes.login} replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return <Navigate to={routes.dashboard} replace />;
  }

  return <Outlet />;
}
