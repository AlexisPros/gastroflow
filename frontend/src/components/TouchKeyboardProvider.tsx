import {
  createContext,
  InputHTMLAttributes,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useState,
} from "react";

import { OnScreenKeyboard } from "./OnScreenKeyboard";

export type TouchKeyboardMode = "numeric" | "decimal" | "text";

type KeyboardState = {
  inputId: string;
  label: string;
  maxLength?: number;
  mode: TouchKeyboardMode;
  onChange: (value: string) => void;
  value: string;
};

type TouchKeyboardContextType = {
  activeInputId: string | null;
  closeKeyboard: (inputId?: string) => void;
  openKeyboard: (state: KeyboardState) => void;
  updateKeyboardValue: (inputId: string, value: string) => void;
};

const TouchKeyboardContext = createContext<TouchKeyboardContextType | null>(null);

export function TouchKeyboardProvider({ children }: { children: ReactNode }) {
  const [keyboard, setKeyboard] = useState<KeyboardState | null>(null);

  useEffect(() => {
    document.body.classList.toggle("touch-keyboard-open", keyboard !== null);
    return () => document.body.classList.remove("touch-keyboard-open");
  }, [keyboard]);

  const closeKeyboard = useCallback((inputId?: string) => {
    setKeyboard((current) => (
      inputId && current?.inputId !== inputId
        ? current
        : null
    ));
  }, []);

  const openKeyboard = useCallback((state: KeyboardState) => setKeyboard(state), []);

  const updateKeyboardValue = useCallback((inputId: string, value: string) => {
    setKeyboard((current) => (
      current?.inputId === inputId && current.value !== value
        ? { ...current, value }
        : current
    ));
  }, []);

  const contextValue = useMemo(
    () => ({
      activeInputId: keyboard?.inputId ?? null,
      closeKeyboard,
      openKeyboard,
      updateKeyboardValue,
    }),
    [closeKeyboard, keyboard?.inputId, openKeyboard, updateKeyboardValue],
  );

  return (
    <TouchKeyboardContext.Provider
      value={contextValue}
    >
      {children}
      {keyboard && (
        <aside
          className={`touch-keyboard-dock ${keyboard.mode === "text" ? "text-mode" : "number-mode"}`}
          aria-label={`Klawiatura dla pola ${keyboard.label}`}
        >
          <div className="touch-keyboard-heading">
            <strong>{keyboard.label}</strong>
            <button type="button" className="ghost-button" onClick={() => closeKeyboard()}>
              Zamknij klawiaturę
            </button>
          </div>
          <OnScreenKeyboard
            mode={keyboard.mode}
            value={keyboard.value}
            maxLength={keyboard.maxLength}
            onChange={(value) => {
              setKeyboard((current) => current ? { ...current, value } : current);
              keyboard.onChange(value);
            }}
          />
        </aside>
      )}
    </TouchKeyboardContext.Provider>
  );
}

export function useTouchKeyboard() {
  const context = useContext(TouchKeyboardContext);
  if (!context) {
    throw new Error("TouchInput must be used within TouchKeyboardProvider");
  }
  return context;
}

type TouchInputProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "onChange" | "type" | "value"
> & {
  keyboardLabel: string;
  keyboardMode?: TouchKeyboardMode;
  onValueChange: (value: string) => void;
  type?: InputHTMLAttributes<HTMLInputElement>["type"];
  value: string | number;
};

export function TouchInput({
  keyboardLabel,
  keyboardMode = "text",
  maxLength,
  onFocus,
  onValueChange,
  type,
  value,
  ...props
}: TouchInputProps) {
  const inputId = useId();
  const {
    activeInputId,
    closeKeyboard,
    openKeyboard,
    updateKeyboardValue,
  } = useTouchKeyboard();
  const stringValue = String(value);

  useEffect(() => {
    if (activeInputId === inputId) {
      updateKeyboardValue(inputId, stringValue);
    }
  }, [activeInputId, inputId, stringValue, updateKeyboardValue]);

  useEffect(() => () => closeKeyboard(inputId), [closeKeyboard, inputId]);

  const activateKeyboard = () => {
    openKeyboard({
      inputId,
      label: keyboardLabel,
      maxLength,
      mode: keyboardMode,
      onChange: onValueChange,
      value: stringValue,
    });
  };

  return (
    <input
      {...props}
      maxLength={maxLength}
      type={type ?? (keyboardMode === "numeric" ? "number" : "text")}
      value={value}
      inputMode={
        keyboardMode === "numeric"
          ? "numeric"
          : keyboardMode === "decimal"
            ? "decimal"
            : props.inputMode
      }
      onClick={activateKeyboard}
      onFocus={(event) => {
        activateKeyboard();
        onFocus?.(event);
      }}
      onChange={(event) => {
        onValueChange(event.target.value);
        updateKeyboardValue(inputId, event.target.value);
      }}
    />
  );
}
