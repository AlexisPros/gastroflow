type OnScreenKeyboardProps = {
  mode: "numeric" | "decimal" | "text";
  value: string;
  onChange: (value: string) => void;
  onSubmit?: () => void;
  submitLabel?: string;
  maxLength?: number;
};

const textRows = [
  ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
  ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
  ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
  ["Z", "X", "C", "V", "B", "N", "M"],
  ["Ą", "Ć", "Ę", "Ł", "Ń", "Ó", "Ś", "Ź", "Ż", ".", ",", "-"],
];

export function OnScreenKeyboard({
  mode,
  value,
  onChange,
  onSubmit,
  submitLabel = "Dalej",
  maxLength,
}: OnScreenKeyboardProps) {
  const append = (character: string) => {
    if (maxLength !== undefined && value.length >= maxLength) {
      return;
    }
    onChange(value + character);
  };

  if (mode === "numeric" || mode === "decimal") {
    const appendDecimalSeparator = () => {
      if (value.includes(",") || value.includes(".")) {
        return;
      }
      append(value ? "." : "0.");
    };

    return (
      <div className="screen-keyboard numeric-keyboard" aria-label="Klawiatura numeryczna">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((key) => (
          <button key={key} type="button" onClick={() => append(key)}>
            {key}
          </button>
        ))}
        {mode === "decimal" ? (
          <button type="button" onClick={appendDecimalSeparator} aria-label="Separator dziesiętny">
            ,
          </button>
        ) : (
          <button type="button" className="keyboard-action" onClick={() => onChange("")}>
            Wyczyść
          </button>
        )}
        <button type="button" onClick={() => append("0")}>0</button>
        <button
          type="button"
          className="keyboard-action"
          onClick={() => onChange(value.slice(0, -1))}
          aria-label="Usuń ostatni znak"
        >
          Usuń
        </button>
        {mode === "decimal" && (
          <button type="button" className="keyboard-action keyboard-clear" onClick={() => onChange("")}>
            Wyczyść
          </button>
        )}
        {onSubmit && (
          <button type="button" className="keyboard-submit" onClick={onSubmit}>
            {submitLabel}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="screen-keyboard text-keyboard" aria-label="Klawiatura ekranowa">
      {textRows.map((row, index) => (
        <div className="keyboard-row" key={index}>
          {row.map((key) => (
            <button key={key} type="button" onClick={() => append(key.toLowerCase())}>
              {key}
            </button>
          ))}
        </div>
      ))}
      <div className="keyboard-row keyboard-controls">
        <button type="button" onClick={() => onChange(value + " ")}>Spacja</button>
        <button type="button" onClick={() => onChange(value.slice(0, -1))}>Usuń</button>
        <button type="button" onClick={() => onChange("")}>Wyczyść</button>
        {onSubmit && <button type="button" onClick={onSubmit}>{submitLabel}</button>}
      </div>
    </div>
  );
}
