import { useCallback, useEffect, useMemo, useState } from "react";

import {
  activateAdminUser,
  createAdminUser,
  deactivateAdminUser,
  getAdminUsers,
  getAdminUsersOptions,
  updateAdminUser,
  type AdminUser,
  type AdminUserCreatePayload,
  type AdminUsersOptions,
} from "../api/adminUsersApi";
import { ApiError } from "../api/apiClient";
import { useAuth } from "../auth/useAuth";
import { usePrompt } from "../components/PromptProvider";
import type { UserRole } from "../shared/types";

type UserStatusFilter = "ACTIVE" | "INACTIVE" | "ALL";

type UserFormState = {
  id: number | null;
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  pin: string;
  role: UserRole;
  kitchen_section_id: number | null;
  is_active: boolean;
};

const emptyOptions: AdminUsersOptions = {
  roles: ["ADMIN", "MANAGER", "WAITER", "KITCHEN", "CHEF", "WYDAWKA", "BARTENDER"],
  kitchen_sections: [],
};

const roleLabels: Record<UserRole, string> = {
  ADMIN: "Admin",
  MANAGER: "Manager",
  WAITER: "Kelner",
  KITCHEN: "Kuchnia",
  CHEF: "Szef kuchni",
  WYDAWKA: "Wydawka",
  BARTENDER: "Bar",
};

const statusLabels: Record<UserStatusFilter, string> = {
  ACTIVE: "Aktywni",
  INACTIVE: "Nieaktywni",
  ALL: "Wszyscy",
};

export function AdminUsersPage() {
  const { token } = useAuth();
  const { confirm } = usePrompt();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [options, setOptions] = useState<AdminUsersOptions>(emptyOptions);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<UserRole | "ALL">("ALL");
  const [statusFilter, setStatusFilter] = useState<UserStatusFilter>("ACTIVE");
  const [form, setForm] = useState<UserFormState>(() => createEmptyUserForm());
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const activeKitchenSections = useMemo(
    () => options.kitchen_sections.filter((section) => section.is_active),
    [options.kitchen_sections],
  );

  const loadUsers = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    setError(null);
    try {
      const [nextUsers, nextOptions] = await Promise.all([
        getAdminUsers(token, {
          search,
          role: roleFilter,
          is_active: statusFilter,
        }),
        getAdminUsersOptions(token),
      ]);
      setUsers(nextUsers);
      setOptions(nextOptions);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Nie udało się pobrać pracowników.");
    } finally {
      setIsLoading(false);
    }
  }, [roleFilter, search, statusFilter, token]);

  useEffect(() => {
    if (!token) return;
    void loadUsers();
  }, [loadUsers, token]);

  function openCreateModal() {
    setForm(createEmptyUserForm(activeKitchenSections[0]?.id ?? null));
    setError(null);
    setNotice(null);
    setIsModalOpen(true);
  }

  function openEditModal(user: AdminUser) {
    setForm({
      id: user.id,
      first_name: user.first_name,
      last_name: user.last_name,
      email: user.email,
      password: "",
      pin: "",
      role: user.role,
      kitchen_section_id: user.kitchen_section_id,
      is_active: user.is_active,
    });
    setError(null);
    setNotice(null);
    setIsModalOpen(true);
  }

  async function saveUser() {
    if (!token) return;
    setIsSaving(true);
    setError(null);
    try {
      if (form.id === null) {
        await createAdminUser(token, formToCreatePayload(form));
        setNotice("Pracownik został utworzony.");
      } else {
        await updateAdminUser(token, form.id, formToUpdatePayload(form));
        setNotice("Dane pracownika zostały zapisane.");
      }
      setIsModalOpen(false);
      await loadUsers();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Nie udało się zapisać pracownika.");
    } finally {
      setIsSaving(false);
    }
  }

  async function toggleUserStatus(user: AdminUser) {
    if (!token) return;
    const yes = await confirm({
      title: user.is_active ? "Dezaktywuj pracownika" : "Aktywuj pracownika",
      message: user.is_active
        ? `Czy na pewno chcesz dezaktywować ${user.first_name} ${user.last_name}?`
        : `Czy na pewno chcesz aktywować ${user.first_name} ${user.last_name}?`,
      confirmText: user.is_active ? "Dezaktywuj" : "Aktywuj",
      cancelText: "Anuluj",
    });
    if (!yes) return;

    setError(null);
    try {
      if (user.is_active) {
        await deactivateAdminUser(token, user.id);
      } else {
        await activateAdminUser(token, user.id);
      }
      await loadUsers();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Nie udało się zmienić statusu pracownika.");
    }
  }

  if (isLoading) {
    return <section className="page-stack"><h1>Ładowanie pracowników...</h1></section>;
  }

  return (
    <section className="admin-users-page">
      <header className="admin-menu-header">
        <div>
          <span className="eyebrow">Admin</span>
          <h1>Pracownicy</h1>
        </div>
        <div className="admin-users-header-actions">
          <button type="button" className="ghost-button" onClick={() => void loadUsers()}>
            Odśwież
          </button>
          <button type="button" className="admin-primary" onClick={openCreateModal}>
            Nowy pracownik
          </button>
        </div>
      </header>

      {error && <p className="form-error">{error}</p>}
      {notice && <p className="form-notice">{notice}</p>}

      <section className="admin-panel admin-users-filters">
        <label>
          Szukaj
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Imię, nazwisko lub email"
          />
        </label>
        <label>
          Rola
          <select
            value={roleFilter}
            onChange={(event) => setRoleFilter(event.target.value as UserRole | "ALL")}
          >
            <option value="ALL">Wszystkie role</option>
            {options.roles.map((role) => (
              <option key={role} value={role}>
                {roleLabels[role]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as UserStatusFilter)}
          >
            {(Object.keys(statusLabels) as UserStatusFilter[]).map((status) => (
              <option key={status} value={status}>
                {statusLabels[status]}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="admin-panel admin-users-list-panel">
        <div className="admin-users-list-heading">
          <span>Pracownik</span>
          <span>Rola</span>
          <span>Sekcja</span>
          <span>Status</span>
          <span>Akcje</span>
        </div>

        <div className="admin-users-list">
          {users.map((user) => (
            <article key={user.id} className={`admin-user-row ${!user.is_active ? "inactive" : ""}`}>
              <div>
                <strong>{user.first_name} {user.last_name}</strong>
                <small>{user.email}</small>
              </div>
              <span className="admin-user-role">{roleLabels[user.role]}</span>
              <span>{user.kitchen_section_name ?? "—"}</span>
              <span className={user.is_active ? "status-pill active" : "status-pill inactive-status"}>
                {user.is_active ? "Aktywny" : "Nieaktywny"}
              </span>
              <div className="admin-user-actions">
                <button type="button" className="info-link" onClick={() => openEditModal(user)}>
                  Edytuj
                </button>
                <button
                  type="button"
                  className={user.is_active ? "danger-link" : "success-link"}
                  onClick={() => void toggleUserStatus(user)}
                >
                  {user.is_active ? "Dezaktywuj" : "Aktywuj"}
                </button>
              </div>
            </article>
          ))}
          {users.length === 0 && (
            <p className="admin-users-empty">Brak pracowników dla wybranych filtrów.</p>
          )}
        </div>
      </section>

      {isModalOpen && (
        <div className="admin-modal-backdrop">
          <section className="admin-modal admin-user-modal">
            <div className="admin-panel-heading split">
              <h2>{form.id === null ? "Nowy pracownik" : "Edycja pracownika"}</h2>
              <button type="button" className="ghost-button" onClick={() => setIsModalOpen(false)}>
                Zamknij
              </button>
            </div>

            <div className="admin-form-grid">
              <label>
                Imię
                <input
                  value={form.first_name}
                  onChange={(event) => setForm({ ...form, first_name: event.target.value })}
                />
              </label>
              <label>
                Nazwisko
                <input
                  value={form.last_name}
                  onChange={(event) => setForm({ ...form, last_name: event.target.value })}
                />
              </label>
              <label>
                Email
                <input
                  type="email"
                  value={form.email}
                  onChange={(event) => setForm({ ...form, email: event.target.value })}
                />
              </label>
              <label>
                Rola
                <select
                  value={form.role}
                  onChange={(event) => {
                    const role = event.target.value as UserRole;
                    setForm({
                      ...form,
                      role,
                      kitchen_section_id:
                        role === "KITCHEN"
                          ? form.kitchen_section_id ?? activeKitchenSections[0]?.id ?? null
                          : null,
                    });
                  }}
                >
                  {options.roles.map((role) => (
                    <option key={role} value={role}>
                      {roleLabels[role]}
                    </option>
                  ))}
                </select>
              </label>
              {form.role === "KITCHEN" && (
                <label className="wide">
                  Sekcja kuchni
                  <select
                    value={form.kitchen_section_id ?? ""}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        kitchen_section_id: event.target.value ? Number(event.target.value) : null,
                      })
                    }
                  >
                    <option value="" disabled>Wybierz sekcję</option>
                    {activeKitchenSections.map((section) => (
                      <option key={section.id} value={section.id}>
                        {section.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label>
                Hasło {form.id !== null && <small>zostaw puste, jeśli bez zmian</small>}
                <input
                  type="password"
                  value={form.password}
                  onChange={(event) => setForm({ ...form, password: event.target.value })}
                />
              </label>
              <label>
                PIN {form.id !== null && <small>zostaw pusty, jeśli bez zmian</small>}
                <input
                  inputMode="numeric"
                  value={form.pin}
                  onChange={(event) => setForm({ ...form, pin: event.target.value })}
                />
              </label>
              <label className="switch-row compact wide">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
                />
                Aktywny
              </label>
            </div>

            <div className="admin-form-actions">
              <button type="button" className="ghost-button" onClick={() => setIsModalOpen(false)}>
                Anuluj
              </button>
              <button
                type="button"
                className="admin-primary"
                disabled={isSaving}
                onClick={() => void saveUser()}
              >
                {isSaving ? "Zapisywanie..." : "Zapisz pracownika"}
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

function createEmptyUserForm(kitchenSectionId: number | null = null): UserFormState {
  return {
    id: null,
    first_name: "",
    last_name: "",
    email: "",
    password: "",
    pin: "",
    role: "WAITER",
    kitchen_section_id: kitchenSectionId,
    is_active: true,
  };
}

function formToCreatePayload(form: UserFormState): AdminUserCreatePayload {
  return {
    first_name: form.first_name.trim(),
    last_name: form.last_name.trim(),
    email: form.email.trim(),
    password: form.password,
    pin: form.pin,
    role: form.role,
    kitchen_section_id: form.role === "KITCHEN" ? form.kitchen_section_id : null,
    is_active: form.is_active,
  };
}

function formToUpdatePayload(form: UserFormState) {
  const payload: Partial<AdminUserCreatePayload> = {
    first_name: form.first_name.trim(),
    last_name: form.last_name.trim(),
    email: form.email.trim(),
    role: form.role,
    kitchen_section_id: form.role === "KITCHEN" ? form.kitchen_section_id : null,
    is_active: form.is_active,
  };

  if (form.password.trim()) {
    payload.password = form.password;
  }

  if (form.pin.trim()) {
    payload.pin = form.pin;
  }

  return payload;
}
