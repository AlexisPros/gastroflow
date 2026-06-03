import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/apiClient";
import {
  getFloorPlanView,
  type FloorPlan,
  type FloorPlanDecoration,
  type FloorTableView,
  type RestaurantTable,
} from "../api/floorPlanApi";
import {
  addItemsToWaiterOrder,
  cancelWaiterOrder,
  createWaiterOrder,
  createInvoiceForWaiterOrder,
  applyDiscountToWaiterOrder,
  generateWaiterGuestCheckPdf,
  generateWaiterReceiptPdf,
  getDiscounts,
  getModifiers,
  getProductCategories,
  getProductModifiers,
  getWaiterOrderItems,
  getWaiterOrders,
  getWaiterProducts,
  isOpenOrder,
  tableStatusLabel,
  type CartEntry,
  type CartItem,
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
  splitWaiterOrder,
  updateWaiterOrder,
  updateWaiterOrderTip,
} from "../api/waiterApi";
import { useAuth } from "../auth/useAuth";
import { connectLiveUpdates } from "../ws/liveUpdates";

type LoadingState = "idle" | "loading" | "ready" | "error";
type WaiterMode = "DASHBOARD" | "TABLE_PICKER" | "ORDER_BUILDER" | "CHECKOUT" | "ORDER_DETAILS";
type MenuDepartment = "KITCHEN" | "BAR";
type TicketSelection = { type: "existing"; id: number } | { type: "cart"; id: string };

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
  const [floorPlan, setFloorPlan] = useState<FloorPlan | null>(null);
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
  const [productSearchQuery, setProductSearchQuery] = useState("");
  const [pendingProduct, setPendingProduct] = useState<Product | null>(null);
  const [status, setStatus] = useState<LoadingState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

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
          getFloorPlanView(token),
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
      setStatus("ready");
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not load waiter workspace.");
      setStatus("error");
    }
  }, [token]);

  useEffect(() => {
    void loadWaiterData();
  }, [loadWaiterData]);

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
  const modifiersById = useMemo(
    () => new Map(modifiers.map((modifier) => [modifier.id, modifier])),
    [modifiers],
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
        <WaiterHeader />
        <div className="module-placeholder">Loading waiter workspace...</div>
      </section>
    );
  }

  if (status === "error") {
    return (
      <section className="page-stack">
        <WaiterHeader />
        <div className="error-box">{error}</div>
        <button type="button" className="primary-button" onClick={loadWaiterData}>
          Reload
        </button>
      </section>
    );
  }

  return (
    <section className={`waiter-workspace ${isFullscreenMode(mode) ? "pos-builder-mode" : ""}`}>
      {!isFullscreenMode(mode) && <WaiterHeader />}

      {!isFullscreenMode(mode) && notice && <div className="success-box">{notice}</div>}
      {!isFullscreenMode(mode) && error && <div className="error-box">{error}</div>}

      {mode === "DASHBOARD" && (
        <div className="waiter-dashboard-grid">
          <main className="waiter-panel waiter-orders-board">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Open orders</span>
                <h1>Active tables</h1>
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
                  <span>Order #{order.id}</span>
                  <strong>{getOrderTableLabel(order)}</strong>
                  <small>
                    {order.guest_count ?? 0} guests · {order.status}
                  </small>
                  <b>{formatMoney(Number(order.total_amount))}</b>
                </button>
              ))}
              {openOrders.length === 0 && (
                <div className="empty-orders-state">
                  <strong>No open orders</strong>
                  <p>New orders will appear here after a table is selected.</p>
                </div>
              )}
            </div>
          </main>

          <aside className="waiter-panel waiter-action-panel">
            <span className="eyebrow">Actions</span>
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
              Create order
            </button>
            <button type="button" className="pos-action-button" onClick={loadWaiterData}>
              Refresh
            </button>
          </aside>
        </div>
      )}

      {mode === "TABLE_PICKER" && (
        <div className="waiter-flow-grid">
          <main className="waiter-panel waiter-map-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Step 1</span>
                <h1>Select free table</h1>
              </div>
              <button type="button" className="ghost-button" onClick={resetToDashboard}>
                Back
              </button>
            </div>

            <div className="waiter-floor-map">
              {floorPlan ? (
                <div
                  className="waiter-floor-canvas"
                  style={{
                    width: floorPlan.width,
                    height: floorPlan.height,
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
                          setSelectedTable(item.table);
                        }
                      }}
                    >
                      <strong>{item.table?.table_number ?? item.table_id}</strong>
                      <span>{tableStatusLabel(item.table?.status ?? "UNKNOWN")}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="empty-ticket">No active floor plan.</div>
              )}
            </div>
          </main>

          <aside className="waiter-panel waiter-action-panel">
            <span className="eyebrow">Step 2</span>
            <h2>{selectedTable ? `Table ${selectedTable.table_number}` : "No table selected"}</h2>
            <label className="compact-field">
              Guests
              <input
                type="number"
                min={1}
                value={guestCount}
                onChange={(event) => setGuestCount(Math.max(1, Number(event.target.value)))}
              />
            </label>
            <button
              type="button"
              className="pos-action-button primary"
              disabled={!selectedTable}
              onClick={() => {
                setCart([]);
                setMode("ORDER_BUILDER");
                setSelectedCategoryId("ALL");
              }}
            >
              Continue to menu
            </button>
          </aside>
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
                Dishes
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
                All
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
                <div className="module-placeholder">No active products in this section.</div>
              )}
            </div>

          </main>

          <aside className="waiter-panel order-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">TICKET</span>
                <h2>
                  {selectedOrder ? `Order #${selectedOrder.id}` : `Table ${selectedTable.table_number}`}
                </h2>
              </div>
              <strong>{formatMoney(getTicketTotal())}</strong>
            </div>
            <p className="muted">
              Table {selectedTable.table_number} · {guestCount} guests
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
            <div className="functions-menu-wrapper">
              {isFunctionsMenuOpen && (
                <div className="functions-menu">
                  <button
                    type="button"
                    onClick={() => {
                      void splitSelectedBill();
                    }}
                    disabled={!selectedOrder || selectedTicketLine?.type !== "existing" || isSubmitting}
                  >
                    Podziel rachunek
                  </button>
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
                      Delete
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      void changeOrderGuestCount();
                    }}
                    disabled={isSubmitting}
                  >
                    Zmień gości
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIsFunctionsMenuOpen(false);
                      setProductSearchQuery("");
                      setIsProductSearchOpen(true);
                    }}
                  >
                    Szukaj pozycji
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
                <h1>Order #{selectedOrder.id}</h1>
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

  function addInfoToLastItem() {
    const lastItem = [...cart].reverse().find(isCartItem);
    if (!lastItem) {
      return;
    }

    const nextNotes = window.prompt("Info / notes", lastItem.notes ?? "");
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
      const invoiceNip = askForInvoiceNip();
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

  function askForInvoiceNip(): string | null {
    const wantsNip = window.confirm("Czy dodać NIP do rachunku?");
    if (!wantsNip) {
      return "";
    }

    const nip = window.prompt("Wpisz NIP");
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
    if (!token || !selectedOrder || selectedTicketLine?.type !== "existing") {
      setError("Select a sent order item first.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const splitOrder = await splitWaiterOrder(token, selectedOrder.id, [
        selectedTicketLine.id,
      ]);
      setSelectedTicketLine(null);
      setIsFunctionsMenuOpen(false);
      setNotice(`Created split order #${splitOrder.id}.`);
      await loadWaiterData();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not split bill.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function changeOrderGuestCount() {
    const nextGuestCount = window.prompt(
      "Guest count",
      String(selectedOrder?.guest_count ?? guestCount),
    );
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

    const managerPin = window.prompt("Manager PIN");
    if (!managerPin) {
      return null;
    }
    return managerPin;
  }

  async function deleteExistingOrder() {
    if (!token || !selectedOrder) {
      return;
    }

    const managerPin = window.prompt("Manager PIN");
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
                Course {item.course_number} · {item.quantity} x {formatMoney(Number(item.unit_price))}
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
                Course {entry.courseNumber} · {formatMoney(getItemTotal(entry))}
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
            Course {entry.nextCourseNumber}
          </button>
        ),
      )}
      {existingItems.length === 0 && !hasCartItems(cart) && (
        <div className="empty-ticket">Select products to build this order.</div>
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
                  Course {item.course_number} · {item.quantity} x{" "}
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
          Subtotal <strong>{formatMoney(Number(order.subtotal_amount))}</strong>
        </span>
        <span>
          Discount <strong>-{formatMoney(Number(order.discount_amount))}</strong>
        </span>
        <span>
          Tip <strong>{formatMoney(Number(order.tip_amount))}</strong>
        </span>
        <b>
          Total <strong>{formatMoney(Number(order.total_amount))}</strong>
        </b>
      </div>
    </div>
  );
}

function WaiterHeader() {
  return (
    <div className="waiter-header">
      <div>
        <span className="eyebrow">Waiter POS</span>
        <h1>Service panel</h1>
        <p className="muted">Open orders first, then create a new table order from the room map.</p>
      </div>
      <img src="/logo.png" alt="GastroFlow" />
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
            <span className="eyebrow">Item options</span>
            <h2>{product.name}</h2>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Close
          </button>
        </div>

        {requiresSteakInfo(product) && (
          <label className="compact-field">
            Cooking level
            <select
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            >
              <option value="">Select level</option>
              {roastLevels.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </label>
        )}

        <label className="compact-field">
          Info / notes
          <input
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="e.g. no onion"
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
                  <strong>{price > 0 ? `+${formatMoney(price)}` : "Free"}</strong>
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
          Add to check
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
            <span className="eyebrow">System search</span>
            <h2>Szukaj pozycji</h2>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Close
          </button>
        </div>

        <label className="compact-field">
          Product name
          <input
            autoFocus
            value={query}
            placeholder="Start typing..."
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
            <div className="empty-ticket">No matching products.</div>
          )}
          {!query.trim() && (
            <div className="empty-ticket">Type a product name to search.</div>
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
  return mode === "ORDER_BUILDER" || mode === "CHECKOUT";
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
