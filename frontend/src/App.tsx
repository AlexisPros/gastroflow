import { AuthProvider } from "./auth/AuthContext";
import { AppRouter } from "./routes/AppRouter";
import { PromptProvider } from "./components/PromptProvider";

export function App() {
  return (
    <PromptProvider>
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
    </PromptProvider>
  );
}
