import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/apiClient";
import { getFloorPlanView, type FloorTableView, type RestaurantTable } from "../api/floorPlanApi";
import {
  addItemsToWaiterOrder,
  cancelWaiterOrder,
  createWaiterOrder,
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
  type Modifier,
  type Order,
  type OrderItem,
  type Product,
  type ProductCategory,
  type ProductModifier,
} from "../api/waiterApi";
import { useAuth } from "../auth/useAuth";
import { connectLiveUpdates } from "../ws/liveUpdates";

type LoadingState = "idle" | "loading" | "ready" | "error";
type WaiterMode = "DASHBOARD" | "TABLE_PICKER" | "ORDER_BUILDER" | "ORDER_DETAILS";
type MenuDepartment = "KITCHEN" | "BAR";

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
  const [floorTables, setFloorTables] = useState<FloorTableView[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [orderItems, setOrderItems] = useState<OrderItem[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [modifiers, setModifiers] = useState<Modifier[]>([]);
  const [productModifiers, setProductModifiers] = useState<ProductModifier[]>([]);
  const [mode, setMode] = useState<WaiterMode>("DASHBOARD");
  const [selectedTable, setSelectedTable] = useState<RestaurantTable | null>(null);
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const [guestCount, setGuestCount] = useState(2);
  const [department, setDepartment] = useState<MenuDepartment>("KITCHEN");
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | "ALL">("ALL");
  const [cart, setCart] = useState<CartEntry[]>([]);
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
      ] =
        await Promise.all([
          getFloorPlanView(token),
          getWaiterOrders(token),
          getWaiterOrderItems(token),
          getWaiterProducts(token),
          getProductCategories(token),
          getModifiers(token),
          getProductModifiers(token),
        ]);

      setFloorTables(floorView.tables);
      setOrders(nextOrders);
      setOrderItems(nextOrderItems);
      setProducts(nextProducts.filter((product) => product.is_active));
      setCategories(nextCategories.filter((category) => category.is_active));
      setModifiers(nextModifiers.filter((modifier) => modifier.is_active));
      setProductModifiers(nextProductModifiers.filter((item) => item.is_active));
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
    document.body.classList.toggle("pos-fullscreen", mode === "ORDER_BUILDER");
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
    <section className={`waiter-workspace ${mode === "ORDER_BUILDER" ? "pos-builder-mode" : ""}`}>
      {mode !== "ORDER_BUILDER" && <WaiterHeader />}

      {mode !== "ORDER_BUILDER" && notice && <div className="success-box">{notice}</div>}
      {mode !== "ORDER_BUILDER" && error && <div className="error-box">{error}</div>}

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
                <span className="eyebrow">Table {selectedTable.table_number}</span>
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
              productsById={productsById}
              getModifierLabel={getModifierLabel}
              getItemTotal={getCartItemTotal}
              onIncrement={incrementCartItem}
              onDecrement={decrementCartItem}
            />
          </aside>

          <div className="pos-bottom-bar">
            <button type="button" className="ghost-button" onClick={addCourseSeparator}>
              Separator
            </button>
            <button type="button" className="ghost-button danger" onClick={voidLastEntry}>
              Void
            </button>
            <button type="button" className="ghost-button" onClick={addInfoToLastItem}>
              Info
            </button>
            {selectedOrder && (
              <button type="button" className="ghost-button danger" onClick={deleteExistingOrder}>
                Delete
              </button>
            )}
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
            <button type="button" className="ghost-button" onClick={resetToDashboard}>
              Cancel / Wyjdź
            </button>
          </div>
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

  function voidLastEntry() {
    setCart((items) => items.slice(0, -1));
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
    setError(null);
  }

  function getTicketTotal(): number {
    return Number(selectedOrder?.total_amount ?? 0) + cartTotal;
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
  productsById,
  getModifierLabel,
  getItemTotal,
  onIncrement,
  onDecrement,
}: {
  existingItems: OrderItem[];
  cart: CartEntry[];
  productsById: Map<number, Product>;
  getModifierLabel: (productModifierId: number) => string;
  getItemTotal: (item: CartItem) => number;
  onIncrement: (entryId: string) => void;
  onDecrement: (entryId: string) => void;
}) {
  return (
    <div className="cart-list">
      {existingItems.map((item) => {
        const product = productsById.get(item.product_id);
        return (
          <div key={item.id} className="cart-row locked">
            <div>
              <strong>* {product?.name ?? `Product #${item.product_id}`}</strong>
              <span>
                Course {item.course_number} · {item.quantity} x {formatMoney(Number(item.unit_price))}
              </span>
              {item.notes && <small>{item.notes}</small>}
            </div>
            <b>{formatMoney(Number(item.total_price))}</b>
          </div>
        );
      })}
      {cart.map((entry) =>
        isCartItem(entry) ? (
          <div key={entry.id} className="cart-row">
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
              <button type="button" onClick={() => onDecrement(entry.id)}>
                -
              </button>
              <span>{entry.quantity}</span>
              <button type="button" onClick={() => onIncrement(entry.id)}>
                +
              </button>
            </div>
          </div>
        ) : (
          <div key={entry.id} className="course-separator">
            Course {entry.nextCourseNumber}
          </div>
        ),
      )}
      {existingItems.length === 0 && !hasCartItems(cart) && (
        <div className="empty-ticket">Select products to build this order.</div>
      )}
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

function isCartItem(entry: CartEntry): entry is CartItem {
  return !("type" in entry);
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

function formatMoney(value: number): string {
  return new Intl.NumberFormat("pl-PL", {
    style: "currency",
    currency: "PLN",
  }).format(value);
}
