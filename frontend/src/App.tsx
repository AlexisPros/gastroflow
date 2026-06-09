import { AuthProvider } from "./auth/AuthContext";
import { AppRouter } from "./routes/AppRouter";
import { PromptProvider } from "./components/PromptProvider";
import { TouchKeyboardProvider } from "./components/TouchKeyboardProvider";

export function App() {
  return (
    <TouchKeyboardProvider>
      <PromptProvider>
        <AuthProvider>
          <AppRouter />
        </AuthProvider>
      </PromptProvider>
    </TouchKeyboardProvider>
  );
}
