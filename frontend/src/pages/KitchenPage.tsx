import { useEffect, useState } from "react";
import { useAuth } from "../auth/useAuth";
import {
  getActiveKitchenOrders,
  acceptKitchenOrder,
  completeKitchenOrder,
  getActiveSectionTasks,
  startKitchenTask,
  completeKitchenTask,
  getKitchenSections,
  KitchenOrder,
  KitchenSectionTask,
  KitchenSection,
} from "../api/kitchenApi";
import { connectLiveUpdates } from "../ws/liveUpdates";
import type { WebSocketMessage } from "../shared/types";

// Audio alert using Web Audio API for a nice double-tone chime
const playAlertSound = () => {
  try {
    const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
    const osc1 = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    
    osc1.type = "sine";
    osc1.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5
    osc1.frequency.setValueAtTime(880, audioCtx.currentTime + 0.12); // A5
    
    gain.gain.setValueAtTime(0.35, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.5);
    
    osc1.connect(gain);
    gain.connect(audioCtx.destination);
    
    osc1.start();
    osc1.stop(audioCtx.currentTime + 0.5);
  } catch (e) {
    console.error("Failed playing alert sound", e);
  }
};

export function KitchenPage() {
  const { token, user } = useAuth();
  
  // Role checking
  const isChef = user?.role === "CHEF" || user?.role === "ADMIN" || user?.role === "MANAGER";
  const isWydawka = user?.role === "WYDAWKA" || isChef;
  const isCook = user?.role === "KITCHEN" || isChef;
  
  // Chef tab state: "WYDAWKA" or "MONITOR"
  const [chefTab, setChefTab] = useState<"WYDAWKA" | "MONITOR">(isChef ? "WYDAWKA" : "WYDAWKA");

  // Data State
  const [orders, setOrders] = useState<KitchenOrder[]>([]);
  const [tasks, setTasks] = useState<KitchenSectionTask[]>([]);
  const [sections, setSections] = useState<KitchenSection[]>([]);
  const [allSections, setAllSections] = useState<KitchenSection[]>([]);
  const [selectedSectionId, setSelectedSectionId] = useState<number | undefined>(
    user?.kitchen_section_id ?? undefined
  );
  
  // Notification popups
  const [toasts, setToasts] = useState<Array<{ id: string; title: string; subtitle: string; orderId: number }>>([]);
  const [previewOrderId, setPreviewOrderId] = useState<number | null>(null);
  const [infoTaskId, setInfoTaskId] = useState<number | null>(null);
  
  const [loading, setLoading] = useState(false);
  const [now, setNow] = useState(Date.now());

  const getElapsedTimeText = (createdAtStr: string) => {
    const elapsedMs = now - new Date(createdAtStr).getTime();
    const totalSecs = Math.max(0, Math.floor(elapsedMs / 1000));
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // Fetch sections once
  useEffect(() => {
    if (token) {
      getKitchenSections(token)
        .then((data) => {
          setAllSections(data);
          const kitchenOnly = data.filter((s) => s.name.toLowerCase() !== "bar");
          setSections(kitchenOnly);
          // If cook has no section selected, pick first one
          if (user?.role === "KITCHEN" && !user?.kitchen_section_id && kitchenOnly.length > 0) {
            setSelectedSectionId(kitchenOnly[0].id);
          }
        })
        .catch(console.error);
    }
  }, [token, user]);

  // Fetch data
  const loadData = async () => {
    const loaded = {
      activeOrders: [] as KitchenOrder[],
      activeTasks: [] as KitchenSectionTask[],
    };
    if (!token) return loaded;
    try {
      if (isWydawka) {
        const activeOrders = await getActiveKitchenOrders(token);
        setOrders(activeOrders);
        loaded.activeOrders = activeOrders;
      }
      if (isCook) {
        // Chef gets all tasks (selectedSectionId = undefined), cooks get their section tasks
        const activeTasks = await getActiveSectionTasks(
          token,
          isChef ? selectedSectionId : (user?.kitchen_section_id ?? undefined)
        );
        setTasks(activeTasks);
        loaded.activeTasks = activeTasks;
      }
    } catch (err) {
      console.error("Error loading kitchen data:", err);
    }
    return loaded;
  };

  // Poll time for tickers
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Fetch on token/section/tab change
  useEffect(() => {
    loadData();
  }, [token, selectedSectionId, chefTab]);

  // WebSocket Live Updates
  useEffect(() => {
    if (!token) return;

    const cleanup = connectLiveUpdates({
      channel: "kitchen",
      token: token,
      onMessage: (message: WebSocketMessage) => {
        const refreshEvents = [
          "order_created",
          "qr_order_confirmed",
          "order_items_added",
          "kitchen_task_started",
          "kitchen_task_completed",
          "kitchen_order_accepted",
          "order_cancelled",
          "order_ready",
        ];

        if (refreshEvents.includes(message.event)) {
          void (async () => {
            const loaded = await loadData();
          
            if (
              message.event === "order_created" ||
              message.event === "qr_order_confirmed" ||
              message.event === "order_items_added"
            ) {
              const data = message.data as any;
              const orderId = Number(data.order_id);
              if (!loaded.activeOrders.some((order) => order.id === orderId)) {
                return;
              }

              playAlertSound();
              
              const newToast = {
                id: Math.random().toString(),
                title: message.event === "order_items_added" ? "Nowe pozycje!" : "Nowe zamówienie!",
                subtitle: `Stolik ${data.table_number || "Bez stolika"}`,
                orderId,
              };
              setToasts((prev) => [newToast, ...prev]);
              
              setTimeout(() => {
                setToasts((prev) => prev.filter((t) => t.id !== newToast.id));
              }, 8000);
            }
          })();
        }
      },
    });

    return cleanup;
  }, [token, selectedSectionId, chefTab]);

  // Actions
  const handleAcceptOrder = async (orderId: number) => {
    if (!token) return;
    setLoading(true);
    try {
      await acceptKitchenOrder(token, orderId);
      setPreviewOrderId(null);
      loadData();
    } catch (err: any) {
      alert("Błąd akceptacji: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteOrder = async (orderId: number) => {
    if (!token) return;
    setLoading(true);
    try {
      await completeKitchenOrder(token, orderId);
      loadData();
    } catch (err: any) {
      alert("Błąd wydania: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStartTask = async (taskId: number) => {
    if (!token) return;
    try {
      await startKitchenTask(token, taskId);
      loadData();
    } catch (err: any) {
      alert("Błąd rozpoczęcia: " + err.message);
    }
  };

  const handleCompleteTask = async (taskId: number) => {
    if (!token) return;
    try {
      await completeKitchenTask(token, taskId);
      loadData();
    } catch (err: any) {
      alert("Błąd zakończenia: " + err.message);
    }
  };

  const getSelectedInfoTask = () => {
    if (!infoTaskId) return null;
    const foundInTasks = tasks.find((t) => t.id === infoTaskId);
    if (foundInTasks) {
      return {
        step_name: foundInTasks.step_name,
        step_description: foundInTasks.step_description,
        product_name: foundInTasks.product_name,
        quantity: foundInTasks.quantity,
        table_number: foundInTasks.table_number,
        order_id: foundInTasks.order_id,
      };
    }
    for (const order of orders) {
      for (const item of order.items) {
        const foundInOrderTasks = item.kitchen_tasks.find((t) => t.id === infoTaskId);
        if (foundInOrderTasks) {
          return {
            step_name: foundInOrderTasks.step_name,
            step_description: foundInOrderTasks.step_description,
            product_name: item.product_name,
            quantity: item.quantity,
            table_number: order.table_number,
            order_id: order.id,
          };
        }
      }
    }
    return null;
  };

  const previewOrder = orders.find((o) => o.id === previewOrderId);

  return (
    <section className="page-stack" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "24px" }}>
      
      {/* Header Panel */}
      <div className="waiter-header" style={{ marginBottom: "0px" }}>
        <div>
          <span className="eyebrow">
            {user?.role === "WYDAWKA"
              ? "Ekran Wydawki Kuchennej"
              : user?.role === "CHEF"
              ? "Panel Szefa Kuchni"
              : `Ekran Sekcji: ${sections.find((s) => s.id === selectedSectionId)?.name || "Kuchnia"}`}
          </span>
          <h1 style={{ fontSize: "2.2rem", fontWeight: 800, display: "flex", alignItems: "center", gap: "16px" }}>
            {user?.role === "WYDAWKA"
              ? "Wydawka Kuchni"
              : user?.role === "CHEF"
              ? "Zarządzanie Kuchnią"
              : "Ekran Kuchni"}
            <span
              className="status-badge"
              style={{
                fontSize: "0.85rem",
                padding: "6px 14px",
                background: "rgba(18, 168, 98, 0.15)",
                color: "var(--brand-green-dark)",
                borderRadius: "50px",
                fontWeight: 700,
              }}
            >
              {isWydawka ? `Zamówienia: ${orders.length}` : `Zadania sekcji: ${tasks.length}`}
            </span>
          </h1>
        </div>

        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          {isChef && (
            <div className="category-tabs" style={{ margin: 0 }}>
              <button
                type="button"
                className={chefTab === "WYDAWKA" ? "active" : ""}
                onClick={() => setChefTab("WYDAWKA")}
              >
                Ekran Wydawki
              </button>
              <button
                type="button"
                className={chefTab === "MONITOR" ? "active" : ""}
                onClick={() => setChefTab("MONITOR")}
              >
                Monitor Sekcji (Wszystkie)
              </button>
            </div>
          )}

          {isChef && chefTab === "MONITOR" && (
            <select
              value={selectedSectionId || ""}
              onChange={(e) => setSelectedSectionId(Number(e.target.value) || undefined)}
              style={{
                padding: "8px 16px",
                borderRadius: "8px",
                border: "1px solid #d7dfda",
                background: "#ffffff",
                fontWeight: 600,
                outline: "none",
                cursor: "pointer",
              }}
            >
              <option value="">Wszystkie sekcje</option>
              {sections.map((sec) => (
                <option key={sec.id} value={sec.id}>
                  {sec.name}
                </option>
              ))}
            </select>
          )}

          <button
            type="button"
            className="ghost-button"
            onClick={loadData}
            style={{ padding: "8px 16px", height: "auto" }}
          >
            Odśwież
          </button>
        </div>
      </div>

      {/* -------------------- WYDAWKA VIEW (Tickets Rail) -------------------- */}
      {isWydawka && (!isChef || chefTab === "WYDAWKA") && (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <h2 style={{ fontSize: "1.3rem", fontWeight: 800, color: "var(--brand-navy)", margin: 0 }}>
            Listki Zamówień (Kolejka Wydawki)
          </h2>

          <div
            className="kitchen-tickets-rail"
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "24px",
              paddingBottom: "20px",
              overflowY: "auto",
              maxHeight: "calc(100vh - 200px)",
              alignContent: "flex-start",
            }}
          >
            {orders.map((order) => {
              const hasNew = order.items.some((item) =>
                item.kitchen_tasks.some((t) => t.status === "NEW")
              );
              const totalTasks = order.items.reduce(
                (acc, item) => acc + item.kitchen_tasks.length,
                0
              );
              const completedTasks = order.items.reduce(
                (acc, item) =>
                  acc + item.kitchen_tasks.filter((t) => t.status === "COMPLETED").length,
                0
              );
              const progress = totalTasks > 0 ? (completedTasks / totalTasks) * 100 : 0;
              const isReady = totalTasks > 0 && completedTasks === totalTasks;

              // Extract pending sections
              const pendingSections = new Set<string>();
              order.items.forEach((item) => {
                item.kitchen_tasks.forEach((t) => {
                  if (t.status !== "COMPLETED") {
                    const secName = allSections.find((s) => s.id === t.kitchen_section_id)?.name || "Kuchnia";
                    pendingSections.add(secName);
                  }
                });
              });

              return (
                <div
                  key={order.id}
                  className="kitchen-ticket"
                  style={{
                    width: "320px",
                    background: "#ffffff",
                    border: "1px solid #cbd5e0",
                    borderRadius: "6px",
                    boxShadow: "0 10px 25px rgba(0,0,0,0.05)",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    position: "relative",
                    overflow: "hidden",
                    borderTop: isReady
                      ? "8px solid var(--brand-green)"
                      : hasNew
                      ? "8px dashed #3182ce"
                      : "8px solid #dd6b20",
                  }}
                >
                  {/* Paper slip style header */}
                  <div style={{ padding: "16px 16px 8px 16px", borderBottom: "1px dashed #cbd5e0" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--brand-navy)" }}>
                        Stolik {order.table_number || "Bez stolika"}
                      </span>
                      <span style={{ fontSize: "0.8rem", color: "#718096", fontWeight: 600 }}>
                        Zam. #{order.id}
                      </span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", color: "#4a5568", marginTop: "4px" }}>
                      <span>Kelner: {order.waiter_name || "Brak"}</span>
                      <strong style={{ color: "#3182ce" }}>
                        {getElapsedTimeText(order.created_at)}
                      </strong>
                    </div>
                  </div>

                  {/* Items listing (Always visible without click) */}
                  <div style={{ padding: "12px 16px", flexGrow: 1, display: "flex", flexDirection: "column", gap: "14px" }}>
                    {order.items.map((item) => {
                      return (
                        <div key={item.id} style={{ display: "flex", flexDirection: "column", gap: "6px", background: "rgba(0,0,0,0.02)", padding: "10px", borderRadius: "8px", border: "1px solid rgba(0,0,0,0.04)" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
                            <span style={{ fontSize: "0.95rem", fontWeight: 800, color: "#1a202c" }}>
                              {item.quantity}x {item.product_name}
                            </span>
                            <span style={{ fontSize: "0.75rem", color: "#718096", fontWeight: 600 }}>
                              Danie {item.course_number}
                            </span>
                          </div>

                          {/* Steps List */}
                          <div style={{ display: "flex", flexDirection: "column", gap: "4px", paddingLeft: "4px", marginTop: "2px" }}>
                            {item.kitchen_tasks.map((task) => {
                              const statusText =
                                task.status === "NEW"
                                  ? "Nowy"
                                  : task.status === "PENDING"
                                  ? "Oczekuje"
                                  : task.status === "IN_PROGRESS"
                                  ? "W toku"
                                  : "Gotowe";
                              const statusColor =
                                task.status === "NEW"
                                  ? "#3182ce"
                                  : task.status === "PENDING"
                                  ? "#4a5568"
                                  : task.status === "IN_PROGRESS"
                                  ? "#dd6b20"
                                  : "var(--brand-green-dark)";

                              return (
                                <div key={task.id} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", borderBottom: "1px dashed #edf2f7", paddingBottom: "2px", alignItems: "center" }}>
                                  <span style={{ color: "#4a5568", fontWeight: 500, display: "flex", alignItems: "center", gap: "6px" }}>
                                    {task.step_name || "Przygotowanie"}
                                    {task.step_description && (
                                      <button
                                        type="button"
                                        onClick={() => setInfoTaskId(task.id)}
                                        style={{
                                          padding: "1px 4px",
                                          fontSize: "0.65rem",
                                          background: "rgba(49, 130, 206, 0.1)",
                                          color: "#3182ce",
                                          border: "1px solid rgba(49, 130, 206, 0.2)",
                                          borderRadius: "3px",
                                          fontWeight: 700,
                                          cursor: "pointer",
                                        }}
                                      >
                                        Info
                                      </button>
                                    )}
                                  </span>
                                  <span style={{ color: statusColor, fontWeight: 700, fontSize: "0.8rem" }}>
                                    {statusText}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                          
                          {item.notes && (
                            <span style={{ fontSize: "0.8rem", color: "#dd6b20", fontWeight: 700, marginTop: "2px" }}>
                              UWAGA: {item.notes}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Footer status & Action */}
                  <div style={{ padding: "8px 16px 16px 16px", borderTop: "1px dashed #cbd5e0" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", fontWeight: 700, marginBottom: "8px" }}>
                      <span>Postęp: {completedTasks}/{totalTasks} ({Math.round(progress)}%)</span>
                    </div>

                    {!isReady && !hasNew && pendingSections.size > 0 && (
                      <div style={{ fontSize: "0.75rem", color: "#dd6b20", marginBottom: "8px", fontStyle: "italic" }}>
                        Sekcje w pracy: {Array.from(pendingSections).join(", ")}
                      </div>
                    )}

                    {hasNew ? (
                      <button
                        type="button"
                        className="primary-button"
                        onClick={() => handleAcceptOrder(order.id)}
                        disabled={loading}
                        style={{ width: "100%", background: "#3182ce", padding: "8px", fontSize: "0.85rem" }}
                      >
                        Przyjmij zamówienie
                      </button>
                    ) : isReady ? (
                      <button
                        type="button"
                        className="primary-button"
                        onClick={() => handleCompleteOrder(order.id)}
                        disabled={loading}
                        style={{
                          width: "100%",
                          background: "var(--brand-green)",
                          animation: "pulse 2s infinite",
                          padding: "8px",
                          fontSize: "0.85rem",
                        }}
                      >
                        Wydaj kelnerowi
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="ghost-button"
                        disabled
                        style={{
                          width: "100%",
                          color: "#dd6b20",
                          background: "#fffaf0",
                          borderColor: "#feebc8",
                          cursor: "not-allowed",
                          padding: "8px",
                          fontSize: "0.85rem",
                        }}
                      >
                        W trakcie przygotowania
                      </button>
                    )}
                  </div>
                </div>
              );
            })}

            {orders.length === 0 && (
              <div className="empty-orders-state" style={{ width: "100%", padding: "40px" }}>
                Brak aktywnego biletu na wydawce.
              </div>
            )}
          </div>
        </div>
      )}

      {/* -------------------- SECTION COOK VIEW (PENDING vs IN_PROGRESS) -------------------- */}
      {isCook && (!isChef || chefTab === "MONITOR") && (
        <div
          style={{
            display: "flex",
            gap: "20px",
            overflowX: "auto",
            paddingBottom: "10px",
            minHeight: "calc(100vh - 180px)",
          }}
        >
          {/* Chef combined monitor vs Cook section columns */}
          {isChef && selectedSectionId === undefined ? (
            // Chef combined tasks list
            ["PENDING", "IN_PROGRESS"].map((statusGroup) => {
              const groupTasks = tasks.filter((t) => t.status === statusGroup);
              const isPendingCol = statusGroup === "PENDING";

              return (
                <div
                  key={statusGroup}
                  style={{
                    flex: 1,
                    minWidth: "350px",
                    background: "rgba(255, 255, 255, 0.4)",
                    backdropFilter: "blur(10px)",
                    borderRadius: "12px",
                    padding: "16px",
                    border: "1px solid rgba(22, 96, 88, 0.1)",
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <h3
                    style={{
                      fontSize: "1.1rem",
                      fontWeight: 800,
                      marginBottom: "12px",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      color: "var(--brand-navy)",
                    }}
                  >
                    <span>{isPendingCol ? "Wszystkie Oczekujące Zadania" : "Zadania w Toku Przygotowania"}</span>
                    <span
                      style={{
                        background: isPendingCol ? "#edf2f7" : "rgba(18, 168, 98, 0.15)",
                        color: isPendingCol ? "#4a5568" : "var(--brand-green-dark)",
                        fontSize: "0.8rem",
                        padding: "2px 8px",
                        borderRadius: "12px",
                      }}
                    >
                      {groupTasks.length}
                    </span>
                  </h3>

                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "12px",
                      overflowY: "auto",
                      flexGrow: 1,
                    }}
                  >
                    {groupTasks.map((task) => {
                      const elapsedMs = now - new Date(task.started_at || new Date().toISOString()).getTime();
                      const waitTime = Math.max(0, Math.floor(elapsedMs / 1000 / 60));

                      return (
                        <div
                          key={task.id}
                          className="waiter-panel"
                          style={{
                            padding: "16px",
                            borderRadius: "8px",
                            borderLeft: isPendingCol ? "4px solid #a0aec0" : "4px solid var(--brand-green)",
                            background: "#ffffff",
                            boxShadow: "0 4px 12px rgba(0,0,0,0.02)",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                            <span className="eyebrow" style={{ fontSize: "0.75rem" }}>
                              Stolik {task.table_number || "Bez stolika"} (Zam. #{task.order_id})
                            </span>
                            
                            <span
                              className="status-badge"
                              style={{
                                background: "rgba(22, 96, 88, 0.1)",
                                color: "var(--brand-navy)",
                                fontSize: "0.7rem",
                                fontWeight: 700,
                              }}
                            >
                              Danie {task.course_number}
                            </span>
                          </div>

                          <h3 style={{ margin: "0 0 4px 0", fontSize: "1.2rem", fontWeight: 800, color: "var(--brand-navy)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                            <span>{task.step_name || "Przygotowanie"}</span>
                            {task.step_description && (
                              <button
                                type="button"
                                onClick={() => setInfoTaskId(task.id)}
                                style={{
                                  padding: "4px 8px",
                                  fontSize: "0.75rem",
                                  background: "rgba(49, 130, 206, 0.1)",
                                  color: "#3182ce",
                                  border: "1px solid rgba(49, 130, 206, 0.2)",
                                  borderRadius: "4px",
                                  fontWeight: 700,
                                  cursor: "pointer",
                                }}
                              >
                                Info
                              </button>
                            )}
                          </h3>
                          <div style={{ fontSize: "0.9rem", color: "#4a5568", marginBottom: "8px", fontWeight: 600 }}>
                            Dla: {task.quantity}x {task.product_name}
                          </div>

                          {task.notes && (
                            <div
                              style={{
                                background: "#fffaf0",
                                border: "1px solid #feebc8",
                                padding: "8px",
                                borderRadius: "6px",
                                fontSize: "0.85rem",
                                color: "#dd6b20",
                                fontWeight: 700,
                                marginBottom: "10px",
                              }}
                            >
                              UWAGA: {task.notes}
                            </div>
                          )}

                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "12px" }}>
                            <div style={{ fontSize: "0.8rem", color: "#718096" }}>
                              {task.estimated_time && <span>Czas: {task.estimated_time} min</span>}
                              {!isPendingCol && <span style={{ marginLeft: "8px", color: "var(--brand-green-dark)" }}>W toku: {waitTime}m</span>}
                            </div>
                            
                            {isPendingCol ? (
                              <button
                                type="button"
                                className="primary-button"
                                onClick={() => handleStartTask(task.id)}
                                style={{ padding: "6px 14px", background: "var(--brand-navy)", fontSize: "0.8rem" }}
                              >
                                Rozpocznij
                              </button>
                            ) : (
                              <button
                                type="button"
                                className="primary-button"
                                onClick={() => handleCompleteTask(task.id)}
                                style={{ padding: "6px 14px", background: "var(--brand-green)", fontSize: "0.8rem" }}
                              >
                                Zakończ
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}

                    {groupTasks.length === 0 && (
                      <div style={{ textAlign: "center", padding: "30px", color: "#718096", fontSize: "0.9rem" }}>
                        Brak zadań w toku.
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          ) : (
            // Regular cook view columns (PENDING & IN_PROGRESS only)
            ["PENDING", "IN_PROGRESS"].map((statusGroup) => {
              const groupTasks = tasks.filter((t) => t.status === statusGroup);
              const isPendingCol = statusGroup === "PENDING";

              return (
                <div
                  key={statusGroup}
                  style={{
                    flex: 1,
                    minWidth: "300px",
                    background: "rgba(255, 255, 255, 0.4)",
                    backdropFilter: "blur(10px)",
                    borderRadius: "12px",
                    padding: "16px",
                    border: "1px solid rgba(22, 96, 88, 0.1)",
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <h3
                    style={{
                      fontSize: "1.05rem",
                      fontWeight: 800,
                      marginBottom: "12px",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      color: isPendingCol ? "#2d3748" : "var(--brand-green-dark)",
                    }}
                  >
                    <span>{isPendingCol ? "Oczekujące" : "W trakcie"}</span>
                    <span style={{
                      background: isPendingCol ? "#edf2f7" : "rgba(18, 168, 98, 0.15)",
                      color: isPendingCol ? "#4a5568" : "var(--brand-green-dark)",
                      padding: "2px 8px",
                      borderRadius: "12px",
                      fontSize: "0.8rem"
                    }}>
                      {groupTasks.length}
                    </span>
                  </h3>

                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "12px",
                      overflowY: "auto",
                      flexGrow: 1,
                    }}
                  >
                    {groupTasks.map((task) => (
                      <div
                        key={task.id}
                        className="waiter-panel"
                        style={{
                          padding: "16px",
                          borderRadius: "8px",
                          borderLeft: isPendingCol ? "4px solid #a0aec0" : "4px solid var(--brand-green)",
                          background: "#ffffff",
                          boxShadow: "0 4px 12px rgba(0,0,0,0.02)",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                          <span className="eyebrow" style={{ fontSize: "0.75rem" }}>
                            Stolik {task.table_number || "Bez stolika"} (Zam. #{task.order_id})
                          </span>
                          <span className="muted" style={{ fontSize: "0.8rem" }}>
                            Danie {task.course_number}
                          </span>
                        </div>

                        <h3 style={{ margin: "0 0 4px 0", fontSize: "1.2rem", fontWeight: 800, color: "var(--brand-navy)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <span>{task.step_name || "Przygotowanie"}</span>
                          {task.step_description && (
                            <button
                              type="button"
                              onClick={() => setInfoTaskId(task.id)}
                              style={{
                                padding: "4px 8px",
                                fontSize: "0.75rem",
                                background: "rgba(49, 130, 206, 0.1)",
                                color: "#3182ce",
                                border: "1px solid rgba(49, 130, 206, 0.2)",
                                borderRadius: "4px",
                                fontWeight: 700,
                                cursor: "pointer",
                              }}
                            >
                              Info
                            </button>
                          )}
                        </h3>
                        <div style={{ fontSize: "0.95rem", color: "#4a5568", marginBottom: "8px", fontWeight: 600 }}>
                          Dla: {task.quantity}x {task.product_name}
                        </div>

                        {task.notes && (
                          <div
                            style={{
                              background: "#fffaf0",
                              border: "1px solid #feebc8",
                              padding: "8px",
                              borderRadius: "6px",
                              fontSize: "0.85rem",
                              color: "#dd6b20",
                              fontWeight: 700,
                              marginBottom: "10px",
                            }}
                          >
                            UWAGA: {task.notes}
                          </div>
                        )}

                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "12px" }}>
                          <div style={{ fontSize: "0.8rem", color: "#718096" }}>
                            {task.estimated_time && <span>Czas: {task.estimated_time} min</span>}
                          </div>
                          
                          {isPendingCol ? (
                            <button
                              type="button"
                              className="primary-button"
                              onClick={() => handleStartTask(task.id)}
                              style={{ padding: "6px 14px", background: "var(--brand-navy)", fontSize: "0.8rem" }}
                            >
                              Rozpocznij
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="primary-button"
                              onClick={() => handleCompleteTask(task.id)}
                              style={{ padding: "6px 14px", background: "var(--brand-green)", fontSize: "0.8rem" }}
                            >
                              Zakończ
                            </button>
                          )}
                        </div>
                      </div>
                    ))}

                    {groupTasks.length === 0 && (
                      <div style={{ textAlign: "center", padding: "30px", color: "#718096", fontSize: "0.9rem" }}>
                        Brak zadań w toku.
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Toast Overlay for New Orders */}
      <div
        style={{
          position: "fixed",
          top: "20px",
          right: "20px",
          zIndex: 9999,
          display: "flex",
          flexDirection: "column",
          gap: "10px",
        }}
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            onClick={() => setPreviewOrderId(t.orderId)}
            style={{
              background: "rgba(255, 255, 255, 0.95)",
              backdropFilter: "blur(8px)",
              borderLeft: "5px solid var(--brand-green)",
              boxShadow: "0 10px 25px rgba(0,0,0,0.15)",
              padding: "16px 20px",
              borderRadius: "8px",
              cursor: "pointer",
              display: "flex",
              flexDirection: "column",
              gap: "4px",
              minWidth: "280px",
              animation: "slideIn 0.3s ease",
            }}
          >
            <strong style={{ color: "var(--brand-navy)", fontSize: "0.95rem" }}>{t.title}</strong>
            <span style={{ fontSize: "0.85rem", color: "#4a5568" }}>{t.subtitle}</span>
            <span style={{ fontSize: "0.75rem", color: "var(--brand-green-dark)", fontWeight: 600 }}>
              Kliknij, aby otworzyć podgląd i potwierdzić
            </span>
          </div>
        ))}
      </div>

      {/* Preview Order Modal (For Acceptance Flow) */}
      {previewOrderId && previewOrder && (
        <div className="modal-backdrop" style={{ zIndex: 9900 }}>
          <div className="product-options-modal" style={{ maxWidth: "500px", width: "100%", padding: "24px" }}>
            <div className="modal-header" style={{ marginBottom: "16px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0, fontSize: "1.3rem" }}>
                Zatwierdzenie zamówienia: Stolik {previewOrder.table_number || "Bez stolika"}
              </h3>
              <button
                type="button"
                className="ghost-button"
                onClick={() => setPreviewOrderId(null)}
                style={{ border: "none", background: "none", fontSize: "1.2rem", cursor: "pointer" }}
              >
                ✕
              </button>
            </div>
            
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: "20px" }}>
              {previewOrder.items.map((item) => (
                <div
                  key={item.id}
                  style={{
                    padding: "12px",
                    background: "rgba(0,0,0,0.02)",
                    borderRadius: "6px",
                    border: "1px solid rgba(0,0,0,0.04)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 700 }}>
                    <span>{item.quantity}x {item.product_name}</span>
                    <span className="muted" style={{ fontWeight: 400, fontSize: "0.8rem" }}>
                      Danie {item.course_number}
                    </span>
                  </div>
                  {item.notes && (
                    <div style={{ color: "#dd6b20", fontSize: "0.85rem", marginTop: "4px", fontWeight: 600 }}>
                      Uwaga: {item.notes}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <button
                type="button"
                className="ghost-button"
                onClick={() => setPreviewOrderId(null)}
                style={{ background: "#ffffff", border: "1px solid #718096", color: "#2d3748" }}
              >
                Zamknij (Anuluj)
              </button>
              <button
                type="button"
                className="primary-button"
                onClick={() => handleAcceptOrder(previewOrder.id)}
                style={{ background: "var(--brand-green)" }}
              >
                Zatwierdź i Rozpocznij
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Step Info Modal */}
      {infoTaskId && (() => {
        const info = getSelectedInfoTask();
        if (!info) return null;
        return (
          <div 
            className="modal-backdrop" 
            style={{ zIndex: 9950 }}
            onClick={() => setInfoTaskId(null)}
          >
            <div 
              className="product-options-modal" 
              style={{ maxWidth: "450px", width: "100%", padding: "24px" }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="modal-header" style={{ marginBottom: "16px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, fontSize: "1.3rem", color: "var(--brand-navy)", fontWeight: 800 }}>
                  {info.step_name || "Szczegóły kroku"}
                </h3>
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => setInfoTaskId(null)}
                  style={{ border: "none", background: "none", fontSize: "1.2rem", cursor: "pointer", padding: "4px" }}
                >
                  ✕
                </button>
              </div>
              
              <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "20px" }}>
                <div style={{ fontSize: "0.95rem", color: "#4a5568", borderBottom: "1px solid #edf2f7", paddingBottom: "12px" }}>
                  <strong>Produkt:</strong> {info.quantity}x {info.product_name}
                  <br />
                  <strong>Stolik:</strong> {info.table_number || "Bez stolika"} (Zam. #{info.order_id})
                </div>
                
                <div style={{ padding: "16px", background: "rgba(0,0,0,0.02)", borderRadius: "8px", border: "1px solid rgba(0,0,0,0.04)" }}>
                  <strong style={{ display: "block", marginBottom: "6px", color: "var(--brand-navy)" }}>Opis przygotowania:</strong>
                  <p style={{ margin: 0, fontSize: "0.95rem", color: "#2d3748", lineHeight: "1.5", whiteSpace: "pre-line" }}>
                    {info.step_description || "Brak opisu dla tego kroku."}
                  </p>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => setInfoTaskId(null)}
                  style={{ background: "var(--brand-navy)", padding: "8px 24px" }}
                >
                  Zamknij
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* CSS Injection */}
      <style>{`
        @keyframes pulse {
          0%, 100% {
            box-shadow: 0 0 0 0 rgba(18, 168, 98, 0.4);
          }
          50% {
            box-shadow: 0 0 0 10px rgba(18, 168, 98, 0);
          }
        }
        @keyframes slideIn {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
      `}</style>
    </section>
  );
}
