import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";

import { ApiError } from "../api/apiClient";
import { useAuth } from "../auth/useAuth";
import { routes } from "../routes/routePaths";

export function LoginPage() {
  const { isAuthenticated, login } = useAuth();
  const [username, setUsername] = useState("admin@gastroflow.dev");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (isAuthenticated) {
    return <Navigate to={routes.dashboard} replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login(username, password);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Login failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel">
        <div>
          <span className="eyebrow">POS platform</span>
          <h1>GastroFlow</h1>
          <p className="muted">
            Sign in to open the correct workspace for your role.
          </p>
        </div>

        <form className="form-stack" onSubmit={handleSubmit}>
          <label>
            Email
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </label>

          {error && <div className="error-box">{error}</div>}

          <button type="submit" className="primary-button" disabled={isSubmitting}>
            {isSubmitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
