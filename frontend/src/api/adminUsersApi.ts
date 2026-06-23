import { apiRequest } from "./apiClient";
import type { UserRole } from "../shared/types";

export type AdminUser = {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  role: UserRole;
  kitchen_section_id: number | null;
  kitchen_section_name: string | null;
  is_active: boolean;
  has_pin: boolean;
  created_at: string;
};

export type AdminKitchenSectionOption = {
  id: number;
  name: string;
  is_active: boolean;
};

export type AdminUsersOptions = {
  roles: UserRole[];
  kitchen_sections: AdminKitchenSectionOption[];
};

export type AdminUserCreatePayload = {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  pin: string;
  role: UserRole;
  kitchen_section_id: number | null;
  is_active: boolean;
};

export type AdminUserUpdatePayload = Partial<AdminUserCreatePayload>;

type AdminUserFilters = {
  search?: string;
  role?: UserRole | "ALL";
  is_active?: "ACTIVE" | "INACTIVE" | "ALL";
};

export async function getAdminUsers(
  token: string,
  filters: AdminUserFilters = {},
): Promise<AdminUser[]> {
  const params = new URLSearchParams();
  if (filters.search?.trim()) {
    params.set("search", filters.search.trim());
  }
  if (filters.role && filters.role !== "ALL") {
    params.set("role", filters.role);
  }
  if (filters.is_active === "ACTIVE") {
    params.set("is_active", "true");
  }
  if (filters.is_active === "INACTIVE") {
    params.set("is_active", "false");
  }

  const query = params.toString();
  return apiRequest<AdminUser[]>(`/admin/users${query ? `?${query}` : ""}`, { token });
}

export async function getAdminUsersOptions(token: string): Promise<AdminUsersOptions> {
  return apiRequest<AdminUsersOptions>("/admin/users/options", { token });
}

export async function createAdminUser(
  token: string,
  body: AdminUserCreatePayload,
): Promise<AdminUser> {
  return apiRequest<AdminUser>("/admin/users", { method: "POST", token, body });
}

export async function updateAdminUser(
  token: string,
  userId: number,
  body: AdminUserUpdatePayload,
): Promise<AdminUser> {
  return apiRequest<AdminUser>(`/admin/users/${userId}`, { method: "PATCH", token, body });
}

export async function deactivateAdminUser(token: string, userId: number): Promise<AdminUser> {
  return apiRequest<AdminUser>(`/admin/users/${userId}/deactivate`, { method: "PATCH", token });
}

export async function activateAdminUser(token: string, userId: number): Promise<AdminUser> {
  return apiRequest<AdminUser>(`/admin/users/${userId}/activate`, { method: "PATCH", token });
}
