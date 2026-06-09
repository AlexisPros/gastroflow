import {
  useCallback,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import { loginWithPin } from "../api/authApi";
import { AuthContext, type AuthContextValue } from "./authContextCore";
import { clearStoredAuth, loadStoredAuth, saveStoredAuth } from "./authStorage";

export function AuthProvider({ children }: PropsWithChildren) {
  const [auth, setAuth] = useState(() => loadStoredAuth());

  const login = useCallback(async (pin: string) => {
    const response = await loginWithPin(pin);
    const nextAuth = {
      access_token: response.access_token,
      user: response.user,
    };
    saveStoredAuth(nextAuth);
    setAuth(nextAuth);
  }, []);

  const logout = useCallback(() => {
    clearStoredAuth();
    setAuth(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: auth?.user ?? null,
      token: auth?.access_token ?? null,
      isAuthenticated: Boolean(auth?.access_token),
      login,
      logout,
    }),
    [auth, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
