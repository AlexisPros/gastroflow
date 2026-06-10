import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../api/apiClient";
import {
  createPublicQrOrder,
  getPublicQrMenu,
  getPublicQrTable,
  type PublicQrCategory,
  type PublicQrProduct,
  type PublicQrTable,
} from "../api/qrApi";
import { createClientId } from "../shared/id";

type Screen = "GUESTS" | "MENU" | "SUMMARY" | "SENT";
type GuestCartItem = {
  id: string;
  product: PublicQrProduct;
  quantity: number;
  modifierIds: number[];
  notes: string;
};

const money = new Intl.NumberFormat("pl-PL", {
  style: "currency",
  currency: "PLN",
});

export function GuestQrPage() {
  const { qrToken = "" } = useParams();
  const [table, setTable] = useState<PublicQrTable | null>(null);
  const [categories, setCategories] = useState<PublicQrCategory[]>([]);
  const [screen, setScreen] = useState<Screen>("GUESTS");
  const [guestCount, setGuestCount] = useState(2);
  const [activeCategoryId, setActiveCategoryId] = useState<number | "ALL">("ALL");
  const [selectedProduct, setSelectedProduct] = useState<PublicQrProduct | null>(null);
  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [cart, setCart] = useState<GuestCartItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [sentOrderId, setSentOrderId] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([getPublicQrTable(qrToken), getPublicQrMenu(qrToken)])
      .then(([nextTable, nextCategories]) => {
        if (!active) return;
        setTable(nextTable);
        setCategories(nextCategories);
      })
      .catch((exc) => {
        if (!active) return;
        setError(exc instanceof ApiError ? exc.message : "Nie udało się otworzyć menu.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [qrToken]);

  const visibleProducts = useMemo(
    () =>
      activeCategoryId === "ALL"
        ? categories.flatMap((category) => category.products)
        : categories.find((category) => category.id === activeCategoryId)?.products ?? [],
    [activeCategoryId, categories],
  );
  const cartCount = cart.reduce((total, item) => total + item.quantity, 0);
  const cartTotal = cart.reduce((total, item) => {
    const modifiers = item.modifierIds.reduce((sum, modifierId) => {
      const modifier = item.product.modifiers.find(
        (candidate) => candidate.product_modifier_id === modifierId,
      );
      return sum + Number(modifier?.price ?? 0);
    }, 0);
    return total + (Number(item.product.price) + modifiers) * item.quantity;
  }, 0);

  function openProduct(product: PublicQrProduct, itemId?: string) {
    setSelectedProduct(product);
    setEditingItemId(itemId ?? null);
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
      const order = await createPublicQrOrder(qrToken, {
        guest_count: guestCount,
        items: cart.map((item) => ({
          product_id: item.product.id,
          quantity: item.quantity,
          notes: item.notes || null,
          product_modifier_ids: item.modifierIds,
        })),
      });
      setSentOrderId(order.id);
      setScreen("SENT");
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Nie udało się wysłać zamówienia.");
    } finally {
      setSubmitting(false);
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
      <GuestMessage
        title="Zamówienie wysłane"
        text={`Zamówienie #${sentOrderId} oczekuje na potwierdzenie przez obsługę.`}
      />
    );
  }

  return (
    <main className="guest-order-page">
      <header className="guest-mobile-header">
        <img src="/logo.png" alt="GastroFlow" />
        <div>
          <span>Stolik</span>
          <strong>{table.table_number}</strong>
        </div>
      </header>

      {screen === "GUESTS" && (
        <section className="guest-count-screen">
          <span className="eyebrow">Witamy</span>
          <h1>Ile osób jest przy stoliku?</h1>
          <div className="guest-count-control">
            <button type="button" onClick={() => setGuestCount((value) => Math.max(1, value - 1))}>
              −
            </button>
            <strong>{guestCount}</strong>
            <button type="button" onClick={() => setGuestCount((value) => Math.min(30, value + 1))}>
              +
            </button>
          </div>
          <button type="button" className="guest-primary-button" onClick={() => setScreen("MENU")}>
            Przejdź do menu
          </button>
        </section>
      )}

      {screen === "MENU" && (
        <>
          <nav className="guest-category-tabs">
            <button
              type="button"
              className={activeCategoryId === "ALL" ? "active" : ""}
              onClick={() => setActiveCategoryId("ALL")}
            >
              Wszystko
            </button>
            {categories.map((category) => (
              <button
                key={category.id}
                type="button"
                className={activeCategoryId === category.id ? "active" : ""}
                onClick={() => setActiveCategoryId(category.id)}
              >
                {category.name}
              </button>
            ))}
          </nav>
          <section className="guest-menu-list">
            {visibleProducts.map((product) => (
              <article key={product.id} className="guest-product-row">
                <button type="button" className="guest-product-main" onClick={() => openProduct(product)}>
                  <div>
                    <h2>{product.name}</h2>
                    <p>{product.description || product.ingredients.join(", ")}</p>
                    <strong>{money.format(Number(product.price))}</strong>
                  </div>
                  <ProductImage product={product} />
                </button>
                <button type="button" className="guest-add-button" onClick={() => openProduct(product)}>
                  +
                </button>
              </article>
            ))}
          </section>
          {cartCount > 0 && (
            <button type="button" className="guest-cart-dock" onClick={() => setScreen("SUMMARY")}>
              <span>Zobacz zamówienie · {cartCount}</span>
              <strong>{money.format(cartTotal)}</strong>
            </button>
          )}
        </>
      )}

      {screen === "SUMMARY" && (
        <section className="guest-summary">
          <button type="button" className="guest-back-button" onClick={() => setScreen("MENU")}>
            ← Wróć do menu
          </button>
          <h1>Podsumowanie</h1>
          <div className="guest-summary-list">
            {cart.map((item) => (
              <article key={item.id} className="guest-summary-item">
                <div>
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
                  <button type="button" onClick={() => openProduct(item.product, item.id)}>
                    Edytuj
                  </button>
                </div>
                <div className="guest-item-actions">
                  <button
                    type="button"
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
                    −
                  </button>
                  <strong>{item.quantity}</strong>
                  <button
                    type="button"
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
                    +
                  </button>
                  <button
                    type="button"
                    className="remove"
                    onClick={() => setCart((items) => items.filter((candidate) => candidate.id !== item.id))}
                  >
                    Usuń
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
      <section className="guest-product-modal">
        <ProductImage product={product} />
        <div className="guest-product-modal-body">
          <h1>{product.name}</h1>
          <p>{product.description}</p>
          {product.ingredients.length > 0 && <small>{product.ingredients.join(", ")}</small>}
          <strong>{money.format(Number(product.price))}</strong>
          {product.modifiers.length > 0 && (
            <div className="guest-modifier-list">
              <h2>Dodatki</h2>
              {product.modifiers.map((modifier) => (
                <label key={modifier.product_modifier_id}>
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
            Uwagi
            <textarea value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={500} />
          </label>
          <div className="guest-modal-actions">
            <button type="button" onClick={onClose}>Anuluj</button>
            <button type="button" className="confirm" onClick={() => onSave({ modifierIds, notes })}>
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
