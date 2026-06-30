import { useCallback, useEffect, useMemo, useState } from "react";
import { Banknote, CreditCard, Search } from "lucide-react";

import { ApiError } from "../api/apiClient";
import {
  getActiveFloorPlan,
  getFloorPlanDecorations,
  getFloorPlanTables,
  getRestaurantTables,
  type FloorPlan,
  type FloorPlanDecoration,
  type FloorPlanTable,
  type RestaurantTable,
} from "../api/floorPlanApi";
import {
  cancelReservation,
  completePrepaidReservation,
  createReservation,
  getReservationMenu,
  getReservations,
  startReservation,
  generateReservationReceiptPdf,
  generateReservationGuestCheckPdf,
  type Reservation,
  type ReservationMenuProduct,
  type ReservationPayload,
} from "../api/reservationApi";
import { useAuth } from "../auth/useAuth";

type FormState = {
  customerName: string;
  customerPhone: string;
  customerEmail: string;
  guestCount: number;
  reservationTime: string;
  durationMinutes: number;
  notes: string;
  paymentMethod: ReservationPayload["payment_method"];
};

const initialForm = (): FormState => {
  const date = new Date(Date.now() + 3 * 60 * 60 * 1000);
  date.setMinutes(Math.ceil(date.getMinutes() / 15) * 15, 0, 0);
  return {
    customerName: "",
    customerPhone: "",
    customerEmail: "",
    guestCount: 2,
    reservationTime: toLocalInput(date),
    durationMinutes: 120,
    notes: "",
    paymentMethod: "ON_SITE",
  };
};

export function ReservationsPage() {
  const { token, user } = useAuth();
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [menu, setMenu] = useState<ReservationMenuProduct[]>([]);
  const [floor, setFloor] = useState<FloorPlan | null>(null);
  const [positions, setPositions] = useState<FloorPlanTable[]>([]);
  const [tables, setTables] = useState<RestaurantTable[]>([]);
  const [decorations, setDecorations] = useState<FloorPlanDecoration[]>([]);
  const [selectedTables, setSelectedTables] = useState<number[]>([]);
  const [quantities, setQuantities] = useState<Record<number, number>>({});
  const [form, setForm] = useState<FormState>(initialForm);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [details, setDetails] = useState<Reservation | null>(null);
  const [filter, setFilter] = useState<"UPCOMING" | "ALL" | "CANCELLED">("UPCOMING");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [isPaymentOpen, setIsPaymentOpen] = useState(false);
  const [cashReceived, setCashReceived] = useState("");
  const [wantsNip, setWantsNip] = useState(false);
  const [invoiceNip, setInvoiceNip] = useState("");
  const canManage = user?.role === "ADMIN" || user?.role === "MANAGER" || user?.role === "WAITER";

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setError(null);
      const [reservationRows, menuRows, activeFloor, tableRows] = await Promise.all([
        getReservations(token),
        getReservationMenu(token),
        getActiveFloorPlan(token),
        getRestaurantTables(token),
      ]);
      const [positionRows, decorationRows] = await Promise.all([
        getFloorPlanTables(token, activeFloor.id),
        getFloorPlanDecorations(token, activeFloor.id),
      ]);
      setReservations(reservationRows);
      setMenu(menuRows);
      setFloor(activeFloor);
      setTables(tableRows);
      setPositions(positionRows);
      setDecorations(decorationRows);
    } catch (exc) {
      setError(messageOf(exc));
    }
  }, [token]);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(), 60_000);
    return () => window.clearInterval(interval);
  }, [load]);

  const visibleReservations = useMemo(() => {
    const normalized = search.trim().toLocaleLowerCase("pl");
    return reservations.filter((reservation) => {
      if (filter === "UPCOMING" && ["CANCELLED", "COMPLETED"].includes(reservation.status)) return false;
      if (filter === "CANCELLED" && reservation.status !== "CANCELLED") return false;
      if (!normalized) return true;
      return [reservation.customer_name, reservation.customer_phone, ...reservation.tables.map((t) => t.table_number)]
        .join(" ")
        .toLocaleLowerCase("pl")
        .includes(normalized);
    });
  }, [filter, reservations, search]);

  const openReservationReceiptPdfs = async (reservationId: number) => {
    if (!token) return;
    try {
      const [fiscalReceiptBlob, guestCheckBlob] = await Promise.all([
        generateReservationReceiptPdf(token, reservationId),
        generateReservationGuestCheckPdf(token, reservationId),
      ]);
      openPdfBlob(fiscalReceiptBlob);
      openPdfBlob(guestCheckBlob);
    } catch (e) {
      console.error("Could not print reservation receipts", e);
    }
  };

  const openPdfBlob = (blob: Blob) => {
    const receiptUrl = window.URL.createObjectURL(blob);
    window.open(receiptUrl, "_blank", "noopener,noreferrer");
    window.setTimeout(() => window.URL.revokeObjectURL(receiptUrl), 60_000);
  };

  const total = useMemo(
    () => menu.reduce((sum, product) => sum + Number(product.price) * (quantities[product.id] ?? 0), 0),
    [menu, quantities],
  );

  const submit = async (paymentConfirmed = false) => {
    if (!token) return;
    if (selectedTables.length === 0) {
      setError("Wybierz co najmniej jeden stolik.");
      return;
    }
    if (!paymentConfirmed && form.paymentMethod !== "ON_SITE" && total > 0) {
      setError(null);
      setCashReceived(form.paymentMethod === "CASH" ? total.toFixed(2) : "");
      setIsPaymentOpen(true);
      return;
    }
    if (
      form.paymentMethod === "CASH"
      && total > 0
      && (!Number.isFinite(Number(cashReceived)) || Number(cashReceived) < total)
    ) {
      setError("Otrzymana gotówka nie może być mniejsza niż kwota rezerwacji.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await createReservation(token, {
        table_ids: selectedTables,
        customer_name: form.customerName,
        customer_phone: form.customerPhone,
        customer_email: form.customerEmail.trim() || null,
        invoice_nip: wantsNip ? invoiceNip.trim() || null : null,
        guest_count: form.guestCount,
        reservation_time: new Date(form.reservationTime).toISOString(),
        duration_minutes: form.durationMinutes,
        notes: form.notes.trim() || null,
        payment_method: total > 0 ? form.paymentMethod : "ON_SITE",
        cash_received:
          form.paymentMethod === "CASH" && total > 0
            ? Number(cashReceived).toFixed(2)
            : null,
        items: Object.entries(quantities)
          .filter(([, quantity]) => quantity > 0)
          .map(([productId, quantity]) => ({ product_id: Number(productId), quantity })),
      });
      setIsCreateOpen(false);
      setIsPaymentOpen(false);
      setCashReceived("");
      setWantsNip(false);
      setInvoiceNip("");
      setSelectedTables([]);
      setQuantities({});
      setForm(initialForm());
      await load();

      if (total > 0 && (form.paymentMethod === "CARD" || form.paymentMethod === "CASH")) {
        void openReservationReceiptPdfs(res.id);
      }
    } catch (exc) {
      setError(messageOf(exc));
    } finally {
      setBusy(false);
    }
  };

  const perform = async (action: "START" | "CANCEL" | "COMPLETE", reservation: Reservation) => {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      if (action === "START") await startReservation(token, reservation.id);
      else if (action === "COMPLETE") await completePrepaidReservation(token, reservation.id);
      else await cancelReservation(token, reservation.id);
      setDetails(null);
      await load();
    } catch (exc) {
      setError(messageOf(exc));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="page-stack reservations-page">
      <div className="reservations-heading">
        <div><span className="eyebrow">Obsługa gości</span><h1>Rezerwacje</h1></div>
        <div className="reservations-heading-actions">
          <button type="button" className="ghost-button" onClick={() => void load()}>Odśwież</button>
          {canManage && <button type="button" className="primary-button" onClick={() => { setError(null); setIsCreateOpen(true); }}>Nowa rezerwacja</button>}
        </div>
      </div>

      {error && <div className="form-error">{error}</div>}
      <div className="reservation-toolbar">
        <div className="category-tabs">
          <button className={filter === "UPCOMING" ? "active" : ""} onClick={() => setFilter("UPCOMING")}>Nadchodzące</button>
          <button className={filter === "ALL" ? "active" : ""} onClick={() => setFilter("ALL")}>Wszystkie</button>
          <button className={filter === "CANCELLED" ? "active" : ""} onClick={() => setFilter("CANCELLED")}>Anulowane</button>
        </div>
        <label className="reservation-search-field">
          <Search aria-hidden="true" />
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Szukaj gościa, telefonu lub stolika" />
        </label>
      </div>

      <div className="reservation-list">
        {visibleReservations.length > 0 && (
          <div className="reservation-list-header" aria-hidden="true">
            <span>Termin</span>
            <span>Gość</span>
            <span>Stoliki</span>
            <span>Wartość</span>
            <span>Status</span>
          </div>
        )}
        {visibleReservations.map((reservation) => (
          <button key={reservation.id} type="button" className="reservation-row" onClick={() => { setError(null); setDetails(reservation); }}>
            <time>{formatDate(reservation.reservation_time)}</time>
            <span className="reservation-guest"><strong>{reservation.customer_name}</strong><small>{reservation.guest_count} os. · {reservation.customer_phone}</small></span>
            <span><strong>{reservation.tables.map((table) => `Stolik ${table.table_number}`).join(", ")}</strong><small>{reservation.duration_minutes} min</small></span>
            <span><strong>{money(reservation.total_amount)}</strong><small>{reservation.payment_status === "PREPAID" ? "Opłacona" : "Płatność na miejscu"}</small></span>
            <span className={`reservation-status status-${reservation.status.toLowerCase()}`}>{statusLabel(reservation.status)}</span>
          </button>
        ))}
        {visibleReservations.length === 0 && <div className="empty-state">Brak rezerwacji spełniających wybrane kryteria.</div>}
      </div>

      {isCreateOpen && (
        <div className="modal-backdrop reservation-modal-backdrop">
          <div className="reservation-modal">
            <header><div><span className="eyebrow">Nowa rezerwacja</span><h2>Dane gościa i stoliki</h2></div><button className="ghost-button" onClick={() => setIsCreateOpen(false)}>Zamknij</button></header>
            {error && <div className="form-error reservation-modal-error">{error}</div>}
            <div className="reservation-create-grid">
              <div className="reservation-map-column">
                <div className="reservation-section-heading">
                  <div>
                    <span className="eyebrow">Plan sali</span>
                    <h3>Wybierz stolik lub połącz kilka</h3>
                  </div>
                  <strong className="reservation-selection-count">
                    {selectedTables.length === 0
                      ? "Nie wybrano"
                      : `Wybrano: ${selectedTables.length}`}
                  </strong>
                </div>
                <ReservationMap floor={floor} positions={positions} tables={tables} decorations={decorations} selected={selectedTables} onToggle={(id) => setSelectedTables((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id])} />
              </div>
              <div className="reservation-form-column">
                <section className="reservation-form-section">
                  <div className="reservation-section-heading compact">
                    <div><span className="eyebrow">Kontakt</span><h3>Dane gościa</h3></div>
                  </div>
                  <div className="reservation-form-grid contact-grid">
                    <label><span>Imię i nazwisko</span><input required value={form.customerName} onChange={(e) => setForm({...form, customerName: e.target.value})} /></label>
                    <label><span>Telefon</span><input required value={form.customerPhone} onChange={(e) => setForm({...form, customerPhone: e.target.value})} /></label>
                    <label className="full-field"><span>E-mail <small>opcjonalnie</small></span><input type="email" value={form.customerEmail} onChange={(e) => setForm({...form, customerEmail: e.target.value})} /></label>
                  </div>
                </section>
                <section className="reservation-form-section">
                  <div className="reservation-section-heading compact">
                    <div><span className="eyebrow">Wizyta</span><h3>Termin i goście</h3></div>
                  </div>
                  <div className="reservation-form-grid visit-grid">
                    <label className="full-field"><span>Data i godzina</span><input type="datetime-local" value={form.reservationTime} onChange={(e) => setForm({...form, reservationTime: e.target.value})} /></label>
                    <label><span>Liczba gości</span><input type="number" min="1" value={form.guestCount} onChange={(e) => setForm({...form, guestCount: Number(e.target.value)})} /></label>
                    <label><span>Czas trwania <small>min</small></span><input type="number" min="30" step="30" value={form.durationMinutes} onChange={(e) => setForm({...form, durationMinutes: Number(e.target.value)})} /></label>
                  </div>
                </section>
                <section className="reservation-form-section reservation-note-section">
                  <label><span>Informacje dodatkowe <small>opcjonalnie</small></span><textarea rows={3} value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} /></label>
                </section>
              </div>
            </div>
            <div className="reservation-preorder">
              <div className="reservation-section-heading">
                <div><span className="eyebrow">Opcjonalnie</span><h3>Przedzamówienie</h3><p>Pozycje trafią na kuchnię lub bar dopiero po rozpoczęciu rezerwacji.</p></div>
                <strong>{Object.values(quantities).reduce((sum, quantity) => sum + quantity, 0)} poz.</strong>
              </div>
              <div className="reservation-products">
                {menu.map((product) => <div key={product.id} className="reservation-product"><span><strong>{product.name}</strong><small>{product.category_name} · {money(product.price)}</small></span><div className="quantity-stepper"><button onClick={() => setQuantities({...quantities, [product.id]: Math.max(0, (quantities[product.id] ?? 0) - 1)})}>−</button><b>{quantities[product.id] ?? 0}</b><button onClick={() => setQuantities({...quantities, [product.id]: (quantities[product.id] ?? 0) + 1})}>+</button></div></div>)}
              </div>
            </div>
            <footer className="reservation-create-footer">
              <div className="payment-choice"><span className="payment-choice-label">Sposób płatności<small>{total <= 0 ? "Dostępny po dodaniu pozycji" : "Za przedzamówienie"}</small></span><div>{(["ON_SITE", "CARD", "CASH"] as const).map((method) => <button key={method} disabled={method !== "ON_SITE" && total <= 0} className={form.paymentMethod === method ? "active" : ""} onClick={() => setForm({...form, paymentMethod: method})}>{method === "ON_SITE" ? "Na miejscu" : method}</button>)}</div></div>
              <div className="reservation-total"><small>Wartość przedzamówienia</small><strong>{money(total)}</strong></div>
              <button className="primary-button" disabled={busy} onClick={() => void submit()}>Zapisz rezerwację</button>
            </footer>
          </div>
        </div>
      )}

      {details && (
        <div className="modal-backdrop"><div className="reservation-details-modal">
          <header><div><span className="eyebrow">Rezerwacja #{details.id}</span><h2>{details.customer_name}</h2></div><button className="ghost-button" onClick={() => setDetails(null)}>Zamknij</button></header>
          <div className="reservation-details-body">
            {error && <div className="form-error reservation-modal-error">{error}</div>}
            <div className="reservation-detail-summary"><div><small>Termin</small><strong>{formatDate(details.reservation_time)}</strong></div><div><small>Czas trwania</small><strong>{details.duration_minutes} min</strong></div><div><small>Goście</small><strong>{details.guest_count}</strong></div><div><small>Płatność</small><strong>{details.payment_status === "PREPAID" ? `Opłacono ${money(details.prepaid_amount)}` : "Na miejscu"}</strong></div></div>
            <section className="reservation-detail-map">
              <div className="reservation-section-heading compact"><div><span className="eyebrow">Plan sali</span><h3>{details.tables.map((table) => `Stolik ${table.table_number}`).join(", ")}</h3></div></div>
              <ReservationMap floor={floor} positions={positions} tables={tables} decorations={decorations} selected={details.tables.map((table) => table.id)} onToggle={() => undefined} compact interactive={false} />
            </section>
            <div className="reservation-contact-details"><span><small>Telefon</small><strong>{details.customer_phone}</strong></span>{details.customer_email && <span><small>E-mail</small><strong>{details.customer_email}</strong></span>}{details.invoice_nip && <span><small>NIP</small><strong>{details.invoice_nip}</strong></span>}</div>
            {details.notes && (
              <div className="reservation-note-wrapper">
                <span className="reservation-note-label">Informacja</span>
                <div className="reservation-note">{details.notes}</div>
              </div>
            )}
            <h3>Przedzamówienie</h3>
            <div className="reservation-detail-items">{details.items.length ? details.items.map((item) => <div key={item.id}><span><strong>{item.product_name}</strong><small>{item.quantity} × {money(item.unit_price)}</small></span><b>{money(item.total_price)}</b></div>) : <p>Bez przedzamówienia.</p>}</div>
          </div>
          {canManage && !["CANCELLED", "COMPLETED"].includes(details.status) && <footer>{!["STARTED"].includes(details.status) && <button className="danger-outline-button" disabled={busy || Number(details.prepaid_amount) > 0} onClick={() => void perform("CANCEL", details)}>Anuluj rezerwację</button>}{details.status !== "STARTED" && <button className="primary-button" disabled={busy} onClick={() => void perform("START", details)}>Rozpocznij rezerwację</button>}{details.status === "STARTED" && details.payment_status === "PREPAID" && <button className="primary-button" disabled={busy} onClick={() => void perform("COMPLETE", details)}>Zakończ obsługę</button>}</footer>}
        </div></div>
      )}

      {isPaymentOpen && (
        <div className="modal-backdrop reservation-payment-backdrop">
          <div className="reservation-payment-modal">
            <header><div><span className="eyebrow">Płatność rezerwacji</span><h2>Potwierdź {form.paymentMethod}</h2></div><button className="ghost-button" onClick={() => setIsPaymentOpen(false)}>Wróć</button></header>
            <div className="reservation-payment-hero">{form.paymentMethod === "CARD" ? <CreditCard aria-hidden="true" /> : <Banknote aria-hidden="true" />}<span><small>Do zapłaty</small><strong>{money(total)}</strong></span></div>
            {error && <div className="form-error">{error}</div>}
            {form.paymentMethod === "CASH" && <label><span>Otrzymana gotówka</span><input inputMode="decimal" value={cashReceived} onChange={(event) => setCashReceived(event.target.value.replace(",", "."))} /><small>Reszta: {money(Math.max(Number(cashReceived || 0) - total, 0))}</small></label>}
            <div className="reservation-nip-choice"><span>Czy dodać NIP?</span><div><button className={!wantsNip ? "active" : ""} onClick={() => setWantsNip(false)}>Nie</button><button className={wantsNip ? "active" : ""} onClick={() => setWantsNip(true)}>Tak</button></div></div>
            {wantsNip && <label><span>NIP</span><input inputMode="numeric" value={invoiceNip} onChange={(event) => setInvoiceNip(event.target.value)} /></label>}
            <footer><button className="ghost-button" onClick={() => setIsPaymentOpen(false)}>Anuluj</button><button className="primary-button" disabled={busy || (wantsNip && invoiceNip.trim().length < 10)} onClick={() => void submit(true)}>Potwierdź płatność</button></footer>
          </div>
        </div>
      )}
    </section>
  );
}

function ReservationMap({floor, positions, tables, decorations, selected, onToggle, compact = false, interactive = true}: {floor: FloorPlan | null; positions: FloorPlanTable[]; tables: RestaurantTable[]; decorations: FloorPlanDecoration[]; selected: number[]; onToggle: (id: number) => void; compact?: boolean; interactive?: boolean}) {
  if (!floor) return <div className="empty-state">Brak aktywnego planu sali.</div>;
  const byId = new Map(tables.map((table) => [table.id, table]));
  const scale = compact ? Math.min(1, 680 / floor.width, 260 / floor.height) : 1;
  return <div className={`reservation-map-scroll ${compact ? "compact" : ""}`}><div className="reservation-map-stage" style={{width: floor.width * scale, height: floor.height * scale}}><div className="reservation-map-canvas" style={{width: floor.width, height: floor.height, transform: `scale(${scale})`}}>
    {decorations.map((item) => <div key={item.id} className={`reservation-decoration ${item.shape === "CIRCLE" ? "circle" : ""}`} style={{left: Number(item.x), top: Number(item.y), width: Number(item.width), height: Number(item.height), background: item.color, transform: `rotate(${Number(item.rotation)}deg)`}}>{item.label}</div>)}
    {positions.map((position) => { const table = byId.get(position.table_id); if (!table) return null; const available = table.status === "FREE" || table.status === "RESERVED"; return <button key={position.id} type="button" disabled={interactive && !available} className={`reservation-map-table status-${table.status.toLowerCase()} ${selected.includes(table.id) ? "selected" : ""} ${!interactive ? "readonly" : ""}`} style={{left: Number(position.x), top: Number(position.y), width: Number(position.width), height: Number(position.height), borderRadius: position.shape === "CIRCLE" ? 999 : 8, transform: `rotate(${Number(position.rotation)}deg)`}} onClick={() => interactive && onToggle(table.id)}><strong>{table.table_number}</strong><small>{selected.includes(table.id) && !interactive ? "Rezerwacja" : table.status === "FREE" ? "Wolny" : table.status === "RESERVED" ? "Zarezerwowany" : "Niedostępny"}</small></button>; })}
  </div></div></div>;
}

const money = (value: string | number) => `${Number(value).toFixed(2).replace(".", ",")} zł`;
const formatDate = (value: string) => new Intl.DateTimeFormat("pl-PL", {day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit"}).format(new Date(value));
const statusLabel = (status: string) => ({CONFIRMED: "Potwierdzona", PENDING: "Oczekuje", STARTED: "Rozpoczęta", COMPLETED: "Zakończona", CANCELLED: "Anulowana"}[status] ?? status);
const toLocalInput = (date: Date) => { const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000); return local.toISOString().slice(0, 16); };
const messageOf = (error: unknown) => error instanceof ApiError ? error.message : "Nie udało się wykonać operacji.";
