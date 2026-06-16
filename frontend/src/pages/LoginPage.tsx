import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";

import { ApiError } from "../api/apiClient";
import { useAuth } from "../auth/useAuth";
import { OnScreenKeyboard } from "../components/OnScreenKeyboard";
import { routes } from "../routes/routePaths";

export function LoginPage() {
  const { isAuthenticated, login } = useAuth();
  const [pin, setPin] = useState("");
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
      await login(pin);
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
          <span className="eyebrow">GastroFlow POS</span>
          <h1>GastroFlow</h1>
          <p className="muted">Wpisz swój PIN, aby otworzyć stanowisko.</p>
        </div>

        <form className="form-stack" onSubmit={handleSubmit}>
          <label className="pin-login-field">
            PIN
            <input
              type="password"
              inputMode="numeric"
              value={pin}
              onChange={(event) => setPin(event.target.value.replace(/\D/g, "").slice(0, 8))}
              autoComplete="off"
              autoFocus
            />
          </label>

          {error && <div className="error-box">{error}</div>}

          <OnScreenKeyboard
            mode="numeric"
            value={pin}
            onChange={setPin}
            onSubmit={() => {
              if (!isSubmitting && pin) {
                document.querySelector<HTMLFormElement>(".login-panel form")?.requestSubmit();
              }
            }}
            submitLabel="Zaloguj"
            maxLength={8}
          />
        </form>
      </section>
    </main>
  );
}
