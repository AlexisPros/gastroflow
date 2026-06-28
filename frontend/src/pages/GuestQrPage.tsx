import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ChevronRight,
  Minus,
  Pencil,
  Plus,
  ShoppingBag,
  Trash2,
  Users,
  UtensilsCrossed,
  Wine,
  X,
} from "lucide-react";
import { useParams } from "react-router-dom";

import { ApiError } from "../api/apiClient";
import {
  createPublicQrOrder,
  getPublicQrMenu,
  getPublicQrOrderStatus,
  getPublicQrTable,
  unlockPublicQrOrder,
  type PublicQrCategory,
  type PublicQrOrderStatus,
  type PublicQrProduct,
  type PublicQrTable,
} from "../api/qrApi";
import { WS_BASE_URL } from "../shared/config";
import { createClientId } from "../shared/id";

type Screen = "GUESTS" | "MENU" | "SUMMARY" | "SENT" | "LOCKED";
type MenuDepartment = "KITCHEN" | "BAR";
type GuestCartItem = {
  id: string;
  product: PublicQrProduct;
  quantity: number;
  modifierIds: number[];
  notes: string;
};
type GuestQrStorage = {
  screen?: Screen;
  guestCount?: number;
  sentOrderId?: number | null;
  orderStatus?: PublicQrOrderStatus | null;
  cart?: GuestCartItem[];
};

const QR_STORAGE_PREFIX = "gastroflow:qr:";

const money = new Intl.NumberFormat("pl-PL", {
  style: "currency",
  currency: "PLN",
});

function getGuestQrStorageKey(qrToken: string) {
  return `${QR_STORAGE_PREFIX}${qrToken}`;
}

function readGuestQrState(qrToken: string): GuestQrStorage | null {
  try {
    const raw = window.localStorage.getItem(getGuestQrStorageKey(qrToken));
    return raw ? (JSON.parse(raw) as GuestQrStorage) : null;
  } catch {
    return null;
  }
}

function writeGuestQrState(qrToken: string, state: GuestQrStorage) {
  try {
    window.localStorage.setItem(getGuestQrStorageKey(qrToken), JSON.stringify(state));
  } catch {
    // Browsers can block storage in private mode; QR flow still works for the active tab.
  }
}

function getActivePublicOrderId(
  status: PublicQrOrderStatus | null,
  sentOrderId: number | null,
) {
  return status?.target_order_id ?? status?.order_id ?? sentOrderId;
}

function getGuestCartItemTotal(item: GuestCartItem) {
  const modifierTotal = item.modifierIds.reduce((sum, modifierId) => {
    const modifier = item.product.modifiers.find(
      (candidate) => candidate.product_modifier_id === modifierId,
    );
    return sum + Number(modifier?.price ?? 0);
  }, 0);
  return (Number(item.product.price) + modifierTotal) * item.quantity;
}

export function GuestQrPage() {
  const { qrToken = "" } = useParams();
  const [table, setTable] = useState<PublicQrTable | null>(null);
  const [categories, setCategories] = useState<PublicQrCategory[]>([]);
  const [screen, setScreen] = useState<Screen>("GUESTS");
  const [guestCount, setGuestCount] = useState(2);
  const [department, setDepartment] = useState<MenuDepartment>("KITCHEN");
  const [activeCategoryId, setActiveCategoryId] = useState<number | "ALL">("ALL");
  const [activeSubcategoryId, setActiveSubcategoryId] = useState<number | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<PublicQrProduct | null>(null);
  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [cart, setCart] = useState<GuestCartItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [sentOrderId, setSentOrderId] = useState<number | null>(null);
  const [orderStatus, setOrderStatus] = useState<PublicQrOrderStatus | null>(null);
  const [orderCodeInput, setOrderCodeInput] = useState("");
  const [unlocking, setUnlocking] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    let active = true;
    const savedState = readGuestQrState(qrToken);
    Promise.all([getPublicQrTable(qrToken), getPublicQrMenu(qrToken)])
      .then(([nextTable, nextCategories]) => {
        if (!active) return;
        setTable(nextTable);
        setCategories(nextCategories);
        if (savedState) {
          setGuestCount(savedState.guestCount ?? 2);
          setCart(savedState.cart ?? []);
          setSentOrderId(savedState.sentOrderId ?? null);
          setOrderStatus(savedState.orderStatus ?? null);
        }

        if (savedState?.sentOrderId) {
          setScreen(savedState.screen === "SUMMARY" ? "SUMMARY" : "SENT");
        } else if (nextTable.status !== "FREE") {
          setScreen("LOCKED");
        } else if (savedState?.screen && savedState.screen !== "LOCKED" && savedState.screen !== "SENT") {
          setScreen(savedState.screen);
        }
      })
      .catch((exc) => {
        if (!active) return;
        setError(exc instanceof ApiError ? exc.message : "Nie udało się otworzyć menu.");
      })
      .finally(() => {
        if (active) {
          setHydrated(true);
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [qrToken]);

  useEffect(() => {
    if (!hydrated || !qrToken) {
      return;
    }

    writeGuestQrState(qrToken, {
      screen,
      guestCount,
      sentOrderId,
      orderStatus,
      cart,
    });
  }, [cart, guestCount, hydrated, orderStatus, qrToken, screen, sentOrderId]);

  useEffect(() => {
    if (screen !== "SENT" || sentOrderId === null) {
      return;
    }

    let active = true;
    let refreshTimer: number | undefined;

    const refreshStatus = async () => {
      try {
        const nextStatus = await getPublicQrOrderStatus(qrToken, sentOrderId);
        if (active) {
          setOrderStatus(nextStatus);
        }
      } catch {
        if (active) {
          refreshTimer = window.setTimeout(refreshStatus, 2500);
        }
      }
    };

    void refreshStatus();

    const socket = new WebSocket(`${WS_BASE_URL}/ws/public_qr`);
    socket.onmessage = () => {
      void refreshStatus();
    };
    socket.onclose = () => {
      if (active) {
        refreshTimer = window.setTimeout(refreshStatus, 2500);
      }
    };

    return () => {
      active = false;
      if (refreshTimer !== undefined) {
        window.clearTimeout(refreshTimer);
      }
      socket.close();
    };
  }, [qrToken, screen, sentOrderId]);

  const childCategoriesByParent = useMemo(() => {
    const map = new Map<number, PublicQrCategory[]>();
    for (const category of categories) {
      if (category.parent_category_id === null) continue;
      map.set(category.parent_category_id, [
        ...(map.get(category.parent_category_id) ?? []),
        category,
      ]);
    }
    return map;
  }, [categories]);
  const rootCategories = useMemo(
    () =>
      categories.filter(
        (category) =>
          category.parent_category_id === null && category.department === department,
      ),
    [categories, department],
  );
  const departmentCategories = useMemo(
    () => categories.filter((category) => category.department === department),
    [categories, department],
  );
  const activeSubcategories = useMemo(
    () =>
      activeCategoryId === "ALL"
        ? []
        : childCategoriesByParent.get(activeCategoryId) ?? [],
    [activeCategoryId, childCategoriesByParent],
  );
  const visibleProducts = useMemo(() => {
    if (activeCategoryId === "ALL") {
      return departmentCategories.flatMap((category) => category.products);
    }
    if (activeSubcategoryId !== null) {
      return categories.find((category) => category.id === activeSubcategoryId)?.products ?? [];
    }
    const parent = categories.find((category) => category.id === activeCategoryId);
    const children = childCategoriesByParent.get(activeCategoryId) ?? [];
    return [
      ...(parent?.products ?? []),
      ...children.flatMap((category) => category.products),
    ];
  }, [
    activeCategoryId,
    activeSubcategoryId,
    categories,
    childCategoriesByParent,
    departmentCategories,
  ]);
  const cartCount = cart.reduce((total, item) => total + item.quantity, 0);
  const cartTotal = cart.reduce((total, item) => total + getGuestCartItemTotal(item), 0);

  function openProduct(product: PublicQrProduct, itemId?: string) {
    setSelectedProduct(product);
    setEditingItemId(itemId ?? null);
  }

  function switchDepartment(nextDepartment: MenuDepartment) {
    setDepartment(nextDepartment);
    setActiveCategoryId("ALL");
    setActiveSubcategoryId(null);
  }

  function saveProduct(options: { modifierIds: number[]; notes: string }) {
    if (!selectedProduct) return;
    if (editingItemId) {
      setCart((items) =>
        items.map((item) =>
          item.id === editingItemId
            ? { ...item, modifierIds: options.modifierIds, notes: options.notes }
            : item,
        ),
      );
    } else {
      setCart((items) => [
        ...items,
        {
          id: createClientId(),
          product: selectedProduct,
          quantity: 1,
          modifierIds: options.modifierIds,
          notes: options.notes,
        },
      ]);
    }
    setSelectedProduct(null);
    setEditingItemId(null);
  }

  async function submitOrder() {
    if (!cart.length) return;
    setSubmitting(true);
    setError("");
    try {
      const activeOrderCode = getActivePublicOrderId(orderStatus, sentOrderId);
      const order = await createPublicQrOrder(qrToken, {
        guest_count: guestCount,
        order_code: activeOrderCode ? String(activeOrderCode) : null,
        items: cart.map((item) => ({
          product_id: item.product.id,
          quantity: item.quantity,
          notes: item.notes || null,
          product_modifier_ids: item.modifierIds,
        })),
      });
      setSentOrderId(order.id);
      setOrderStatus({
        order_id: order.id,
        target_order_id: null,
        status: order.status,
        public_status: "PENDING_CONFIRMATION",
        progress_percent: 0,
        can_order_more: false,
        items: [],
      });
      setCart([]);
      setScreen("SENT");
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Nie udało się wysłać zamówienia.");
    } finally {
      setSubmitting(false);
    }
  }

  async function unlockOrder() {
    if (!orderCodeInput.trim()) return;
    setUnlocking(true);
    setError("");
    try {
      const nextStatus = await unlockPublicQrOrder(qrToken, {
        order_code: orderCodeInput.trim(),
      });
      setSentOrderId(nextStatus.order_id);
      setOrderStatus(nextStatus);
      setCart([]);
      setScreen("SENT");
    } catch (exc) {
      setError(
        exc instanceof ApiError
          ? exc.message
          : "Nie znaleziono zamówienia dla tego stolika.",
      );
    } finally {
      setUnlocking(false);
    }
  }

  if (loading) {
    return <GuestMessage title="Otwieranie menu..." />;
  }
  if (!table || (error && categories.length === 0)) {
    return <GuestMessage title="Nie można otworzyć stolika" text={error} />;
  }
  if (screen === "SENT") {
    return (
      <GuestOrderStatus
        orderId={sentOrderId}
        status={orderStatus}
        onOrderMore={() => {
          setScreen("MENU");
        }}
      />
    );
  }

  return (
    <main className="guest-order-page">
      <header className="guest-mobile-header">
        <img src="/logo.png" alt="GastroFlow" />
        <div className="guest-table-badge">
          <span>Stolik</span>
          <strong>{table.table_number}</strong>
        </div>
      </header>

      {screen === "GUESTS" && (
        <section className="guest-count-screen">
          <span className="guest-count-icon" aria-hidden="true">
            <Users />
          </span>
          <div className="guest-count-heading">
            <span className="eyebrow">Witamy</span>
            <h1>Ile osób jest przy stoliku?</h1>
          </div>
          <div className="guest-count-control">
            <button
              type="button"
              aria-label="Zmniejsz liczbę gości"
              onClick={() => setGuestCount((value) => Math.max(1, value - 1))}
            >
              <Minus aria-hidden="true" />
            </button>
            <strong>{guestCount}</strong>
            <button
              type="button"
              aria-label="Zwiększ liczbę gości"
              onClick={() => setGuestCount((value) => Math.min(30, value + 1))}
            >
              <Plus aria-hidden="true" />
            </button>
          </div>
          <button type="button" className="guest-primary-button" onClick={() => setScreen("MENU")}>
            Przejdź do menu
          </button>
        </section>
      )}

      {screen === "LOCKED" && (
        <section className="guest-count-screen guest-locked-screen">
          <span className="eyebrow">Stolik zajęty</span>
          <h1>Ten stolik ma już otwarty rachunek.</h1>
          <p className="muted">
            Wpisz numer zamówienia, aby wrócić do statusu i domówić kolejne pozycje.
          </p>
          <label className="guest-order-code-field">
            Numer zamówienia
            <input
              value={orderCodeInput}
              inputMode="numeric"
              pattern="[0-9]*"
              onChange={(event) => setOrderCodeInput(event.target.value.replace(/\D/g, ""))}
              placeholder="np. 12"
            />
          </label>
          {error && <div className="error-box">{error}</div>}
          <button
            type="button"
            className="guest-primary-button"
            disabled={unlocking || !orderCodeInput.trim()}
            onClick={() => void unlockOrder()}
          >
            {unlocking ? "Sprawdzanie..." : "Otwórz status zamówienia"}
          </button>
        </section>
      )}

      {screen === "MENU" && (
        <>
          <div className="guest-menu-navigation">
            {sentOrderId !== null && (
              <button
                type="button"
                className="guest-status-return"
                onClick={() => setScreen("SENT")}
              >
                <span>Status zamówienia #{sentOrderId}</span>
                <ChevronRight aria-hidden="true" />
              </button>
            )}
            <nav className="guest-department-tabs" aria-label="Rodzaj menu">
              <button
                type="button"
                className={department === "KITCHEN" ? "active" : ""}
                onClick={() => switchDepartment("KITCHEN")}
              >
                <UtensilsCrossed aria-hidden="true" />
                Dania
              </button>
              <button
                type="button"
                className={department === "BAR" ? "active" : ""}
                onClick={() => switchDepartment("BAR")}
              >
                <Wine aria-hidden="true" />
                Napoje
              </button>
            </nav>
            <nav className="guest-category-tabs" aria-label="Kategorie">
              <button
                type="button"
                className={activeCategoryId === "ALL" ? "active" : ""}
                onClick={() => {
                  setActiveCategoryId("ALL");
                  setActiveSubcategoryId(null);
                }}
              >
                Wszystko
              </button>
              {rootCategories.map((category) => (
                <button
                  key={category.id}
                  type="button"
                  className={activeCategoryId === category.id ? "active" : ""}
                  onClick={() => {
                    setActiveCategoryId(category.id);
                    setActiveSubcategoryId(null);
                  }}
                >
                  {category.name}
                </button>
              ))}
            </nav>
            {activeSubcategories.length > 0 && (
              <nav className="guest-subcategory-tabs" aria-label="Podkategorie">
                <button
                  type="button"
                  className={activeSubcategoryId === null ? "active" : ""}
                  onClick={() => setActiveSubcategoryId(null)}
                >
                  Wszystkie
                </button>
                {activeSubcategories.map((subcategory) => (
                  <button
                    key={subcategory.id}
                    type="button"
                    className={activeSubcategoryId === subcategory.id ? "active" : ""}
                    onClick={() => setActiveSubcategoryId(subcategory.id)}
                  >
                    {subcategory.name}
                  </button>
                ))}
              </nav>
            )}
          </div>
          <header className="guest-menu-heading">
            <div>
              <span className="eyebrow">
                {department === "KITCHEN" ? "Karta dań" : "Karta napojów"}
              </span>
              <h1>Menu</h1>
            </div>
            <span>{visibleProducts.length} pozycji</span>
          </header>
          <section className="guest-menu-list">
            {visibleProducts.map((product) => (
              <article key={product.id} className="guest-product-row">
                <button type="button" className="guest-product-main" onClick={() => openProduct(product)}>
                  <div className="guest-product-copy">
                    <h2>{product.name}</h2>
                    {product.description && <p>{product.description}</p>}
                    <strong>{money.format(Number(product.price))}</strong>
                  </div>
                  <ProductImage product={product} />
                </button>
                <button
                  type="button"
                  className="guest-add-button"
                  aria-label={`Dodaj do zamówienia: ${product.name}`}
                  onClick={() => openProduct(product)}
                >
                  <Plus aria-hidden="true" />
                </button>
              </article>
            ))}
            {visibleProducts.length === 0 && (
              <p className="guest-menu-empty">Brak dostępnych pozycji w tej kategorii.</p>
            )}
          </section>
          {cartCount > 0 && (
            <button type="button" className="guest-cart-dock" onClick={() => setScreen("SUMMARY")}>
              <span className="guest-cart-dock-copy">
                <ShoppingBag aria-hidden="true" />
                <span>
                  <small>Twoje zamówienie</small>
                  <b>{cartCount} {cartCount === 1 ? "pozycja" : "pozycji"}</b>
                </span>
              </span>
              <strong>{money.format(cartTotal)}</strong>
              <ChevronRight aria-hidden="true" />
            </button>
          )}
        </>
      )}

      {screen === "SUMMARY" && (
        <section className="guest-summary">
          <header className="guest-summary-header">
            <button
              type="button"
              className="guest-summary-icon-button"
              aria-label="Wróć do menu"
              onClick={() => setScreen("MENU")}
            >
              <ArrowLeft aria-hidden="true" />
            </button>
            <div>
              <span className="eyebrow">Twoje zamówienie</span>
              <h1>Podsumowanie</h1>
            </div>
            <span className="guest-summary-bag" aria-hidden="true">
              <ShoppingBag />
              <b>{cartCount}</b>
            </span>
          </header>
          <div className="guest-summary-list">
            {cart.map((item) => (
              <article key={item.id} className="guest-summary-item">
                <div className="guest-summary-image">
                  <ProductImage product={item.product} />
                </div>
                <div className="guest-summary-item-copy">
                  <strong>{item.product.name}</strong>
                  {item.modifierIds.map((modifierId) => (
                    <small key={modifierId}>
                      {formatGuestModifier(
                        item.product.modifiers.find(
                          (modifier) => modifier.product_modifier_id === modifierId,
                        ),
                      )}
                    </small>
                  ))}
                  {item.notes && <small>{item.notes}</small>}
                  <button
                    type="button"
                    className="guest-summary-edit"
                    onClick={() => openProduct(item.product, item.id)}
                  >
                    <Pencil size={15} aria-hidden="true" />
                    Edytuj
                  </button>
                </div>
                <div className="guest-item-actions">
                  <strong className="guest-summary-line-total">
                    {money.format(getGuestCartItemTotal(item))}
                  </strong>
                  <div className="guest-quantity-stepper">
                  <button
                    type="button"
                    aria-label={`Zmniejsz liczbę: ${item.product.name}`}
                    onClick={() =>
                      setCart((items) =>
                        items
                          .map((candidate) =>
                            candidate.id === item.id
                              ? { ...candidate, quantity: candidate.quantity - 1 }
                              : candidate,
                          )
                          .filter((candidate) => candidate.quantity > 0),
                      )
                    }
                  >
                    <Minus aria-hidden="true" />
                  </button>
                  <strong>{item.quantity}</strong>
                  <button
                    type="button"
                    aria-label={`Zwiększ liczbę: ${item.product.name}`}
                    onClick={() =>
                      setCart((items) =>
                        items.map((candidate) =>
                          candidate.id === item.id
                            ? { ...candidate, quantity: candidate.quantity + 1 }
                            : candidate,
                        ),
                      )
                    }
                  >
                    <Plus aria-hidden="true" />
                  </button>
                  </div>
                  <button
                    type="button"
                    className="remove"
                    aria-label={`Usuń z zamówienia: ${item.product.name}`}
                    onClick={() => setCart((items) => items.filter((candidate) => candidate.id !== item.id))}
                  >
                    <Trash2 aria-hidden="true" />
                  </button>
                </div>
              </article>
            ))}
          </div>
          <div className="guest-summary-total">
            <span>Razem</span>
            <strong>{money.format(cartTotal)}</strong>
          </div>
          {error && <div className="error-box">{error}</div>}
          <button
            type="button"
            className="guest-primary-button"
            disabled={submitting || cart.length === 0}
            onClick={() => void submitOrder()}
          >
            {submitting ? "Wysyłanie..." : "Wyślij zamówienie"}
          </button>
        </section>
      )}

      {selectedProduct && (
        <GuestProductModal
          product={selectedProduct}
          existing={cart.find((item) => item.id === editingItemId)}
          onClose={() => {
            setSelectedProduct(null);
            setEditingItemId(null);
          }}
          onSave={saveProduct}
        />
      )}
    </main>
  );
}

function ProductImage({ product }: { product: PublicQrProduct }) {
  return product.image_url ? (
    <img src={product.image_url} alt={product.name} />
  ) : (
    <span className="guest-product-placeholder">
      <img src="/logo.png" alt="" />
    </span>
  );
}

function formatGuestModifier(
  modifier: PublicQrProduct["modifiers"][number] | undefined,
): string {
  if (!modifier) return "";
  return Number(modifier.price) > 0
    ? `${modifier.name} + ${money.format(Number(modifier.price))}`
    : modifier.name;
}

function GuestProductModal({
  product,
  existing,
  onClose,
  onSave,
}: {
  product: PublicQrProduct;
  existing?: GuestCartItem;
  onClose: () => void;
  onSave: (options: { modifierIds: number[]; notes: string }) => void;
}) {
  const [modifierIds, setModifierIds] = useState<number[]>(existing?.modifierIds ?? []);
  const [notes, setNotes] = useState(existing?.notes ?? "");
  return (
    <div className="guest-modal-backdrop">
      <section className="guest-product-modal" role="dialog" aria-modal="true" aria-label={product.name}>
        <div className="guest-product-modal-media">
          <ProductImage product={product} />
          <button
            type="button"
            className="guest-product-close"
            aria-label="Zamknij"
            onClick={onClose}
          >
            <X aria-hidden="true" />
          </button>
        </div>
        <div className="guest-product-modal-body">
          <header className="guest-product-modal-heading">
            <div>
              <span className="eyebrow">Szczegóły pozycji</span>
              <h1>{product.name}</h1>
            </div>
            <strong>{money.format(Number(product.price))}</strong>
          </header>
          {product.description && <p>{product.description}</p>}
          {product.modifiers.length > 0 && (
            <div className="guest-modifier-list">
              <div className="guest-option-heading">
                <h2>Dodatki</h2>
                <span>Opcjonalnie</span>
              </div>
              {product.modifiers.map((modifier) => (
                <label
                  key={modifier.product_modifier_id}
                  className={modifierIds.includes(modifier.product_modifier_id) ? "selected" : ""}
                >
                  <input
                    type="checkbox"
                    checked={modifierIds.includes(modifier.product_modifier_id)}
                    onChange={() =>
                      setModifierIds((items) =>
                        items.includes(modifier.product_modifier_id)
                          ? items.filter((id) => id !== modifier.product_modifier_id)
                          : [...items, modifier.product_modifier_id],
                      )
                    }
                  />
                  <span>{modifier.name}</span>
                  <strong>
                    {Number(modifier.price) === 0 ? "bezpłatnie" : `+ ${money.format(Number(modifier.price))}`}
                  </strong>
                </label>
              ))}
            </div>
          )}
          <label className="guest-notes-field">
            <span>Uwagi do pozycji</span>
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              maxLength={500}
              placeholder="Np. bez cebuli"
            />
          </label>
          <div className="guest-modal-actions">
            <button type="button" onClick={onClose}>Anuluj</button>
            <button type="button" className="confirm" onClick={() => onSave({ modifierIds, notes })}>
              <Plus aria-hidden="true" />
              {existing ? "Zapisz zmiany" : "Dodaj do zamówienia"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

function GuestMessage({ title, text }: { title: string; text?: string }) {
  return (
    <main className="guest-qr-page">
      <section className="guest-qr-panel">
        <img src="/logo.png" alt="GastroFlow" className="guest-qr-logo" />
        <div className="guest-qr-message">
          <h1>{title}</h1>
          {text && <p className="muted">{text}</p>}
        </div>
      </section>
    </main>
  );
}

function GuestOrderStatus({
  orderId,
  status,
  onOrderMore,
}: {
  orderId: number | null;
  status: PublicQrOrderStatus | null;
  onOrderMore: () => void;
}) {
  const publicStatus = status?.public_status ?? "PENDING_CONFIRMATION";
  const progress = Math.max(0, Math.min(100, status?.progress_percent ?? 0));
  const copy = getGuestStatusCopy(publicStatus);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const detailsTotal = (status?.items ?? []).reduce(
    (sum, item) => sum + Number(item.total_price),
    0,
  );

  return (
    <main className="guest-qr-page">
      <section className="guest-qr-panel">
        <img src="/logo.png" alt="GastroFlow" className="guest-qr-logo" />
        <div className="guest-qr-message">
          <span className={`guest-status-pill ${copy.kind}`}>{copy.badge}</span>
          <h1>{copy.title}</h1>
          <p className="muted">
            Zamówienie #{orderId} {copy.text}
          </p>
        </div>
        <div className="guest-progress-card">
          <div>
            <span>Przygotowanie</span>
            <strong>{progress}%</strong>
          </div>
          <div className="guest-progress-track">
            <span style={{ width: `${progress}%` }} />
          </div>
        </div>
        <button
          type="button"
          className="guest-secondary-button"
          onClick={() => setIsDetailsOpen((isOpen) => !isOpen)}
        >
          {isDetailsOpen ? "Ukryj szczegóły" : "Szczegóły zamówienia"}
        </button>
        {isDetailsOpen && (
          <section className="guest-order-details-card">
            <div>
              <span>Zamówione pozycje</span>
              <strong>{money.format(detailsTotal)}</strong>
            </div>
            {(status?.items ?? []).length > 0 ? (
              <div className="guest-order-details-list">
                {status?.items.map((item) => (
                  <article key={item.id}>
                    <div>
                      <strong>{item.product_name}</strong>
                      <small>
                        Kurs {item.course_number} · {item.quantity} x {money.format(Number(item.unit_price))}
                      </small>
                      {item.modifiers.map((modifier) => (
                        <small key={`${item.id}-${modifier.name}`}>
                          + {modifier.name}
                          {Number(modifier.price) > 0
                            ? ` (${money.format(Number(modifier.price))})`
                            : ""}
                        </small>
                      ))}
                      {item.notes && <small>{item.notes}</small>}
                    </div>
                    <b>{money.format(Number(item.total_price))}</b>
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted">Pozycje pojawią się po odświeżeniu statusu.</p>
            )}
          </section>
        )}
        {status?.can_order_more && (
          <button type="button" className="guest-primary-button" onClick={onOrderMore}>
            Domów
          </button>
        )}
      </section>
    </main>
  );
}

function getGuestStatusCopy(publicStatus: string) {
  if (publicStatus === "REJECTED") {
    return {
      kind: "danger",
      badge: "Odrzucone",
      title: "Zamówienie odrzucone",
      text: "zostało odrzucone przez obsługę.",
    };
  }
  if (publicStatus === "READY") {
    return {
      kind: "success",
      badge: "Gotowe",
      title: "Zamówienie gotowe",
      text: "jest gotowe do odbioru lub podania.",
    };
  }
  if (publicStatus === "PREPARING") {
    return {
      kind: "success",
      badge: "Przyjęte",
      title: "Zamówienie przyjęte",
      text: "zostało przyjęte i jest przygotowywane.",
    };
  }
  if (publicStatus === "CLOSED") {
    return {
      kind: "success",
      badge: "Zamknięte",
      title: "Rachunek zamknięty",
      text: "zostało już rozliczone.",
    };
  }
  return {
    kind: "pending",
    badge: "Oczekuje",
    title: "Zamówienie wysłane",
    text: "oczekuje na potwierdzenie przez obsługę.",
  };
}
