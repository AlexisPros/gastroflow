import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../api/apiClient";
import { getPublicQrTable, type PublicQrTable } from "../api/qrApi";

type PageState = "loading" | "ready" | "error";

export function GuestQrPage() {
  const { qrToken = "" } = useParams();
  const [table, setTable] = useState<PublicQrTable | null>(null);
  const [pageState, setPageState] = useState<PageState>("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadTable() {
      try {
        const result = await getPublicQrTable(qrToken);
        if (active) {
          setTable(result);
          setPageState("ready");
        }
      } catch (exc) {
        if (active) {
          setError(
            exc instanceof ApiError
              ? exc.message
              : "Nie udało się otworzyć kodu QR.",
          );
          setPageState("error");
        }
      }
    }

    if (qrToken) {
      void loadTable();
    } else {
      setError("Kod QR jest nieprawidłowy.");
      setPageState("error");
    }

    return () => {
      active = false;
    };
  }, [qrToken]);

  return (
    <main className="guest-qr-page">
      <section className="guest-qr-panel">
        <img src="/logo.png" alt="GastroFlow" className="guest-qr-logo" />

        {pageState === "loading" && (
          <div className="guest-qr-message">
            <span className="eyebrow">GastroFlow</span>
            <h1>Otwieranie stolika...</h1>
          </div>
        )}

        {pageState === "error" && (
          <div className="guest-qr-message">
            <span className="eyebrow">Kod QR</span>
            <h1>Nie można otworzyć stolika</h1>
            <p className="muted">{error}</p>
          </div>
        )}

        {pageState === "ready" && table && (
          <div className="guest-qr-message">
            <span className="eyebrow">Witamy w GastroFlow</span>
            <h1>Stolik {table.table_number}</h1>
            <p className="muted">
              Kod QR działa poprawnie. Menu i składanie zamówienia będą dostępne
              na tym ekranie.
            </p>
            <div className="guest-qr-status">
              <span>Status stolika</span>
              <strong>{table.status}</strong>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
