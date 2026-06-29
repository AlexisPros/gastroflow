import { useEffect, useState } from "react";
import { Check, Clock3, Info, LockKeyhole, Play } from "lucide-react";
import { useAuth } from "../auth/useAuth";
import {
  getActiveSectionTasks,
  startKitchenTask,
  completeKitchenTask,
  getKitchenSections,
  KitchenSectionTask,
} from "../api/kitchenApi";
import { connectLiveUpdates } from "../ws/liveUpdates";
import type { WebSocketMessage } from "../shared/types";
import { getOrderTimingState } from "../shared/orderTiming";

// Audio alert using Web Audio API for soft double chime
const playBarAlertSound = () => {
  try {
    const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
    const osc1 = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    
    osc1.type = "sine";
    osc1.frequency.setValueAtTime(659.25, audioCtx.currentTime); // E5
    osc1.frequency.setValueAtTime(987.77, audioCtx.currentTime + 0.1); // B5
    
    gain.gain.setValueAtTime(0.25, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.4);
    
    osc1.connect(gain);
    gain.connect(audioCtx.destination);
    
    osc1.start();
    osc1.stop(audioCtx.currentTime + 0.4);
  } catch (e) {
    console.error("Failed playing bar alert sound", e);
  }
};

export function BarPage() {
  const { token } = useAuth();
  
  const [tasks, setTasks] = useState<KitchenSectionTask[]>([]);
  const [barSectionId, setBarSectionId] = useState<number | undefined>();
  
  const [toasts, setToasts] = useState<Array<{ id: string; title: string; subtitle: string }>>([]);
  const [infoTaskId, setInfoTaskId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());

  // The bar screen must never fall back to a kitchen section.
  useEffect(() => {
    if (token) {
      getKitchenSections(token)
        .then((data) => {
          const barSec = data.find((s) => s.name.toLowerCase() === "bar");
          if (barSec) {
            setBarSectionId(barSec.id);
            setError(null);
          } else {
            setBarSectionId(undefined);
            setTasks([]);
            setError("Sekcja Bar nie jest skonfigurowana.");
          }
        })
        .catch((err) => {
          setBarSectionId(undefined);
          setTasks([]);
          setError("Błąd pobierania sekcji baru: " + (err.message || err));
        });
    }
  }, [token]);

  // Load bar tasks
  const loadTasks = async () => {
    if (!token || barSectionId === undefined) return [] as KitchenSectionTask[];
    try {
      const activeTasks = await getActiveSectionTasks(token, barSectionId);
      setTasks(activeTasks);
      setError(null);
      return activeTasks;
    } catch (err: any) {
      setError("Błąd pobierania zadań baru: " + (err.message || err));
      return [] as KitchenSectionTask[];
    }
  };

  // Poll time for elapsed timers
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Fetch when barSectionId changes
  useEffect(() => {
    loadTasks();
  }, [token, barSectionId]);

  // WebSocket Live Updates
  useEffect(() => {
    if (!token || barSectionId === undefined) return;

    const cleanup = connectLiveUpdates({
      channel: "bar",
      token: token,
      onMessage: (message: WebSocketMessage) => {
        const refreshEvents = [
          "order_created",
          "qr_order_confirmed",
          "order_items_added",
          "kitchen_task_started",
          "kitchen_task_completed",
          "order_cancelled",
          "bar_order_ready",
        ];

        if (refreshEvents.includes(message.event)) {
          void (async () => {
            const activeTasks = await loadTasks();

            // Alert only if this update actually produced a task for the bar.
            if (
              message.event === "order_created" ||
              message.event === "qr_order_confirmed" ||
              message.event === "order_items_added"
            ) {
              const data = message.data as any;
              const orderId = Number(data.order_id);
              if (!activeTasks.some((task) => task.order_id === orderId)) {
                return;
              }

              playBarAlertSound();
              
              const newToast = {
                id: Math.random().toString(),
                title: "Nowe zamówienie barowe!",
                subtitle: `Stolik ${data.table_number || "Bez stolika"}`,
              };
              setToasts((prev) => [newToast, ...prev]);

              setTimeout(() => {
                setToasts((prev) => prev.filter((t) => t.id !== newToast.id));
              }, 6000);
            }
          })();
        }
      },
    });

    return cleanup;
  }, [token, barSectionId]);

  const handleStartTask = async (taskId: number) => {
    if (!token) return;
    try {
      await startKitchenTask(token, taskId);
      loadTasks();
    } catch (err: any) {
      alert("Błąd rozpoczęcia zadania: " + err.message);
    }
  };

  const handleCompleteTask = async (taskId: number) => {
    if (!token) return;
    try {
      await completeKitchenTask(token, taskId);
      loadTasks();
    } catch (err: any) {
      alert("Błąd zakończenia zadania: " + err.message);
    }
  };

  const getWaitingTimeText = (createdAtStr: string) => {
    const elapsedMs = now - new Date(createdAtStr).getTime();
    const totalSecs = Math.max(0, Math.floor(elapsedMs / 1000));
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const pendingTasks = tasks.filter((t) => t.status === "NEW" || t.status === "PENDING");
  const inProgressTasks = tasks.filter((t) => t.status === "IN_PROGRESS");
  const barTaskOrders = groupBarTasksByOrder(tasks);

  return (
    <section className="page-stack" style={{ padding: "20px" }}>
      {/* Header */}
      <div className="waiter-header" style={{ marginBottom: "12px" }}>
        <div>
          <span className="eyebrow">Moduł Baru</span>
          <h1 style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            Ekran Baru
            <span
              className="status-badge"
              style={{
                fontSize: "0.9rem",
                padding: "4px 12px",
                background: "rgba(18, 168, 98, 0.15)",
                color: "var(--brand-green-dark)",
                borderRadius: "50px",
                fontWeight: 600,
              }}
            >
              Aktywne zamówienia: {tasks.length}
            </span>
          </h1>
        </div>

        <button
          type="button"
          className="ghost-button"
          onClick={loadTasks}
          style={{ padding: "8px 16px", height: "auto" }}
        >
          Odśwież
        </button>
      </div>

      {/* Bar tasks grouped by check */}
      <div className="kitchen-order-board bar-order-board">
        {barTaskOrders.map((orderGroup) => {
          const inProgressCount = orderGroup.tasks.filter(
            (task) => task.status === "IN_PROGRESS",
          ).length;
          const timing = getOrderTimingState(
            orderGroup.createdAt,
            orderGroup.estimatedTime,
            now,
          );

          return (
            <article
              key={orderGroup.orderId}
              className={`kitchen-order-group ${timing.tone}`}
            >
              <header className="kitchen-order-group-header">
                <div>
                  <span className="eyebrow">Zamówienie #{orderGroup.orderId}</span>
                  <h2>Stolik {orderGroup.tableNumber || "Bez stolika"}</h2>
                </div>
                <span
                  className={
                    timing.tone !== "on-time"
                      ? timing.tone
                      : inProgressCount > 0
                        ? "active"
                        : "waiting"
                  }
                >
                  {timing.tone !== "on-time"
                    ? `Opóźnienie ${timing.delayMinutes} min`
                    : inProgressCount > 0
                    ? `W trakcie: ${inProgressCount}`
                    : `Oczekuje: ${orderGroup.tasks.length}`}
                </span>
              </header>

              <div className="kitchen-order-task-list">
                {orderGroup.tasks.map((task) => {
                  const isInProgress = task.status === "IN_PROGRESS";
                  const isBlocked = !isInProgress && !task.can_start;

                  return (
                    <section
                      key={task.id}
                      className={`kitchen-order-task ${
                        isInProgress ? "in-progress" : isBlocked ? "blocked" : "ready"
                      }`}
                    >
                      <div className="kitchen-order-task-meta">
                        <span>{task.quantity}x {task.product_name}</span>
                        <span>Kurs {task.course_number}</span>
                      </div>

                      <div className="kitchen-order-task-title">
                        <h3>{task.step_name || "Przygotowanie"}</h3>
                        {task.step_description && (
                          <button
                            type="button"
                            className="kitchen-task-info-button"
                            aria-label={`Informacje o kroku: ${task.step_name || "Przygotowanie"}`}
                            onClick={() => setInfoTaskId(task.id)}
                          >
                            <Info aria-hidden="true" />
                          </button>
                        )}
                      </div>

                      {task.notes && (
                        <div className="kitchen-task-notes">UWAGA: {task.notes}</div>
                      )}

                      {isBlocked && task.blocked_by_step_name && (
                        <div className="kitchen-task-dependency">
                          <LockKeyhole aria-hidden="true" />
                          <span>Czeka na: {task.blocked_by_step_name}</span>
                        </div>
                      )}

                      <footer className="kitchen-order-task-footer">
                        <span>
                          <Clock3 aria-hidden="true" />
                          {isInProgress && task.started_at
                            ? `W toku ${getWaitingTimeText(task.started_at)}`
                            : task.estimated_time
                              ? `${task.estimated_time} min`
                              : "Bez czasu"}
                        </span>
                        {isInProgress ? (
                          <button
                            type="button"
                            className="kitchen-task-action complete"
                            onClick={() => void handleCompleteTask(task.id)}
                          >
                            <Check aria-hidden="true" />
                            Zakończ
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="kitchen-task-action start"
                            disabled={!task.can_start}
                            onClick={() => void handleStartTask(task.id)}
                          >
                            {isBlocked ? (
                              <LockKeyhole aria-hidden="true" />
                            ) : (
                              <Play aria-hidden="true" />
                            )}
                            {isBlocked
                              ? "Zablokowane"
                              : task.status === "NEW"
                                ? "Przyjmij i rozpocznij"
                                : "Rozpocznij"}
                          </button>
                        )}
                      </footer>
                    </section>
                  );
                })}
              </div>
            </article>
          );
        })}

        {barTaskOrders.length === 0 && (
          <div className="empty-orders-state kitchen-order-board-empty">
            Brak aktywnych zamówień barowych.
          </div>
        )}
      </div>

      {/* Previous column view kept out of the render path while grouped checks are active. */}
      {false && (
      <div
        style={{
          display: "flex",
          gap: "20px",
          overflowX: "auto",
          paddingBottom: "10px",
          minHeight: "calc(100vh - 180px)",
        }}
      >
        {/* Do przygotowania column */}
        <div
          style={{
            flex: 1,
            minWidth: "320px",
            maxWidth: "520px",
            background: "rgba(255, 255, 255, 0.4)",
            backdropFilter: "blur(10px)",
            borderRadius: "12px",
            padding: "16px",
            border: "1px solid rgba(22, 96, 88, 0.1)",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <h2
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
            <span>Do przygotowania</span>
            <span
              style={{
                background: "#edf2f7",
                color: "#4a5568",
                fontSize: "0.8rem",
                padding: "2px 8px",
                borderRadius: "12px",
              }}
            >
              {pendingTasks.length}
            </span>
          </h2>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              overflowY: "auto",
              flexGrow: 1,
            }}
          >
            {pendingTasks.map((task) => (
              <div
                key={task.id}
                className="waiter-panel"
                style={{
                  padding: "16px",
                  borderRadius: "8px",
                  borderLeft: "4px solid #a0aec0",
                  background: "#ffffff",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.02)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "8px",
                  }}
                >
                  <span className="eyebrow" style={{ fontSize: "0.75rem" }}>
                    Stolik {task.table_number || "Bez stolika"} (Zam. #{task.order_id})
                  </span>
                  <span
                    style={{
                      borderRadius: "50px",
                      fontSize: "0.75rem",
                      background: "rgba(0,0,0,0.04)",
                      padding: "2px 6px",
                    }}
                  >
                    {getWaitingTimeText(task.started_at || task.completed_at || new Date().toISOString())}
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

                {!task.can_start && task.blocked_by_step_name && (
                  <div className="kitchen-task-dependency">
                    Czeka na: {task.blocked_by_step_name}
                  </div>
                )}

                <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "12px" }}>
                  <button
                    type="button"
                    className="primary-button"
                    disabled={!task.can_start}
                    onClick={() => handleStartTask(task.id)}
                    style={{
                      padding: "6px 16px",
                      background: "var(--brand-navy)",
                      fontSize: "0.85rem",
                      opacity: task.can_start ? 1 : 0.48,
                      cursor: task.can_start ? "pointer" : "not-allowed",
                    }}
                  >
                    {!task.can_start
                      ? "Zablokowane"
                      : task.status === "NEW"
                        ? "Przyjmij i rozpocznij"
                        : "Rozpocznij"}
                  </button>
                </div>
              </div>
            ))}

            {pendingTasks.length === 0 && (
              <div style={{ textAlign: "center", padding: "30px", color: "#718096", fontSize: "0.9rem" }}>
                Brak napojów do przygotowania.
              </div>
            )}
          </div>
        </div>

        {/* W przygotowaniu column */}
        <div
          style={{
            flex: 1,
            minWidth: "320px",
            maxWidth: "520px",
            background: "rgba(255, 255, 255, 0.4)",
            backdropFilter: "blur(10px)",
            borderRadius: "12px",
            padding: "16px",
            border: "1px solid rgba(22, 96, 88, 0.1)",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <h2
            style={{
              fontSize: "1.1rem",
              fontWeight: 800,
              marginBottom: "12px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              color: "var(--brand-green-dark)",
            }}
          >
            <span>W przygotowaniu</span>
            <span
              style={{
                background: "rgba(18, 168, 98, 0.15)",
                color: "var(--brand-green-dark)",
                fontSize: "0.8rem",
                padding: "2px 8px",
                borderRadius: "12px",
              }}
            >
              {inProgressTasks.length}
            </span>
          </h2>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              overflowY: "auto",
              flexGrow: 1,
            }}
          >
            {inProgressTasks.map((task) => (
              <div
                key={task.id}
                className="waiter-panel"
                style={{
                  padding: "16px",
                  borderRadius: "8px",
                  borderLeft: "4px solid var(--brand-green)",
                  background: "#ffffff",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.02)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "8px",
                  }}
                >
                  <span className="eyebrow" style={{ fontSize: "0.75rem" }}>
                    Stolik {task.table_number || "Bez stolika"} (Zam. #{task.order_id})
                  </span>
                  <span
                    style={{
                      borderRadius: "50px",
                      fontSize: "0.75rem",
                      background: "rgba(18, 168, 98, 0.1)",
                      color: "var(--brand-green-dark)",
                      padding: "2px 6px",
                    }}
                  >
                    {getWaitingTimeText(task.started_at || new Date().toISOString())}
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

                <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "12px" }}>
                  <button
                    type="button"
                    className="primary-button"
                    onClick={() => handleCompleteTask(task.id)}
                    style={{ padding: "6px 16px", background: "var(--brand-green)", fontSize: "0.85rem" }}
                  >
                    Zakończ (Gotowe)
                  </button>
                </div>
              </div>
            ))}

            {inProgressTasks.length === 0 && (
              <div style={{ textAlign: "center", padding: "30px", color: "#718096", fontSize: "0.9rem" }}>
                Brak napojów w trakcie przygotowania.
              </div>
            )}
          </div>
        </div>
      </div>
      )}

      {/* Step Info Modal */}
      {infoTaskId && (() => {
        const info = tasks.find((t) => t.id === infoTaskId);
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

      {/* Toast Overlay for New Bar Orders */}
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
            style={{
              background: "rgba(255, 255, 255, 0.95)",
              backdropFilter: "blur(8px)",
              borderLeft: "5px solid #3182ce",
              boxShadow: "0 10px 25px rgba(0,0,0,0.15)",
              padding: "16px 20px",
              borderRadius: "8px",
              display: "flex",
              flexDirection: "column",
              gap: "4px",
              minWidth: "260px",
              animation: "slideIn 0.3s ease",
            }}
          >
            <strong style={{ color: "var(--brand-navy)", fontSize: "0.95rem" }}>{t.title}</strong>
            <span style={{ fontSize: "0.85rem", color: "#4a5568" }}>{t.subtitle}</span>
          </div>
        ))}
      </div>

      <style>{`
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

type BarTaskOrderGroup = {
  orderId: number;
  tableNumber: string | null;
  createdAt: string;
  estimatedTime: number | null;
  tasks: KitchenSectionTask[];
};

function groupBarTasksByOrder(tasks: KitchenSectionTask[]): BarTaskOrderGroup[] {
  const groups = new Map<number, BarTaskOrderGroup>();

  for (const task of tasks) {
    const group = groups.get(task.order_id) ?? {
      orderId: task.order_id,
      tableNumber: task.table_number,
      createdAt: task.item_created_at || task.order_created_at,
      estimatedTime: task.order_estimated_time,
      tasks: [],
    };
    group.tasks.push(task);
    groups.set(task.order_id, group);
  }

  return Array.from(groups.values()).map((group) => {
    const activeTasks = group.tasks.filter((t) => t.status !== "COMPLETED");
    const oldestItemCreatedAt = activeTasks.length > 0
      ? activeTasks.reduce((oldest, t) => {
          const tTime = new Date(t.item_created_at || t.order_created_at).getTime();
          const oldestTime = new Date(oldest).getTime();
          return tTime < oldestTime ? (t.item_created_at || t.order_created_at) : oldest;
        }, activeTasks[0].item_created_at || activeTasks[0].order_created_at)
      : group.createdAt;

    return {
      ...group,
      createdAt: oldestItemCreatedAt,
      tasks: [...group.tasks].sort((first, second) => {
        if (first.course_number !== second.course_number) {
          return first.course_number - second.course_number;
        }
        if (first.order_item_id !== second.order_item_id) {
          return first.order_item_id - second.order_item_id;
        }
        return (first.step_sequence ?? 0) - (second.step_sequence ?? 0);
      }),
    };
  });
}
