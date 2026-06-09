import { createContext, useContext, useState, ReactNode } from "react";
import { OnScreenKeyboard } from "./OnScreenKeyboard";
import { useTouchKeyboard } from "./TouchKeyboardProvider";

type PromptOptions = {
  title: string;
  label?: string;
  defaultValue?: string;
  type?: "text" | "number" | "password";
  keyboardMode?: "numeric" | "decimal" | "text";
  confirmText?: string;
  cancelText?: string;
};

type ConfirmOptions = {
  title: string;
  message?: string;
  confirmText?: string;
  cancelText?: string;
};

type PromptContextType = {
  prompt: (options: PromptOptions | string) => Promise<string | null>;
  confirm: (options: ConfirmOptions | string) => Promise<boolean>;
};

const PromptContext = createContext<PromptContextType | null>(null);

export function usePrompt() {
  const context = useContext(PromptContext);
  if (!context) {
    throw new Error("usePrompt must be used within a PromptProvider");
  }
  return context;
}

export function PromptProvider({ children }: { children: ReactNode }) {
  const { closeKeyboard } = useTouchKeyboard();
  const [promptState, setPromptState] = useState<{
    isOpen: boolean;
    options: PromptOptions;
    resolve: (value: string | null) => void;
    value: string;
  } | null>(null);

  const [confirmState, setConfirmState] = useState<{
    isOpen: boolean;
    options: ConfirmOptions;
    resolve: (value: boolean) => void;
  } | null>(null);

  const prompt = (options: PromptOptions | string) => {
    return new Promise<string | null>((resolve) => {
      closeKeyboard();
      const opts = typeof options === "string" ? { title: options } : options;
      setPromptState({
        isOpen: true,
        options: opts,
        resolve,
        value: opts.defaultValue ?? "",
      });
    });
  };

  const confirm = (options: ConfirmOptions | string) => {
    return new Promise<boolean>((resolve) => {
      closeKeyboard();
      const opts = typeof options === "string" ? { title: options } : options;
      setConfirmState({
        isOpen: true,
        options: opts,
        resolve,
      });
    });
  };

  const handlePromptConfirm = () => {
    if (promptState) {
      promptState.resolve(promptState.value);
      setPromptState(null);
    }
  };

  const handlePromptCancel = () => {
    if (promptState) {
      promptState.resolve(null);
      setPromptState(null);
    }
  };

  const handleConfirmYes = () => {
    if (confirmState) {
      confirmState.resolve(true);
      setConfirmState(null);
    }
  };

  const handleConfirmNo = () => {
    if (confirmState) {
      confirmState.resolve(false);
      setConfirmState(null);
    }
  };

  return (
    <PromptContext.Provider value={{ prompt, confirm }}>
      {children}

      {/* Prompt Modal */}
      {promptState?.isOpen && (
        <div className="modal-backdrop" style={{ zIndex: 9999 }}>
          <div
            className="product-options-modal"
            style={{
              maxWidth:
                promptState.options.type === "number"
                || promptState.options.type === "password"
                  ? 460
                  : 760,
              width: "100%",
              gap: "24px",
            }}
          >
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: "1.1rem" }}>{promptState.options.title}</h3>
            </div>
            <div className="form-stack">
              {promptState.options.label && (
                <p className="muted" style={{ margin: 0 }}>
                  {promptState.options.label}
                </p>
              )}
              <input
                autoFocus
                type={promptState.options.type ?? "text"}
                value={promptState.value}
                onChange={(e) =>
                  setPromptState((prev) => (prev ? { ...prev, value: e.target.value } : null))
                }
                onKeyDown={(e) => {
                  if (e.key === "Enter") handlePromptConfirm();
                  if (e.key === "Escape") handlePromptCancel();
                }}
                style={{ width: "100%", padding: "10px", borderRadius: "6px", border: "1px solid #c8d2cc" }}
              />
              <OnScreenKeyboard
                mode={
                  promptState.options.keyboardMode
                  ?? (
                    promptState.options.type === "number"
                    || promptState.options.type === "password"
                      ? "numeric"
                      : "text"
                  )
                }
                value={promptState.value}
                onChange={(value) =>
                  setPromptState((prev) => (prev ? { ...prev, value } : null))
                }
              />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: "8px" }}>
              <button type="button" className="ghost-button" onClick={handlePromptCancel}>
                {promptState.options.cancelText ?? "Cofnij"}
              </button>
              <button type="button" className="primary-button" onClick={handlePromptConfirm}>
                {promptState.options.confirmText ?? "Dalej"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirm Modal */}
      {confirmState?.isOpen && (
        <div className="modal-backdrop" style={{ zIndex: 9999 }}>
          <div className="product-options-modal" style={{ maxWidth: 400, width: "100%", gap: "24px" }}>
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: "1.1rem" }}>{confirmState.options.title}</h3>
            </div>
            {confirmState.options.message && (
              <div>
                <p style={{ margin: 0 }}>{confirmState.options.message}</p>
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: "8px" }}>
              <button type="button" className="ghost-button" onClick={handleConfirmNo}>
                {confirmState.options.cancelText ?? "Cofnij"}
              </button>
              <button type="button" className="primary-button" onClick={handleConfirmYes}>
                {confirmState.options.confirmText ?? "Dalej"}
              </button>
            </div>
          </div>
        </div>
      )}
    </PromptContext.Provider>
  );
}
