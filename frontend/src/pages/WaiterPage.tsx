import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/apiClient";
import { getFloorPlanView, type FloorTableView, type RestaurantTable } from "../api/floorPlanApi";
import {
  createWaiterOrder,
  getProductCategories,
  getWaiterOrderItems,
  getWaiterOrders,
  getWaiterProducts,
  isOpenOrder,
  tableStatusLabel,
  type CartItem,
  type Order,
  type OrderItem,
  type Product,
  type ProductCategory,
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
  const [mode, setMode] = useState<WaiterMode>("DASHBOARD");
  const [selectedTable, setSelectedTable] = useState<RestaurantTable | null>(null);
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const [guestCount, setGuestCount] = useState(2);
  const [department, setDepartment] = useState<MenuDepartment>("KITCHEN");
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | "ALL">("ALL");
  const [cart, setCart] = useState<CartItem[]>([]);
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
      const [floorView, nextOrders, nextOrderItems, nextProducts, nextCategories] =
        await Promise.all([
          getFloorPlanView(token),
          getWaiterOrders(token),
          getWaiterOrderItems(token),
          getWaiterProducts(token),
          getProductCategories(token),
        ]);

      setFloorTables(floorView.tables);
      setOrders(nextOrders);
      setOrderItems(nextOrderItems);
      setProducts(nextProducts.filter((product) => product.is_active));
      setCategories(nextCategories.filter((category) => category.is_active));
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
    () => orderItems.filter((item) => item.order_id === selectedOrderId),
    [orderItems, selectedOrderId],
  );

  const productsById = useMemo(
    () => new Map(products.map((product) => [product.id, product])),
    [products],
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
    () => cart.reduce((total, item) => total + Number(item.product.price) * item.quantity, 0),
    [cart],
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
    <section className="waiter-workspace">
      <WaiterHeader />

      {notice && <div className="success-box">{notice}</div>}
      {error && <div className="error-box">{error}</div>}

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
                    setSelectedOrderId(order.id);
                    setMode("ORDER_DETAILS");
                    setNotice(null);
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
        <div className="waiter-builder-grid">
          <main className="waiter-panel waiter-menu-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Order for table {selectedTable.table_number}</span>
                <h1>Menu</h1>
              </div>
              <button type="button" className="ghost-button" onClick={() => setMode("TABLE_PICKER")}>
                Change table
              </button>
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
                  onClick={() => addProduct(product)}
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
                <span className="eyebrow">Ticket</span>
                <h2>Table {selectedTable.table_number}</h2>
              </div>
              <strong>{formatMoney(cartTotal)}</strong>
            </div>
            <p className="muted">{guestCount} guests</p>

            <CartList cart={cart} onAdd={addProduct} onDecrement={decrementProduct} />

            <div className="ticket-actions">
              <button type="button" className="ghost-button" onClick={resetToDashboard}>
                Cancel
              </button>
              <button
                type="button"
                className="primary-button"
                onClick={() => {
                  void submitOrder();
                }}
                disabled={cart.length === 0 || isSubmitting}
              >
                {isSubmitting ? "Sending..." : "Send to kitchen"}
              </button>
            </div>
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

  function addProduct(product: Product) {
    setNotice(null);
    setCart((items) => {
      const existingItem = items.find((item) => item.product.id === product.id);
      if (existingItem) {
        return items.map((item) =>
          item.product.id === product.id
            ? { ...item, quantity: item.quantity + 1 }
            : item,
        );
      }
      return [...items, { product, quantity: 1 }];
    });
  }

  function decrementProduct(productId: number) {
    setCart((items) =>
      items
        .map((item) =>
          item.product.id === productId ? { ...item, quantity: item.quantity - 1 } : item,
        )
        .filter((item) => item.quantity > 0),
    );
  }

  function resetToDashboard() {
    setMode("DASHBOARD");
    setSelectedTable(null);
    setSelectedOrderId(null);
    setCart([]);
    setError(null);
  }

  async function submitOrder() {
    if (!token || !user || !selectedTable) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const order = await createWaiterOrder(token, {
        table_id: selectedTable.id,
        waiter_id: user.id,
        guest_count: guestCount,
        source: "WAITER",
        items: cart.map((item) => ({
          product_id: item.product.id,
          quantity: item.quantity,
          notes: item.notes ?? null,
          product_modifier_ids: [],
        })),
      });
      setNotice(`Order #${order.id} sent to production.`);
      resetToDashboard();
      await loadWaiterData();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not create order.");
    } finally {
      setIsSubmitting(false);
    }
  }
}

function CartList({
  cart,
  onAdd,
  onDecrement,
}: {
  cart: CartItem[];
  onAdd: (product: Product) => void;
  onDecrement: (productId: number) => void;
}) {
  return (
    <div className="cart-list">
      {cart.map((item) => (
        <div key={item.product.id} className="cart-row">
          <div>
            <strong>{item.product.name}</strong>
            <span>{formatMoney(Number(item.product.price))}</span>
          </div>
          <div className="quantity-stepper">
            <button type="button" onClick={() => onDecrement(item.product.id)}>
              -
            </button>
            <span>{item.quantity}</span>
            <button type="button" onClick={() => onAdd(item.product)}>
              +
            </button>
          </div>
        </div>
      ))}
      {cart.length === 0 && (
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
