import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/apiClient";
import {
  getFloorPlans,
  getFloorPlanView,
  type FloorPlan,
  type FloorPlanDecoration,
  type FloorTableView,
  type RestaurantTable,
} from "../api/floorPlanApi";
import {
  addItemsToWaiterOrder,
  cancelWaiterOrder,
  createWaiterBillSegment,
  createWaiterOrder,
  deleteWaiterBillSegment,
  createInvoiceForWaiterOrder,
  applyDiscountToWaiterOrder,
  finalizeWaiterBillSplit,
  generateWaiterGuestCheckPdf,
  generateWaiterReceiptPdf,
  getWaiterBillSplit,
  getDiscounts,
  getModifiers,
  getProductCategories,
  getProductModifiers,
  getWaiterOrderItems,
  getWaiterOrders,
  getWaiterProducts,
  isOpenOrder,
  moveWaiterBillSplitItems,
  tableStatusLabel,
  splitWaiterBillSplitItem,
  type CartEntry,
  type CartItem,
  type BillSplitOriginalItem,
  type BillSplitView,
  type Discount,
  type Modifier,
  type Order,
  type OrderItem,
  type Product,
  type ProductCategory,
  type ProductModifier,
  verifyManagerPin,
  voidWaiterOrderItem,
  registerWaiterPayment,
  removeDiscountFromWaiterOrder,
  updateWaiterOrder,
  updateWaiterOrderTip,
  getWaiterMergeCandidates,
  mergeWaiterOrder,
  type OrderMergeCandidate,
} from "../api/waiterApi";
import { useAuth } from "../auth/useAuth";
import { usePrompt } from "../components/PromptProvider";
import { connectLiveUpdates } from "../ws/liveUpdates";

type LoadingState = "idle" | "loading" | "ready" | "error";
type WaiterMode = "DASHBOARD" | "TABLE_PICKER" | "ORDER_BUILDER" | "CHECKOUT" | "ORDER_DETAILS";
type MenuDepartment = "KITCHEN" | "BAR";
type TicketSelection = { type: "existing"; id: number } | { type: "cart"; id: string };

function clampScale(s: number) {
  return Math.min(Math.max(s, 0.7), 2.5);
}

const barCategoryWords = [
  "bar",
  "beer",
  "wine",
  "cocktail",
  "drink",
  "soft",
  "napoje",
  "napój",
  "wina",
  "piwo",
  "alkohol",
];

export function WaiterPage() {
  const { token, user } = useAuth();
  const { prompt, confirm } = usePrompt();
  const [floorPlan, setFloorPlan] = useState<FloorPlan | null>(null);
  const [floorPlans, setFloorPlans] = useState<FloorPlan[]>([]);
  const [selectedFloorPlanId, setSelectedFloorPlanId] = useState<number | null>(null);
  const [floorTables, setFloorTables] = useState<FloorTableView[]>([]);
  const [floorDecorations, setFloorDecorations] = useState<FloorPlanDecoration[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [orderItems, setOrderItems] = useState<OrderItem[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [modifiers, setModifiers] = useState<Modifier[]>([]);
  const [productModifiers, setProductModifiers] = useState<ProductModifier[]>([]);
  const [discounts, setDiscounts] = useState<Discount[]>([]);
  const [mode, setMode] = useState<WaiterMode>("DASHBOARD");
  const [selectedTable, setSelectedTable] = useState<RestaurantTable | null>(null);
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const [guestCount, setGuestCount] = useState(2);
  const [department, setDepartment] = useState<MenuDepartment>("KITCHEN");
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | "ALL">("ALL");
  const [cart, setCart] = useState<CartEntry[]>([]);
  const [selectedTicketLine, setSelectedTicketLine] = useState<TicketSelection | null>(null);
  const [tipInput, setTipInput] = useState("");
  const [isFunctionsMenuOpen, setIsFunctionsMenuOpen] = useState(false);
  const [isProductSearchOpen, setIsProductSearchOpen] = useState(false);
  const [isBillSplitOpen, setIsBillSplitOpen] = useState(false);
  const [isMergeModalOpen, setIsMergeModalOpen] = useState(false);
  const [mergeCandidates, setMergeCandidates] = useState<OrderMergeCandidate[]>([]);
  const [selectedMergeCandidateId, setSelectedMergeCandidateId] = useState<number | null>(null);
  const [isMerging, setIsMerging] = useState(false);
  const [billSplitView, setBillSplitView] = useState<BillSplitView | null>(null);
  const [selectedBillSplitItemIds, setSelectedBillSplitItemIds] = useState<number[]>([]);
  const [productSearchQuery, setProductSearchQuery] = useState("");
  const [pendingProduct, setPendingProduct] = useState<Product | null>(null);
  const [status, setStatus] = useState<LoadingState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [mapScale, setMapScale] = useState(0.7);
  const waiterMapRef = useRef<HTMLDivElement | null>(null);
  const floorContentSize = useMemo(() => {
    if (!floorPlan) {
      return { width: 0, height: 0 };
    }

    const hasMapObjects = floorTables.length > 0 || floorDecorations.length > 0;
    const tableWidth = floorTables.reduce(
      (width, item) => Math.max(width, Number(item.x) + Number(item.width)),
      0,
    );
    const tableHeight = floorTables.reduce(
      (height, item) => Math.max(height, Number(item.y) + Number(item.height)),
      0,
    );
    const decorationWidth = floorDecorations.reduce(
      (width, item) => Math.max(width, Number(item.x) + Number(item.width)),
      0,
    );
    const decorationHeight = floorDecorations.reduce(
      (height, item) => Math.max(height, Number(item.y) + Number(item.height)),
      0,
    );

    return {
      width: (hasMapObjects ? Math.max(tableWidth, decorationWidth) : floorPlan.width) + 40,
      height: (hasMapObjects ? Math.max(tableHeight, decorationHeight) : floorPlan.height) + 40,
    };
  }, [floorDecorations, floorPlan, floorTables]);

  const loadWaiterData = useCallback(async () => {
    if (!token) {
      return;
    }

    setStatus((current) => (current === "ready" ? current : "loading"));
    setError(null);

    try {
      const [
        floorView,
        nextOrders,
        nextOrderItems,
        nextProducts,
        nextCategories,
        nextModifiers,
        nextProductModifiers,
        nextDiscounts,
      ] =
        await Promise.all([
          getFloorPlanView(token, selectedFloorPlanId ?? undefined),
          getWaiterOrders(token),
          getWaiterOrderItems(token),
          getWaiterProducts(token),
          getProductCategories(token),
          getModifiers(token),
          getProductModifiers(token),
          getDiscounts(token),
        ]);

      setFloorPlan(floorView.floorPlan);
      setFloorTables(floorView.tables);
      setFloorDecorations(floorView.decorations);
      setOrders(nextOrders);
      setOrderItems(nextOrderItems);
      setProducts(nextProducts.filter((product) => product.is_active));
      setCategories(nextCategories.filter((category) => category.is_active));
      setModifiers(nextModifiers.filter((modifier) => modifier.is_active));
      setProductModifiers(nextProductModifiers.filter((item) => item.is_active));
      setDiscounts(nextDiscounts.filter((discount) => discount.is_active));
      
      if (selectedFloorPlanId === null && floorView.floorPlan) {
        setSelectedFloorPlanId(floorView.floorPlan.id);
      }
      
      setStatus("ready");
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not load waiter workspace.");
      setStatus("error");
    }
  }, [token, selectedFloorPlanId]);

  const loadFloorPlansList = useCallback(async () => {
    if (!token) return;
    try {
      const plans = await getFloorPlans(token);
      setFloorPlans(plans);
      if (plans.length > 0 && selectedFloorPlanId === null) {
        setSelectedFloorPlanId(plans[0].id);
      }
    } catch (e) {
      console.error("Could not load floor plans", e);
    }
  }, [token, selectedFloorPlanId]);

  useEffect(() => {
    void loadFloorPlansList();
  }, [loadFloorPlansList]);

  useEffect(() => {
    if (selectedFloorPlanId !== null) {
      void loadWaiterData();
    } else if (floorPlans.length === 0) {
      void loadWaiterData();
    }
  }, [loadWaiterData, selectedFloorPlanId, floorPlans.length]);

  useEffect(() => {
    document.body.classList.toggle("pos-fullscreen", isFullscreenMode(mode));
    return () => document.body.classList.remove("pos-fullscreen");
  }, [mode]);

  useEffect(() => {
    if (!token) {
      return;
    }

    return connectLiveUpdates({
      channel: "waiters",
      token,
      onMessage: (message) => {
        if (message.event !== "connected") {
          void loadWaiterData();
        }
      },
    });
  }, [loadWaiterData, token]);

  const openOrders = useMemo(() => {
    const activeOrders = orders.filter(isOpenOrder);
    if (!user || user.role === "ADMIN" || user.role === "MANAGER") {
      return activeOrders;
    }
    return activeOrders.filter((order) => order.waiter_id === user.id);
  }, [orders, user]);

  const selectedOrder = useMemo(
    () => openOrders.find((order) => order.id === selectedOrderId) ?? null,
    [openOrders, selectedOrderId],
  );

  const selectedOrderItems = useMemo(
    () =>
      [...orderItems]
        .filter((item) => item.order_id === selectedOrderId)
        .sort((a, b) => a.position - b.position),
    [orderItems, selectedOrderId],
  );

  const productsById = useMemo(
    () => new Map(products.map((product) => [product.id, product])),
    [products],
  );
  const categoriesById = useMemo(
    () => new Map(categories.map((category) => [category.id, category])),
    [categories],
  );
  const modifiersById = useMemo(
    () => new Map(modifiers.map((modifier) => [modifier.id, modifier])),
    [modifiers],
  );
  const hasRepeatableDrink = useMemo(
    () =>
      [...cart]
        .reverse()
        .some((entry) => isCartItem(entry) && isBarProduct(entry.product, categoriesById)) ||
      [...selectedOrderItems]
        .reverse()
        .some((item) => {
          const product = productsById.get(item.product_id);
          return product ? isBarProduct(product, categoriesById) : false;
        }),
    [cart, categoriesById, productsById, selectedOrderItems],
  );

  const departmentCategories = useMemo(
    () =>
      categories.filter((category) =>
        department === "BAR"
          ? isBarCategory(category.name)
          : !isBarCategory(category.name),
      ),
    [categories, department],
  );

  const visibleProducts = useMemo(() => {
    const departmentCategoryIds = new Set(departmentCategories.map((category) => category.id));
    return products.filter((product) => {
      if (!departmentCategoryIds.has(product.category_id)) {
        return false;
      }
      return selectedCategoryId === "ALL" || product.category_id === selectedCategoryId;
    });
  }, [departmentCategories, products, selectedCategoryId]);

  const productSearchResults = useMemo(() => {
    const query = productSearchQuery.trim().toLowerCase();
    if (!query) {
      return [];
    }

    return products
      .filter((product) => {
        const name = product.name.toLowerCase();
        const description = product.description?.toLowerCase() ?? "";
        return name.includes(query) || description.includes(query);
      })
      .slice(0, 12);
  }, [productSearchQuery, products]);

  const cartTotal = useMemo(
    () =>
      cart.reduce((total, entry) => {
        if (!isCartItem(entry)) {
          return total;
        }

        const modifierTotal = entry.productModifierIds.reduce(
          (modifierSum, productModifierId) => {
            const productModifier = productModifiers.find(
              (modifier) => modifier.id === productModifierId,
            );
            return productModifier
              ? modifierSum + getProductModifierPrice(productModifier, modifiersById)
              : modifierSum;
          },
          0,
        );
        return total + (Number(entry.product.price) + modifierTotal) * entry.quantity;
      }, 0),
    [cart, modifiersById, productModifiers],
  );

  if (status === "idle" || status === "loading") {
    return (
      <section className="page-stack">
        <div className="module-placeholder">Loading waiter workspace...</div>
      </section>
    );
  }

  if (status === "error") {
    return (
      <section className="page-stack">
        <div className="error-box">{error}</div>
        <button type="button" className="primary-button" onClick={loadWaiterData}>
          Reload
        </button>
      </section>
    );
  }

  return (
    <section className={`waiter-workspace ${isFullscreenMode(mode) ? "pos-builder-mode" : ""}`}>
      {!isFullscreenMode(mode) && notice && <div className="success-box">{notice}</div>}
      {!isFullscreenMode(mode) && error && <div className="error-box">{error}</div>}

      {mode === "DASHBOARD" && (
        <div className="waiter-dashboard-grid">
          <main className="waiter-panel waiter-orders-board">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Otwarte rachunki</span>
                <h1>Aktywne stoliki</h1>
              </div>
              <strong>{openOrders.length}</strong>
            </div>

            <div className="order-card-grid">
              {openOrders.map((order) => (
                <button
                  key={order.id}
                  type="button"
                  className="order-overview-card"
                  onClick={() => {
                    openExistingOrder(order);
                  }}
                >
                  <span>Rachunek #{formatOrderNumber(order)}</span>
                  <strong>{getOrderTableLabel(order)}</strong>
                  <small>
                    {order.guest_count ?? 0} os. · {order.status === 'OPEN' ? 'OTWARTY' : (order.status === 'IN_PROGRESS' ? 'W TRAKCIE' : order.status)}
                  </small>
                  <b>{formatMoney(Number(order.total_amount))}</b>
                </button>
              ))}
              {openOrders.length === 0 && (
                <div className="empty-orders-state">
                  <strong>Brak otwartych rachunków</strong>
                  <p>Nowe rachunki pojawią się tutaj po wybraniu stolika.</p>
                </div>
              )}
            </div>
          </main>

          <aside className="waiter-panel waiter-action-panel">
            <span className="eyebrow">Akcje</span>
            <button
              type="button"
              className="pos-action-button primary"
              onClick={() => {
                setMode("TABLE_PICKER");
                setSelectedTable(null);
                setNotice(null);
                setError(null);
              }}
            >
              Utwórz rachunek
            </button>
            <button type="button" className="pos-action-button" onClick={loadWaiterData}>
              Odśwież
            </button>
          </aside>
        </div>
      )}

      {mode === "TABLE_PICKER" && (
        <div className="waiter-flow-grid table-picker-flow">
          <main className="waiter-panel waiter-map-panel">
            <div className="panel-heading" style={{ alignItems: "center" }}>
              <div>
                <span className="eyebrow">Krok 1</span>
                <h1>Wybierz wolny stolik</h1>
              </div>
              <button type="button" className="ghost-button" onClick={resetToDashboard}>
                Wstecz
              </button>
            </div>

            {floorPlans.length > 1 && (
              <div className="category-tabs" style={{ marginBottom: "1rem" }}>
                {floorPlans.map((plan) => (
                  <button
                    key={plan.id}
                    type="button"
                    className={selectedFloorPlanId === plan.id ? "active" : ""}
                    onClick={() => setSelectedFloorPlanId(plan.id)}
                  >
                    {plan.name}
                  </button>
                ))}
              </div>
            )}

            <div
              ref={waiterMapRef}
              className="waiter-floor-map"
              onWheel={(event) => {
                if (!event.ctrlKey && !event.metaKey) {
                  return;
                }
                event.preventDefault();
                setMapScale((value) =>
                  clampScale(value + (event.deltaY > 0 ? -0.1 : 0.1)),
                );
              }}
            >
              {floorPlan ? (
                <div
                  className="waiter-floor-stage"
                  style={{
                    width: floorContentSize.width * mapScale,
                    height: floorContentSize.height * mapScale,
                  }}
                >
                  <div
                    className="waiter-floor-canvas"
                    style={{
                      width: floorContentSize.width,
                      height: floorContentSize.height,
                      transform: `scale(${mapScale})`,
                      transformOrigin: "top left",
                      backgroundImage: floorPlan.background_image_url
                        ? `url(${floorPlan.background_image_url})`
                        : undefined,
                    }}
                  >
                  {floorDecorations.map((item) => (
                    <div
                      key={item.id}
                      className={`waiter-map-decoration ${
                        item.shape === "CIRCLE" ? "circle" : ""
                      }`}
                      style={{
                        left: Number(item.x),
                        top: Number(item.y),
                        width: Number(item.width),
                        height: Number(item.height),
                        background: item.color,
                        transform: `rotate(${Number(item.rotation)}deg)`,
                      }}
                    >
                      {item.label && <span>{item.label}</span>}
                    </div>
                  ))}
                  {floorTables.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={`waiter-map-table status-${(item.table?.status ?? "UNKNOWN")
                        .toLowerCase()
                        .replaceAll("_", "-")} ${
                        selectedTable?.id === item.table_id ? "selected" : ""
                      }`}
                      style={{
                        left: Number(item.x),
                        top: Number(item.y),
                        width: Number(item.width),
                        height: Number(item.height),
                        borderRadius: item.shape === "CIRCLE" ? 999 : 8,
                        transform: `rotate(${Number(item.rotation)}deg)`,
                      }}
                      disabled={item.table?.status !== "FREE"}
                      onClick={() => {
                        if (item.table?.status === "FREE") {
                          void selectTableForNewOrder(item.table);
                        }
                      }}
                    >
                      <strong>{item.table?.table_number ?? item.table_id}</strong>
                      <span className="table-status-label">
                        {tableStatusLabel(item.table?.status ?? "UNKNOWN")}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
              ) : (
                <div className="empty-ticket">Brak aktywnego planu sali.</div>
              )}
            </div>
          </main>
        </div>
      )}

      {mode === "ORDER_BUILDER" && selectedTable && (
        <div className="waiter-order-screen">
          <main className="waiter-panel waiter-menu-panel">
            <div className="panel-heading">
              <div>
                <h1>Menu</h1>
              </div>
            </div>

            <div className="department-tabs">
              <button
                type="button"
                className={department === "KITCHEN" ? "active" : ""}
                onClick={() => switchDepartment("KITCHEN")}
              >
                Dania
              </button>
              <button
                type="button"
                className={department === "BAR" ? "active" : ""}
                onClick={() => switchDepartment("BAR")}
              >
                Bar
              </button>
            </div>

            <div className="category-tabs">
              <button
                type="button"
                className={selectedCategoryId === "ALL" ? "active" : ""}
                onClick={() => setSelectedCategoryId("ALL")}
              >
                Wszystko
              </button>
              {departmentCategories.map((category) => (
                <button
                  key={category.id}
                  type="button"
                  className={selectedCategoryId === category.id ? "active" : ""}
                  onClick={() => setSelectedCategoryId(category.id)}
                >
                  {category.name}
                </button>
              ))}
            </div>

            <div className="product-grid">
              {visibleProducts.map((product) => (
                <button
                  key={product.id}
                  type="button"
                  className="product-tile"
                  onClick={() => startProductAdd(product)}
                >
                  <span>{product.name}</span>
                  {product.description && <small>{product.description}</small>}
                  <strong>{formatMoney(Number(product.price))}</strong>
                </button>
              ))}
              {visibleProducts.length === 0 && (
                <div className="module-placeholder">Brak aktywnych produktów w tej sekcji.</div>
              )}
            </div>

          </main>

          <aside className="waiter-panel order-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">RACHUNEK</span>
                <h2>
                  {selectedOrder
                    ? `Zamówienie #${formatOrderNumber(selectedOrder)}`
                    : `Stolik ${selectedTable.table_number}`}
                </h2>
              </div>
              <strong>{formatMoney(getTicketTotal())}</strong>
            </div>
            <p className="muted">
              Stolik {selectedTable.table_number} · {guestCount} osób
            </p>

            {error && <div className="error-box">{error}</div>}

            <CartList
              existingItems={selectedOrderItems}
              cart={cart}
              selectedTicketLine={selectedTicketLine}
              productsById={productsById}
              getModifierLabel={getModifierLabel}
              getItemTotal={getCartItemTotal}
              onSelectExisting={(id) => setSelectedTicketLine({ type: "existing", id })}
              onSelectCart={(id) => setSelectedTicketLine({ type: "cart", id })}
              onIncrement={incrementCartItem}
              onDecrement={decrementCartItem}
            />
          </aside>

          <div className="pos-bottom-bar">
            <button type="button" className="ghost-button" onClick={addCourseSeparator}>
              Separator
            </button>
            <div className="functions-menu-wrapper">
              {isFunctionsMenuOpen && (
                <div className="functions-menu">
                  {selectedOrder && (
                    <button
                      type="button"
                      className="danger"
                      onClick={() => {
                        setIsFunctionsMenuOpen(false);
                        void deleteExistingOrder();
                      }}
                      disabled={isSubmitting}
                    >
                      Usuń cały rachunek
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      void splitSelectedBill();
                    }}
                    disabled={!selectedOrder || isSubmitting}
                  >
                    Podziel rachunek
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void changeOrderGuestCount();
                    }}
                    disabled={isSubmitting}
                  >
                    Zmień liczbę gości
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIsFunctionsMenuOpen(false);
                      setProductSearchQuery("");
                      setIsProductSearchOpen(true);
                    }}
                  >
                    Znajdź pozycję w menu
                  </button>
                  <button
                    type="button"
                    onClick={repeatLastDrink}
                    disabled={!hasRepeatableDrink || isSubmitting}
                  >
                    Ostatni napój
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIsFunctionsMenuOpen(false);
                      void handleOpenMergeModal();
                    }}
                    disabled={!selectedOrder || isSubmitting}
                  >
                    Połącz rachunek
                  </button>
                </div>
              )}
              <button
                type="button"
                className="ghost-button"
                onClick={() => setIsFunctionsMenuOpen((isOpen) => !isOpen)}
              >
                Funkcje
              </button>
            </div>
            <button
              type="button"
              className="ghost-button danger"
              onClick={() => {
                void voidSelectedEntry();
              }}
              disabled={!selectedTicketLine || isSubmitting}
            >
              Void
            </button>
            <button type="button" className="ghost-button" onClick={addInfoToLastItem}>
              Info
            </button>
            <button
              type="button"
              className="ghost-button close-check-button"
              onClick={openCheckout}
              disabled={!selectedOrder || hasCartItems(cart) || isSubmitting}
            >
              Zamknij rachunek
            </button>
            <button
              type="button"
              className="primary-button secondary-send"
              onClick={() => {
                void submitOrder("ORDER_BUILDER");
              }}
              disabled={!hasCartItems(cart) || isSubmitting}
            >
              Wyślij
            </button>
            <button type="button" className="ghost-button exit-button" onClick={resetToDashboard}>
              Cancel / Wyjdź
            </button>
          </div>
        </div>
      )}

      {mode === "CHECKOUT" && selectedOrder && selectedTable && (
        <div className="checkout-screen">
          <main className="waiter-panel checkout-details-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Order details</span>
                <h1>Table {selectedTable.table_number}</h1>
              </div>
              <strong>{formatMoney(Number(selectedOrder.total_amount))}</strong>
            </div>

            {error && <div className="error-box">{error}</div>}
            {notice && <div className="success-box">{notice}</div>}

            <CheckoutOrderDetails
              order={selectedOrder}
              items={selectedOrderItems}
              productsById={productsById}
            />
          </main>

          <aside className="waiter-panel checkout-actions-panel">
            <div className="payment-buttons">
              <button
                type="button"
                className="primary-button"
                disabled={isSubmitting}
                onClick={() => {
                  void closeOrderWithPayment("CARD");
                }}
              >
                Zamknij CARD
              </button>
              <button
                type="button"
                className="primary-button cash-button"
                disabled={isSubmitting}
                onClick={() => {
                  void closeOrderWithPayment("CASH");
                }}
              >
                Zamknij CASH
              </button>
            </div>

            <section className="discount-section">
              <div>
                <h2>Rabaty</h2>
              </div>
              <div className="discount-grid">
                {discounts.map((discount) => (
                  <button
                    key={discount.id}
                    type="button"
                    className={selectedOrder.discount_id === discount.id ? "selected" : ""}
                    disabled={isSubmitting}
                    onClick={() => {
                      void toggleDiscount(discount.id);
                    }}
                  >
                    <strong>{formatDiscountValue(discount)}</strong>
                  </button>
                ))}
                {discounts.length === 0 && (
                  <div className="empty-ticket">No discounts in database.</div>
                )}
              </div>
            </section>

            <section className="tip-section">
              <div>
                <h2>Napiwek</h2>
              </div>
              <div className="tip-quick-grid">
                {[10, 15, 20].map((percent) => (
                  <button
                    key={percent}
                    type="button"
                    className={isTipPercentSelected(percent) ? "selected" : ""}
                    disabled={isSubmitting}
                    onClick={() => {
                      void applyTipPercent(percent);
                    }}
                  >
                    {percent}%
                  </button>
                ))}
                <button
                  type="button"
                  className="clear-tip-button"
                  disabled={isSubmitting}
                  onClick={() => {
                    void applyTipAmount("0");
                  }}
                >
                  Clear
                </button>
              </div>
              <div className="tip-manual-row">
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={tipInput}
                  placeholder="Kwota napiwku"
                  onChange={(event) => setTipInput(event.target.value)}
                />
                <button
                  type="button"
                  className="ghost-button"
                  disabled={isSubmitting}
                  onClick={() => {
                    void applyTipAmount(tipInput);
                  }}
                >
                  Add tip
                </button>
              </div>
            </section>

            <button type="button" className="ghost-button" onClick={() => setMode("ORDER_BUILDER")}>
              Back
            </button>
          </aside>
        </div>
      )}

      {mode === "ORDER_DETAILS" && selectedOrder && (
        <div className="waiter-builder-grid">
          <main className="waiter-panel order-detail-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">{getOrderTableLabel(selectedOrder)}</span>
                <h1>Order #{formatOrderNumber(selectedOrder)}</h1>
              </div>
              <button type="button" className="ghost-button" onClick={resetToDashboard}>
                Back
              </button>
            </div>

            <div className="order-detail-list">
              {selectedOrderItems.map((item) => {
                const product = productsById.get(item.product_id);
                return (
                  <div key={item.id} className="order-detail-row">
                    <div>
                      <strong>{product?.name ?? `Product #${item.product_id}`}</strong>
                      <span>
                        {item.quantity} x {formatMoney(Number(item.unit_price))}
                      </span>
                    </div>
                    <b>{formatMoney(Number(item.total_price))}</b>
                  </div>
                );
              })}
            </div>
          </main>

          <aside className="waiter-panel waiter-action-panel">
            <span className="eyebrow">Summary</span>
            <h2>{formatMoney(Number(selectedOrder.total_amount))}</h2>
            <p className="muted">Payment and closing actions will be added in the next step.</p>
          </aside>
        </div>
      )}

      {pendingProduct && (
        <ProductOptionsModal
          product={pendingProduct}
          productModifiers={getProductModifiersForProduct(pendingProduct.id)}
          modifiersById={modifiersById}
          onClose={() => setPendingProduct(null)}
          onAdd={({ notes, productModifierIds }) => {
            appendCartItem(pendingProduct, {
              notes,
              productModifierIds,
            });
            setPendingProduct(null);
          }}
        />
      )}

      {isMergeModalOpen && selectedOrder && (
        <div className="modal-backdrop">
          <div className="product-options-modal product-search-modal">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Łączenie</span>
                <h2>Wybierz rachunek do dołączenia</h2>
              </div>
              <button type="button" className="ghost-button" onClick={() => setIsMergeModalOpen(false)}>
                Zamknij
              </button>
            </div>

            <div className="product-search-results">
              {mergeCandidates.map((candidate) => (
                <button
                  key={candidate.id}
                  type="button"
                  className={selectedMergeCandidateId === candidate.id ? "selected" : ""}
                  onClick={() => setSelectedMergeCandidateId(candidate.id)}
                >
                  <span>
                    <strong>Rachunek #{candidate.id}</strong>
                    {candidate.table_id ? <small>Stolik {floorTables.find((t) => t.table_id === candidate.table_id)?.table?.table_number ?? "?"}</small> : null}
                  </span>
                  <b>
                    {formatMoney(Number(candidate.total_amount))} ({candidate.item_count} poz.)
                  </b>
                </button>
              ))}
              {mergeCandidates.length === 0 && (
                <div className="empty-ticket">Brak innych rachunków do połączenia.</div>
              )}
            </div>

            <div className="bill-split-actions" style={{ justifyContent: "flex-end" }}>
              <button
                type="button"
                className="primary-button"
                disabled={!selectedMergeCandidateId || isMerging}
                onClick={async () => {
                  if (await confirm(`Czy na pewno chcesz dołączyć ten rachunek do rachunku #${selectedOrder.id}?`)) {
                    void handleMergeConfirm();
                  }
                }}
              >
                {isMerging ? "Łączenie..." : "Połącz rachunki"}
              </button>
            </div>
          </div>
        </div>
      )}

      {isProductSearchOpen && (
        <ProductSearchModal
          query={productSearchQuery}
          results={productSearchResults}
          onQueryChange={setProductSearchQuery}
          onClose={() => setIsProductSearchOpen(false)}
          onSelect={(product) => {
            setIsProductSearchOpen(false);
            setProductSearchQuery("");
            startProductAdd(product);
          }}
        />
      )}

      {isBillSplitOpen && selectedOrder && billSplitView && (
        <BillSplitModal
          view={billSplitView}
          selectedItemIds={selectedBillSplitItemIds}
          isSubmitting={isSubmitting}
          onToggleItem={toggleBillSplitItemSelection}
          onClose={() => {
            setIsBillSplitOpen(false);
            setSelectedBillSplitItemIds([]);
          }}
          onAddSegment={addBillSplitSegment}
          onDeleteLastEmptySegment={deleteLastEmptyBillSplitSegment}
          onDeleteSegment={deleteBillSplitSegment}
          onMoveToSegment={moveBillSplitSelection}
          onSplitItem={splitBillSplitItemAcrossSegments}
          onFinalize={finalizeBillSplit}
        />
      )}
    </section>
  );

  function getOrderTableLabel(order: Order): string {
    const table = floorTables.find((item) => item.table_id === order.table_id)?.table;
    return table ? `Table ${table.table_number}` : "No table";
  }

  function switchDepartment(nextDepartment: MenuDepartment) {
    setDepartment(nextDepartment);
    setSelectedCategoryId("ALL");
  }

  function openExistingOrder(order: Order) {
    const table = floorTables.find((item) => item.table_id === order.table_id)?.table;
    if (!table) {
      setError("Order table is not available on floor plan.");
      return;
    }

    setSelectedOrderId(order.id);
    setSelectedTable(table);
    setGuestCount(order.guest_count ?? table.current_guests ?? 1);
    setCart([]);
    setNotice(null);
    setError(null);
    setMode("ORDER_BUILDER");
  }

  async function selectTableForNewOrder(table: RestaurantTable | null | undefined) {
    if (!table || table.status !== "FREE") {
      return;
    }

    const rawGuestCount = await prompt({
      title: `Stolik ${table.table_number}`,
      label: "Liczba gości",
      defaultValue: String(guestCount),
      type: "number",
      confirmText: "Przejdź do menu",
      cancelText: "Anuluj",
    });

    if (rawGuestCount === null) {
      return;
    }

    const parsedGuestCount = Number(rawGuestCount);
    if (!Number.isInteger(parsedGuestCount) || parsedGuestCount <= 0) {
      setError("Guest count must be a positive number.");
      return;
    }

    setSelectedTable(table);
    setGuestCount(parsedGuestCount);
    setCart([]);
    setSelectedCategoryId("ALL");
    setMode("ORDER_BUILDER");
  }

  function startProductAdd(product: Product) {
    const availableModifiers = getProductModifiersForProduct(product.id);
    if (availableModifiers.length > 0 || requiresSteakInfo(product)) {
      setPendingProduct(product);
      return;
    }

    appendCartItem(product, { notes: null, productModifierIds: [] });
  }

  function appendCartItem(
    product: Product,
    options: { notes: string | null; productModifierIds: number[] },
  ) {
    setNotice(null);
    setCart((items) => [
      ...items,
      {
        id: crypto.randomUUID(),
        product,
        quantity: 1,
        position: items.filter(isCartItem).length,
        courseNumber: getCurrentCourseNumber(items),
        notes: options.notes,
        productModifierIds: options.productModifierIds,
      },
    ]);
  }

  function repeatLastDrink() {
    const lastCartDrink = [...cart]
      .reverse()
      .find(
        (entry): entry is CartItem =>
          isCartItem(entry) && isBarProduct(entry.product, categoriesById),
      );

    if (lastCartDrink) {
      appendCartItem(lastCartDrink.product, {
        notes: lastCartDrink.notes ?? null,
        productModifierIds: [...lastCartDrink.productModifierIds],
      });
      setIsFunctionsMenuOpen(false);
      setNotice(`Dodano ponownie: ${lastCartDrink.product.name}.`);
      return;
    }

    const lastSavedDrink = [...selectedOrderItems].reverse().find((item) => {
      const product = productsById.get(item.product_id);
      return product ? isBarProduct(product, categoriesById) : false;
    });
    const product = lastSavedDrink
      ? productsById.get(lastSavedDrink.product_id)
      : undefined;

    if (!lastSavedDrink || !product) {
      setError("Brak ostatniego napoju do powtórzenia.");
      return;
    }

    appendCartItem(product, {
      notes: lastSavedDrink.notes,
      productModifierIds: [],
    });
    setIsFunctionsMenuOpen(false);
    setNotice(`Dodano ponownie: ${product.name}.`);
  }

  function incrementCartItem(entryId: string) {
    setCart((items) =>
      items.map((entry) =>
        isCartItem(entry) && entry.id === entryId
          ? { ...entry, quantity: entry.quantity + 1 }
          : entry,
      ),
    );
  }

  function decrementCartItem(entryId: string) {
    setCart((items) =>
      items
        .map((entry) =>
          isCartItem(entry) && entry.id === entryId
            ? { ...entry, quantity: entry.quantity - 1 }
            : entry,
        )
        .filter((entry) => !isCartItem(entry) || entry.quantity > 0),
    );
  }

  function addCourseSeparator() {
    setCart((items) => {
      if (!hasCartItems(items)) {
        return items;
      }
      return [
        ...items,
        {
          id: crypto.randomUUID(),
          type: "SEPARATOR",
          nextCourseNumber: getCurrentCourseNumber(items) + 1,
        },
      ];
    });
  }

  async function addInfoToLastItem() {
    const lastItem = [...cart].reverse().find(isCartItem);
    if (!lastItem) {
      return;
    }

    const nextNotes = await prompt({
      title: "Info / notes",
      defaultValue: lastItem.notes ?? "",
    });
    if (nextNotes === null) {
      return;
    }

    setCart((items) =>
      items.map((entry) =>
        isCartItem(entry) && entry.id === lastItem.id
          ? { ...entry, notes: nextNotes.trim() || null }
          : entry,
      ),
    );
  }

  function resetToDashboard() {
    setMode("DASHBOARD");
    setSelectedTable(null);
    setSelectedOrderId(null);
    setCart([]);
    setSelectedTicketLine(null);
    setIsBillSplitOpen(false);
    setBillSplitView(null);
    setSelectedBillSplitItemIds([]);
    setIsFunctionsMenuOpen(false);
    setIsProductSearchOpen(false);
    setTipInput("");
    setError(null);
  }

  function openCheckout() {
    if (!selectedOrder || hasCartItems(cart)) {
      return;
    }

    setError(null);
    setNotice(null);
    setSelectedTicketLine(null);
    setTipInput(Number(selectedOrder.tip_amount) > 0 ? selectedOrder.tip_amount : "");
    setMode("CHECKOUT");
  }

  function getTicketTotal(): number {
    return Number(selectedOrder?.total_amount ?? 0) + cartTotal;
  }

  function replaceOrder(updatedOrder: Order) {
    setOrders((items) =>
      items.map((order) => (order.id === updatedOrder.id ? updatedOrder : order)),
    );
  }

  async function toggleDiscount(discountId: number) {
    if (!token || !selectedOrder) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const updatedOrder =
        selectedOrder.discount_id === discountId
          ? await removeDiscountFromWaiterOrder(token, selectedOrder.id)
          : await applyDiscountToWaiterOrder(token, selectedOrder.id, discountId);
      replaceOrder(updatedOrder);
      setNotice(
        selectedOrder.discount_id === discountId
          ? "Discount removed."
          : "Discount applied.",
      );
      await loadWaiterData();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not update discount.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function applyTipPercent(percent: number) {
    if (!selectedOrder) {
      return;
    }

    if (isTipPercentSelected(percent)) {
      await applyTipAmount("0");
      return;
    }

    const tipBase = getTipBaseAmount(selectedOrder);
    const tipAmount = (tipBase * percent) / 100;
    await applyTipAmount(tipAmount.toFixed(2));
  }

  function isTipPercentSelected(percent: number): boolean {
    if (!selectedOrder) {
      return false;
    }

    const tipAmount = Number(selectedOrder.tip_amount);
    if (tipAmount <= 0) {
      return false;
    }

    const expectedTip = (getTipBaseAmount(selectedOrder) * percent) / 100;
    return Math.abs(tipAmount - expectedTip) < 0.015;
  }

  function getTipBaseAmount(order: Order): number {
    return Math.max(Number(order.total_amount) - Number(order.tip_amount), 0);
  }

  async function applyTipAmount(rawAmount: string) {
    if (!token || !selectedOrder) {
      return;
    }

    const amount = Number(rawAmount);
    if (!Number.isFinite(amount) || amount < 0) {
      setError("Tip amount must be zero or greater.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const updatedOrder = await updateWaiterOrderTip(
        token,
        selectedOrder.id,
        amount.toFixed(2),
      );
      replaceOrder(updatedOrder);
      setTipInput(amount > 0 ? amount.toFixed(2) : "");
      setNotice(amount > 0 ? "Tip added." : "Tip removed.");
      await loadWaiterData();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not update tip.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function closeOrderWithPayment(method: "CARD" | "CASH") {
    if (!token || !selectedOrder) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const invoiceNip = await askForInvoiceNip();
      if (invoiceNip === null) {
        return;
      }

      if (invoiceNip) {
        await createInvoiceForWaiterOrder(token, selectedOrder.id, {
          nip: invoiceNip,
          company_name: `Customer NIP ${invoiceNip}`,
        });
      }

      await registerWaiterPayment(token, selectedOrder.id, {
        method,
        amount: selectedOrder.total_amount,
        close_order: true,
      });
      await openReceiptPdfs(selectedOrder.id);
      setNotice(`Order #${selectedOrder.id} closed.`);
      resetToDashboard();
      await loadWaiterData();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not close order.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function askForInvoiceNip(): Promise<string | null> {
    const wantsNip = await confirm({ title: "Czy dodać NIP do rachunku?" });
    if (!wantsNip) {
      return "";
    }

    const nip = await prompt({ title: "Wpisz NIP" });
    if (nip === null) {
      return null;
    }

    const normalizedNip = nip.trim();
    if (!normalizedNip) {
      setError("NIP is required when invoice data is requested.");
      return null;
    }

    return normalizedNip;
  }

  async function openReceiptPdfs(orderId: number) {
    if (!token) {
      return;
    }

    const [fiscalReceiptBlob, guestCheckBlob] = await Promise.all([
      generateWaiterReceiptPdf(token, orderId),
      generateWaiterGuestCheckPdf(token, orderId),
    ]);
    openPdfBlob(fiscalReceiptBlob);
    openPdfBlob(guestCheckBlob);
  }

  function openPdfBlob(blob: Blob) {
    const receiptUrl = window.URL.createObjectURL(blob);
    window.open(receiptUrl, "_blank", "noopener,noreferrer");
    window.setTimeout(() => window.URL.revokeObjectURL(receiptUrl), 60_000);
  }

  async function submitOrder(afterSubmit: "DASHBOARD" | "ORDER_BUILDER") {
    if (!token || !user || !selectedTable) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const payloadItems = cart.filter(isCartItem).map((item, index) => ({
        product_id: item.product.id,
        quantity: item.quantity,
        position: index,
        course_number: item.courseNumber,
        notes: item.notes ?? null,
        product_modifier_ids: item.productModifierIds,
      }));
      const order = selectedOrder
        ? await addItemsToWaiterOrder(token, selectedOrder.id, {
            items: payloadItems,
          })
        : await createWaiterOrder(token, {
            table_id: selectedTable.id,
            waiter_id: user.id,
            guest_count: guestCount,
            source: "WAITER",
            items: payloadItems,
          });
      setNotice(`Order #${order.id} sent to production.`);
      setCart([]);
      setSelectedTicketLine(null);
      if (afterSubmit === "DASHBOARD") {
        resetToDashboard();
      } else {
        setSelectedOrderId(order.id);
      }
      await loadWaiterData();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not create order.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleOpenMergeModal() {
    if (!token || !selectedOrder) return;
    try {
      setIsSubmitting(true);
      const candidates = await getWaiterMergeCandidates(token, selectedOrder.id);
      setMergeCandidates(candidates);
      setSelectedMergeCandidateId(null);
      setIsMergeModalOpen(true);
    } catch (err) {
      console.error("handleOpenMergeModal error", err);
      if (err instanceof ApiError) {
        setError(`Błąd API: ${err.message}`);
      } else {
        setError(`Wystąpił błąd: ${err instanceof Error ? err.message : String(err)}`);
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleMergeConfirm() {
    if (!token || !selectedOrder || !selectedMergeCandidateId) return;
    try {
      setIsMerging(true);
      await mergeWaiterOrder(token, selectedOrder.id, selectedMergeCandidateId);
      setIsMergeModalOpen(false);
      setNotice("Rachunki zostały połączone!");
      await loadWaiterData();
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(`Błąd: ${err.message}`);
      }
    } finally {
      setIsMerging(false);
    }
  }

  async function voidSelectedEntry() {
    if (!token || !selectedTicketLine) {
      return;
    }

    setError(null);
    setNotice(null);

    if (selectedTicketLine.type === "cart") {
      try {
        const managerPin = await getManagerPinIfNeeded();
        if (managerPin === null) {
          return;
        }
        if (managerPin) {
          await verifyManagerPin(token, managerPin);
        }
        setCart((items) => items.filter((entry) => entry.id !== selectedTicketLine.id));
        setSelectedTicketLine(null);
      } catch (exc) {
        setError(exc instanceof ApiError ? exc.message : "Manager PIN is invalid.");
      }
      return;
    }

    if (!selectedOrder) {
      return;
    }

    setIsSubmitting(true);
    try {
      const managerPin = await getManagerPinIfNeeded();
      if (managerPin === null) {
        return;
      }
      await voidWaiterOrderItem(
        token,
        selectedOrder.id,
        selectedTicketLine.id,
        managerPin || undefined,
      );
      setSelectedTicketLine(null);
      setNotice("Selected item was voided.");
      await loadWaiterData();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not void selected item.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function splitSelectedBill() {
    if (!token || !selectedOrder) {
      setError("Open an existing sent order first.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const view = await getWaiterBillSplit(token, selectedOrder.id);
      setBillSplitView(view);
      setSelectedBillSplitItemIds([]);
      setIsBillSplitOpen(true);
      setIsFunctionsMenuOpen(false);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not open bill split.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function toggleBillSplitItemSelection(itemId: number) {
    setSelectedBillSplitItemIds((itemIds) =>
      itemIds.includes(itemId)
        ? itemIds.filter((id) => id !== itemId)
        : [...itemIds, itemId],
    );
  }

  async function addBillSplitSegment() {
    if (!token || !selectedOrder) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await createWaiterBillSegment(token, selectedOrder.id);
      setBillSplitView(await getWaiterBillSplit(token, selectedOrder.id));
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not add check.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function deleteBillSplitSegment(segmentId: number) {
    if (!token || !selectedOrder) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await deleteWaiterBillSegment(token, selectedOrder.id, segmentId);
      setBillSplitView(await getWaiterBillSplit(token, selectedOrder.id));
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Only empty checks can be deleted.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function deleteLastEmptyBillSplitSegment() {
    if (!billSplitView) {
      return;
    }

    const lastEmptySegment = [...billSplitView.segments]
      .reverse()
      .find((segment) => segment.items.length === 0);

    if (!lastEmptySegment) {
      setError("There is no empty check to remove.");
      return;
    }

    void deleteBillSplitSegment(lastEmptySegment.id);
  }

  async function moveBillSplitSelection(targetSegmentId: number) {
    if (!token || !selectedOrder || !billSplitView || selectedBillSplitItemIds.length === 0) {
      return;
    }

    const itemsToMove: Array<{ order_item_id: number; quantity?: string }> = [];
    for (const itemId of selectedBillSplitItemIds) {
      const item = billSplitView.original_items.find((candidate) => candidate.id === itemId);
      if (!item) {
        continue;
      }

      const availableQuantity = Number(item.remaining_quantity);
      if (availableQuantity <= 0) {
        continue;
      }

      let quantity = availableQuantity;
      if (availableQuantity > 1) {
        const rawQuantity = await prompt({
          title: `Ile przenieść: ${item.product_name}? Dostępne: ${formatQuantity(item.remaining_quantity)}`,
          defaultValue: "1",
        });
        if (rawQuantity === null) {
          return;
        }

        quantity = Number(rawQuantity.replace(",", "."));
        if (!Number.isFinite(quantity) || quantity < 1 || quantity > availableQuantity) {
          setError("Quantity must be at least 1 and cannot exceed available quantity.");
          return;
        }
      }

      itemsToMove.push({
        order_item_id: item.id,
        quantity: formatApiDecimal(quantity),
      });
    }

    if (itemsToMove.length === 0) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const view = await moveWaiterBillSplitItems(token, selectedOrder.id, {
        target_segment_id: targetSegmentId,
        items: itemsToMove,
      });
      setBillSplitView(view);
      setSelectedBillSplitItemIds([]);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not move items.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function splitBillSplitItemAcrossSegments(itemId: number, segmentIds: number[]) {
    if (!token || !selectedOrder) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const view = await splitWaiterBillSplitItem(token, selectedOrder.id, {
        order_item_id: itemId,
        target_segment_ids: segmentIds,
      });
      setBillSplitView(view);
      setSelectedBillSplitItemIds((itemIds) => itemIds.filter((id) => id !== itemId));
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not split item.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function finalizeBillSplit() {
    if (!token || !selectedOrder || !billSplitView) {
      return;
    }

    const nonEmptySegments = billSplitView.segments.filter(
      (segment) => segment.items.length > 0,
    );
    const segmentGuestCounts: Array<{ segment_id: number; guest_count: number }> = [];
    for (const segment of nonEmptySegments) {
      const rawGuestCount = await prompt({
        title: `Liczba gości dla ${segment.name}`,
        defaultValue: String(selectedOrder.guest_count ?? guestCount),
      });
      if (rawGuestCount === null) {
        return;
      }

      const parsedGuestCount = Number(rawGuestCount);
      if (!Number.isInteger(parsedGuestCount) || parsedGuestCount <= 0) {
        setError("Guest count must be a positive number.");
        return;
      }

      segmentGuestCounts.push({
        segment_id: segment.id,
        guest_count: parsedGuestCount,
      });
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const splitOrders = await finalizeWaiterBillSplit(token, selectedOrder.id, {
        segment_guest_counts: segmentGuestCounts,
      });
      setNotice(
        splitOrders.length > 0
          ? `Rachunek podzielony: ${splitOrders
              .map((order) => `#${formatOrderNumber(order)}`)
              .join(", ")}.`
          : "Rachunek podzielony.",
      );
      setIsBillSplitOpen(false);
      setBillSplitView(null);
      setSelectedBillSplitItemIds([]);
      await loadWaiterData();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not finalize bill split.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function changeOrderGuestCount() {
    const nextGuestCount = await prompt({
      title: "Liczba gości",
      defaultValue: String(selectedOrder?.guest_count ?? guestCount),
    });
    if (nextGuestCount === null) {
      return;
    }

    const parsedGuestCount = Number(nextGuestCount);
    if (!Number.isInteger(parsedGuestCount) || parsedGuestCount <= 0) {
      setError("Guest count must be a positive number.");
      return;
    }

    setIsFunctionsMenuOpen(false);
    setGuestCount(parsedGuestCount);

    if (!token || !selectedOrder) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const updatedOrder = await updateWaiterOrder(token, selectedOrder.id, {
        guest_count: parsedGuestCount,
      });
      replaceOrder(updatedOrder);
      setNotice("Guest count updated.");
      await loadWaiterData();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not update guest count.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function getManagerPinIfNeeded(): Promise<string | null> {
    if (user?.role === "ADMIN" || user?.role === "MANAGER") {
      return "";
    }

    const managerPin = await prompt({ title: "Manager PIN", type: "password" });
    if (!managerPin) {
      return null;
    }
    return managerPin;
  }

  async function deleteExistingOrder() {
    if (!token || !selectedOrder) {
      return;
    }

    const managerPin = await prompt({ title: "Manager PIN", type: "password" });
    if (!managerPin) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await cancelWaiterOrder(token, selectedOrder.id, managerPin);
      setNotice(`Order #${selectedOrder.id} cancelled.`);
      resetToDashboard();
      await loadWaiterData();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not delete order.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function getProductModifiersForProduct(productId: number) {
    return productModifiers.filter((item) => item.product_id === productId);
  }

  function getModifierLabel(productModifierId: number): string {
    const productModifier = productModifiers.find((item) => item.id === productModifierId);
    if (!productModifier) {
      return `Modifier #${productModifierId}`;
    }
    const modifier = modifiersById.get(productModifier.modifier_id);
    const price = getProductModifierPrice(productModifier, modifiersById);
    return `${modifier?.name ?? `Modifier #${productModifier.modifier_id}`} ${
      price > 0 ? `+${formatMoney(price)}` : ""
    }`.trim();
  }

  function getCartItemTotal(item: CartItem): number {
    const modifierTotal = item.productModifierIds.reduce((total, productModifierId) => {
      const productModifier = productModifiers.find((modifier) => modifier.id === productModifierId);
      return productModifier
        ? total + getProductModifierPrice(productModifier, modifiersById)
        : total;
    }, 0);
    return (Number(item.product.price) + modifierTotal) * item.quantity;
  }
}

function BillSplitModal({
  view,
  selectedItemIds,
  isSubmitting,
  onToggleItem,
  onClose,
  onAddSegment,
  onDeleteLastEmptySegment,
  onDeleteSegment,
  onMoveToSegment,
  onSplitItem,
  onFinalize,
}: {
  view: BillSplitView;
  selectedItemIds: number[];
  isSubmitting: boolean;
  onToggleItem: (itemId: number) => void;
  onClose: () => void;
  onAddSegment: () => void;
  onDeleteLastEmptySegment: () => void;
  onDeleteSegment: (segmentId: number) => void;
  onMoveToSegment: (segmentId: number) => void;
  onSplitItem: (itemId: number, segmentIds: number[]) => void;
  onFinalize: () => void;
}) {
  const [splitItem, setSplitItem] = useState<BillSplitOriginalItem | null>(null);
  const selectedCount = selectedItemIds.length;
  const assignedTotal = view.segments.reduce(
    (total, segment) => total + Number(segment.total_amount),
    0,
  );
  const hasEmptySegment = view.segments.some((segment) => segment.items.length === 0);

  return (
    <div className="modal-backdrop bill-split-backdrop">
      <div className="bill-split-modal">
        <div className="bill-split-header">
          <div>
            <span className="eyebrow">Podział rachunku</span>
            <h2>Zamówienie #{view.order_id}</h2>
            <p className="muted">
              Wybierz pozycje z oryginalnego rachunku, a następnie dotknij rachunku docelowego.
            </p>
          </div>
          <div className="bill-split-summary">
            <span>
              Pozostało <strong>{formatMoney(Number(view.unassigned_total))}</strong>
            </span>
            <span>
              Przypisano <strong>{formatMoney(assignedTotal)}</strong>
            </span>
          </div>
        </div>

        <div className="bill-split-layout">
          <section className="bill-split-original">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Oryginalny rachunek</span>
                <h3>Pozycje</h3>
              </div>
              <strong>wybrano: {selectedCount}</strong>
            </div>
            <div className="bill-split-item-list">
              {view.original_items.map((item) => {
                const remainingQuantity = Number(item.remaining_quantity);
                const isSelected = selectedItemIds.includes(item.id);
                return (
                  <div
                    key={item.id}
                    className={`bill-split-source-row ${isSelected ? "selected" : ""} ${
                      remainingQuantity <= 0 ? "fully-assigned" : ""
                    }`}
                  >
                    <button
                      type="button"
                      disabled={remainingQuantity <= 0 || isSubmitting}
                      onClick={() => onToggleItem(item.id)}
                    >
                      <span>
                        <strong>{item.product_name}</strong>
                        <small>
                          Dostępne: {formatQuantity(item.remaining_quantity)} /{" "}
                          {formatQuantity(item.quantity)}
                        </small>
                        {item.notes && <small>{item.notes}</small>}
                      </span>
                      <b>{formatMoney(Number(item.unit_price))}</b>
                    </button>
                    <button
                      type="button"
                      className="split-item-button"
                      disabled={isSubmitting || view.segments.length < 2}
                      onClick={() => setSplitItem(item)}
                    >
                      Split item
                    </button>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="bill-split-targets">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Części rachunku</span>
                <h3>Rachunki</h3>
              </div>
              <div className="bill-split-segment-actions">
                <button
                  type="button"
                  className="ghost-button danger"
                  disabled={isSubmitting || !hasEmptySegment}
                  onClick={onDeleteLastEmptySegment}
                >
                  Anuluj dodanie checka
                </button>
                <button
                  type="button"
                  className="primary-button"
                  disabled={isSubmitting}
                  onClick={onAddSegment}
                >
                  Dodaj rachunek
                </button>
              </div>
            </div>

            <div className="bill-segment-scroll">
              {view.segments.map((segment) => (
                <button
                  key={segment.id}
                  type="button"
                  className="bill-segment-card"
                  disabled={isSubmitting}
                  onClick={() => onMoveToSegment(segment.id)}
                >
                  <span className="bill-segment-title">
                    <strong>{segment.name}</strong>
                    <b>{formatMoney(Number(segment.total_amount))}</b>
                  </span>
                  <span className="bill-segment-items">
                    {segment.items.map((item) => (
                      <span key={item.id} className="bill-segment-item">
                        <span>
                          <strong>{item.product_name}</strong>
                          <small>
                            {formatQuantity(item.quantity)} x{" "}
                            {formatMoney(Number(item.unit_price))}
                          </small>
                          {Number(item.quantity) > 0 && Number(item.quantity) < 1 && (
                            <small>{formatQuantity(item.quantity)} część</small>
                          )}
                          {item.notes && <small>{item.notes}</small>}
                        </span>
                        <b>{formatMoney(Number(item.total_price))}</b>
                      </span>
                    ))}
                    {segment.items.length === 0 && (
                      <span className="bill-segment-empty">Dotknij, aby przenieść tutaj wybrane pozycje.</span>
                    )}
                  </span>
                  {segment.items.length === 0 && view.segments.length > 1 && (
                    <span
                      className="remove-segment-button"
                      onClick={(event) => {
                        event.stopPropagation();
                        onDeleteSegment(segment.id);
                      }}
                    >
                      Usuń pusty rachunek
                    </span>
                  )}
                </button>
              ))}
            </div>
          </section>
        </div>

        <div className="bill-split-actions">
          <button type="button" className="ghost-button danger" onClick={onClose}>
            Cofnij
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={isSubmitting}
            onClick={onFinalize}
          >
            Zakończ podział
          </button>
        </div>

        {splitItem && (
          <SplitItemModal
            item={splitItem}
            view={view}
            isSubmitting={isSubmitting}
            onClose={() => setSplitItem(null)}
            onSplit={(segmentIds) => {
              onSplitItem(splitItem.id, segmentIds);
              setSplitItem(null);
            }}
          />
        )}
      </div>
    </div>
  );
}

function SplitItemModal({
  item,
  view,
  isSubmitting,
  onClose,
  onSplit,
}: {
  item: BillSplitOriginalItem;
  view: BillSplitView;
  isSubmitting: boolean;
  onClose: () => void;
  onSplit: (segmentIds: number[]) => void;
}) {
  const [selectedSegmentIds, setSelectedSegmentIds] = useState<number[]>([]);
  const shareQuantity =
    selectedSegmentIds.length > 0
      ? Number(item.quantity) / selectedSegmentIds.length
      : 0;

  return (
    <div className="nested-modal-backdrop">
      <div className="split-item-modal">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Wspólna pozycja</span>
            <h3>{item.product_name}</h3>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Zamknij
          </button>
        </div>

        <p className="muted">
          Wybierz co najmniej dwa rachunki. Każdy wybrany rachunek otrzyma{" "}
          {shareQuantity > 0 ? formatQuantity(String(shareQuantity)) : "0"} część.
        </p>

        <div className="split-item-checks">
          {view.segments.map((segment) => {
            const isSelected = selectedSegmentIds.includes(segment.id);
            return (
              <button
                key={segment.id}
                type="button"
                className={isSelected ? "selected" : ""}
                onClick={() =>
                  setSelectedSegmentIds((segmentIds) =>
                    isSelected
                      ? segmentIds.filter((id) => id !== segment.id)
                      : [...segmentIds, segment.id],
                  )
                }
              >
                <strong>{segment.name}</strong>
                <span>{formatMoney(Number(segment.total_amount))}</span>
              </button>
            );
          })}
        </div>

        <button
          type="button"
          className="primary-button"
          disabled={isSubmitting || selectedSegmentIds.length < 2}
          onClick={() => onSplit(selectedSegmentIds)}
        >
          Split item
        </button>
      </div>
    </div>
  );
}

function CartList({
  existingItems,
  cart,
  selectedTicketLine,
  productsById,
  getModifierLabel,
  getItemTotal,
  onSelectExisting,
  onSelectCart,
  onIncrement,
  onDecrement,
}: {
  existingItems: OrderItem[];
  cart: CartEntry[];
  selectedTicketLine: TicketSelection | null;
  productsById: Map<number, Product>;
  getModifierLabel: (productModifierId: number) => string;
  getItemTotal: (item: CartItem) => number;
  onSelectExisting: (itemId: number) => void;
  onSelectCart: (entryId: string) => void;
  onIncrement: (entryId: string) => void;
  onDecrement: (entryId: string) => void;
}) {
  return (
    <div className="cart-list">
      {existingItems.map((item) => {
        const product = productsById.get(item.product_id);
        return (
          <button
            key={item.id}
            type="button"
            className={`cart-row locked ${
              selectedTicketLine?.type === "existing" && selectedTicketLine.id === item.id
                ? "selected"
                : ""
            }`}
            onClick={() => onSelectExisting(item.id)}
          >
            <div>
              <strong>* {product?.name ?? `Product #${item.product_id}`}</strong>
              <span>
                Kurs {item.course_number} · {item.quantity} x {formatMoney(Number(item.unit_price))}
              </span>
              {item.notes && <small>{item.notes}</small>}
            </div>
            <b>{formatMoney(Number(item.total_price))}</b>
          </button>
        );
      })}
      {cart.map((entry) =>
        isCartItem(entry) ? (
          <div
            key={entry.id}
            className={`cart-row ${
              selectedTicketLine?.type === "cart" && selectedTicketLine.id === entry.id
                ? "selected"
                : ""
            }`}
            onClick={() => onSelectCart(entry.id)}
          >
            <div>
              <strong>{entry.product.name}</strong>
              <span>
                Kurs {entry.courseNumber} · {formatMoney(getItemTotal(entry))}
              </span>
              {entry.notes && <small>{entry.notes}</small>}
              {entry.productModifierIds.map((productModifierId) => (
                <small key={productModifierId}>{getModifierLabel(productModifierId)}</small>
              ))}
            </div>
            <div className="quantity-stepper">
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  onDecrement(entry.id);
                }}
              >
                -
              </button>
              <span>{entry.quantity}</span>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  onIncrement(entry.id);
                }}
              >
                +
              </button>
            </div>
          </div>
        ) : (
          <button
            key={entry.id}
            type="button"
            className={`course-separator ${
              selectedTicketLine?.type === "cart" && selectedTicketLine.id === entry.id
                ? "selected"
                : ""
            }`}
            onClick={() => onSelectCart(entry.id)}
          >
            Kurs {entry.nextCourseNumber}
          </button>
        ),
      )}
      {existingItems.length === 0 && !hasCartItems(cart) && (
        <div className="empty-ticket">Wybierz produkty, aby utworzyć zamówienie.</div>
      )}
    </div>
  );
}

function CheckoutOrderDetails({
  order,
  items,
  productsById,
}: {
  order: Order;
  items: OrderItem[];
  productsById: Map<number, Product>;
}) {
  return (
    <div className="checkout-ticket">
      <div className="checkout-ticket-list">
        {items.map((item) => {
          const product = productsById.get(item.product_id);
          return (
            <div key={item.id} className="checkout-ticket-row">
              <div>
                <strong>{product?.name ?? `Product #${item.product_id}`}</strong>
                <span>
                  Kurs {item.course_number} · {item.quantity} x{" "}
                  {formatMoney(Number(item.unit_price))}
                </span>
                {item.notes && <small>{item.notes}</small>}
              </div>
              <b>{formatMoney(Number(item.total_price))}</b>
            </div>
          );
        })}
      </div>

      <div className="checkout-totals">
        <span>
          Podsuma <strong>{formatMoney(Number(order.subtotal_amount))}</strong>
        </span>
        <span>
          Rabat <strong>-{formatMoney(Number(order.discount_amount))}</strong>
        </span>
        <span>
          Napiwek <strong>{formatMoney(Number(order.tip_amount))}</strong>
        </span>
        <b>
          Suma <strong>{formatMoney(Number(order.total_amount))}</strong>
        </b>
      </div>
    </div>
  );
}



function ProductOptionsModal({
  product,
  productModifiers,
  modifiersById,
  onClose,
  onAdd,
}: {
  product: Product;
  productModifiers: ProductModifier[];
  modifiersById: Map<number, Modifier>;
  onClose: () => void;
  onAdd: (options: { notes: string | null; productModifierIds: number[] }) => void;
}) {
  const [notes, setNotes] = useState("");
  const [selectedProductModifierIds, setSelectedProductModifierIds] = useState<number[]>([]);

  const roastLevels = ["Rare", "Medium rare", "Medium", "Medium well", "Well done"];

  return (
    <div className="modal-backdrop">
      <div className="product-options-modal">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Opcje pozycji</span>
            <h2>{product.name}</h2>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Zamknij
          </button>
        </div>

        {requiresSteakInfo(product) && (
          <label className="compact-field">
            Stopień wysmażenia
            <select
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            >
              <option value="">Wybierz stopień</option>
              {roastLevels.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </label>
        )}

        <label className="compact-field">
          Uwagi
          <input
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="np. bez cebuli"
          />
        </label>

        {productModifiers.length > 0 && (
          <div className="modifier-choice-list">
            {productModifiers.map((productModifier) => {
              const modifier = modifiersById.get(productModifier.modifier_id);
              const price = getProductModifierPrice(productModifier, modifiersById);
              const isSelected = selectedProductModifierIds.includes(productModifier.id);
              return (
                <label key={productModifier.id} className="modifier-choice">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={(event) => {
                      setSelectedProductModifierIds((ids) =>
                        event.target.checked
                          ? [...ids, productModifier.id]
                          : ids.filter((id) => id !== productModifier.id),
                      );
                    }}
                  />
                  <span>{modifier?.name ?? `Modifier #${productModifier.modifier_id}`}</span>
                  <strong>{price > 0 ? `+${formatMoney(price)}` : "Za darmo"}</strong>
                </label>
              );
            })}
          </div>
        )}

        <button
          type="button"
          className="primary-button"
          onClick={() =>
            onAdd({
              notes: notes.trim() || null,
              productModifierIds: selectedProductModifierIds,
            })
          }
        >
          Dodaj do rachunku
        </button>
      </div>
    </div>
  );
}

function ProductSearchModal({
  query,
  results,
  onQueryChange,
  onClose,
  onSelect,
}: {
  query: string;
  results: Product[];
  onQueryChange: (query: string) => void;
  onClose: () => void;
  onSelect: (product: Product) => void;
}) {
  return (
    <div className="modal-backdrop">
      <div className="product-options-modal product-search-modal">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Wyszukiwanie</span>
            <h2>Szukaj pozycji</h2>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Zamknij
          </button>
        </div>

        <label className="compact-field">
          Nazwa produktu
          <input
            autoFocus
            value={query}
            placeholder="Zacznij pisać..."
            onChange={(event) => onQueryChange(event.target.value)}
          />
        </label>

        <div className="product-search-results">
          {results.map((product) => (
            <button
              key={product.id}
              type="button"
              onClick={() => onSelect(product)}
            >
              <span>
                <strong>{product.name}</strong>
                {product.description && <small>{product.description}</small>}
              </span>
              <b>{formatMoney(Number(product.price))}</b>
            </button>
          ))}
          {query.trim() && results.length === 0 && (
            <div className="empty-ticket">Brak pasujących produktów.</div>
          )}
          {!query.trim() && (
            <div className="empty-ticket">Wpisz nazwę produktu, aby wyszukać.</div>
          )}
        </div>
      </div>
    </div>
  );
}

function isCartItem(entry: CartEntry): entry is CartItem {
  return !("type" in entry);
}

function isFullscreenMode(mode: WaiterMode): boolean {
  return mode === "ORDER_BUILDER" || mode === "CHECKOUT" || mode === "TABLE_PICKER";
}

function hasCartItems(entries: CartEntry[]): boolean {
  return entries.some(isCartItem);
}

function getCurrentCourseNumber(entries: CartEntry[]): number {
  return entries.reduce(
    (courseNumber, entry) =>
      isCartItem(entry) ? courseNumber : entry.nextCourseNumber,
    1,
  );
}

function requiresSteakInfo(product: Product): boolean {
  const name = product.name.toLowerCase();
  return name.includes("steak") || name.includes("stek");
}

function getProductModifierPrice(
  productModifier: ProductModifier,
  modifiersById: Map<number, Modifier>,
): number {
  if (productModifier.price_override !== null) {
    return Number(productModifier.price_override);
  }
  return Number(modifiersById.get(productModifier.modifier_id)?.price ?? 0);
}

function isBarCategory(categoryName: string): boolean {
  const normalizedName = categoryName.toLowerCase();
  return barCategoryWords.some((word) => normalizedName.includes(word));
}

function isBarProduct(
  product: Product,
  categoriesById: Map<number, ProductCategory>,
): boolean {
  const category = categoriesById.get(product.category_id);
  return category ? isBarCategory(category.name) : false;
}

function formatDiscountValue(discount: Discount): string {
  const type = discount.type.toUpperCase();
  const value = Number(discount.value);

  if (type === "PERCENT" || type === "PERCENTAGE") {
    return `${value}%`;
  }

  return formatMoney(value);
}

function formatMoney(value: number): string {
  return new Intl.NumberFormat("pl-PL", {
    style: "currency",
    currency: "PLN",
  }).format(value);
}

function formatOrderNumber(order: Order): string {
  if (order.split_parent_order_id && order.split_sequence) {
    return `${order.split_parent_order_id}/${order.split_sequence}`;
  }
  return String(order.id);
}

function formatQuantity(value: string | number): string {
  const quantity = Number(value);
  if (!Number.isFinite(quantity)) {
    return String(value);
  }
  return new Intl.NumberFormat("pl-PL", {
    maximumFractionDigits: 3,
  }).format(quantity);
}

function formatApiDecimal(value: number): string {
  return value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}
