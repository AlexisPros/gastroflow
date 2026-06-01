import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/apiClient";
import {
  getFloorPlanView,
  type FloorPlan,
  type FloorTableView,
  type RestaurantTableStatus,
} from "../api/floorPlanApi";
import { useAuth } from "../auth/useAuth";
import { connectLiveUpdates } from "../ws/liveUpdates";

type LoadingState = "idle" | "loading" | "ready" | "error";

const statusLabels: Record<string, string> = {
  FREE: "Free",
  PENDING_ORDER: "Pending QR",
  OCCUPIED: "Occupied",
  RESERVED: "Reserved",
};

export function FloorPlanPage() {
  const { token } = useAuth();
  const [floorPlan, setFloorPlan] = useState<FloorPlan | null>(null);
  const [tables, setTables] = useState<FloorTableView[]>([]);
  const [selectedTableId, setSelectedTableId] = useState<number | null>(null);
  const [status, setStatus] = useState<LoadingState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState("disconnected");
  const [lastEvent, setLastEvent] = useState<string | null>(null);

  const loadFloorPlan = useCallback(async () => {
    if (!token) {
      return;
    }

    setStatus((current) => (current === "ready" ? current : "loading"));
    setError(null);

    try {
      const data = await getFloorPlanView(token);
      setFloorPlan(data.floorPlan);
      setTables(data.tables);
      setStatus("ready");
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not load floor plan.");
      setStatus("error");
    }
  }, [token]);

  useEffect(() => {
    void loadFloorPlan();
  }, [loadFloorPlan]);

  useEffect(() => {
    if (!token) {
      return;
    }

    return connectLiveUpdates({
      channel: "floor",
      token,
      onStatusChange: setWsStatus,
      onMessage: (message) => {
        setLastEvent(message.event);
        if (message.event !== "connected") {
          void loadFloorPlan();
        }
      },
    });
  }, [loadFloorPlan, token]);

  const selectedTable = useMemo(
    () => tables.find((item) => item.table_id === selectedTableId) ?? null,
    [selectedTableId, tables],
  );

  const counts = useMemo(() => {
    return tables.reduce(
      (acc, item) => {
        const tableStatus = item.table?.status ?? "UNKNOWN";
        acc.total += 1;
        acc[tableStatus] = (acc[tableStatus] ?? 0) + 1;
        return acc;
      },
      { total: 0 } as Record<string, number>,
    );
  }, [tables]);

  if (status === "loading" || status === "idle") {
    return (
      <section className="page-stack">
        <FloorHeader wsStatus={wsStatus} lastEvent={lastEvent} />
        <div className="module-placeholder">Loading floor plan...</div>
      </section>
    );
  }

  if (status === "error") {
    return (
      <section className="page-stack">
        <FloorHeader wsStatus={wsStatus} lastEvent={lastEvent} />
        <div className="error-box">{error}</div>
        <button type="button" className="primary-button" onClick={loadFloorPlan}>
          Reload
        </button>
      </section>
    );
  }

  return (
    <section className="page-stack">
      <FloorHeader
        floorPlan={floorPlan}
        wsStatus={wsStatus}
        lastEvent={lastEvent}
        onReload={loadFloorPlan}
      />

      <div className="floor-layout">
        <div className="floor-map-panel">
          <div className="floor-toolbar">
            <StatusBadge label="Free" value={counts.FREE ?? 0} status="FREE" />
            <StatusBadge
              label="Pending"
              value={counts.PENDING_ORDER ?? 0}
              status="PENDING_ORDER"
            />
            <StatusBadge
              label="Occupied"
              value={counts.OCCUPIED ?? 0}
              status="OCCUPIED"
            />
            <StatusBadge
              label="Reserved"
              value={counts.RESERVED ?? 0}
              status="RESERVED"
            />
          </div>

          {floorPlan ? (
            <div className="floor-map-scroll">
              <div
                className="floor-map"
                style={{
                  width: floorPlan.width,
                  height: floorPlan.height,
                  backgroundImage: floorPlan.background_image_url
                    ? `url(${floorPlan.background_image_url})`
                    : undefined,
                }}
              >
                {tables.map((item) => (
                  <FloorTableButton
                    key={item.id}
                    item={item}
                    isSelected={selectedTableId === item.table_id}
                    onSelect={() => setSelectedTableId(item.table_id)}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="module-placeholder">No active floor plan.</div>
          )}
        </div>

        <aside className="floor-details-panel">
          <h2>Table details</h2>
          {selectedTable ? (
            <TableDetails item={selectedTable} />
          ) : (
            <p className="muted">Select a table on the map.</p>
          )}
        </aside>
      </div>
    </section>
  );
}

function FloorHeader({
  floorPlan,
  wsStatus,
  lastEvent,
  onReload,
}: {
  floorPlan?: FloorPlan | null;
  wsStatus: string;
  lastEvent: string | null;
  onReload?: () => void;
}) {
  return (
    <div className="floor-header">
      <div>
        <span className="eyebrow">Floor plan</span>
        <h1>{floorPlan?.name ?? "Room map"}</h1>
        <p className="muted">
          Live table status preview for waiter and manager workstations.
        </p>
      </div>
      <div className="floor-header-actions">
        <span className={`ws-pill ${wsStatus}`}>{wsStatus}</span>
        {lastEvent && <span className="event-pill">{lastEvent}</span>}
        {onReload && (
          <button type="button" className="ghost-button" onClick={onReload}>
            Reload
          </button>
        )}
      </div>
    </div>
  );
}

function StatusBadge({
  label,
  value,
  status,
}: {
  label: string;
  value: number;
  status: RestaurantTableStatus;
}) {
  return (
    <div className={`status-badge ${statusClass(status)}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function FloorTableButton({
  item,
  isSelected,
  onSelect,
}: {
  item: FloorTableView;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const tableStatus = item.table?.status ?? "UNKNOWN";
  const shapeClass = item.shape === "CIRCLE" ? "circle" : "rectangle";

  return (
    <button
      type="button"
      className={`floor-table ${shapeClass} ${statusClass(tableStatus)} ${
        isSelected ? "selected" : ""
      }`}
      style={{
        left: Number(item.x),
        top: Number(item.y),
        width: Number(item.width),
        height: Number(item.height),
        transform: `rotate(${Number(item.rotation)}deg)`,
      }}
      onClick={onSelect}
    >
      <strong>{item.table?.table_number ?? `#${item.table_id}`}</strong>
      <span>{statusLabels[tableStatus] ?? tableStatus}</span>
    </button>
  );
}

function TableDetails({ item }: { item: FloorTableView }) {
  const table = item.table;

  return (
    <div className="table-details">
      <div>
        <span className="detail-label">Table</span>
        <strong>{table?.table_number ?? item.table_id}</strong>
      </div>
      <div>
        <span className="detail-label">Status</span>
        <strong>{statusLabels[table?.status ?? "UNKNOWN"] ?? table?.status}</strong>
      </div>
      <div>
        <span className="detail-label">Guests</span>
        <strong>{table?.current_guests ?? 0}</strong>
      </div>
      <div>
        <span className="detail-label">Position</span>
        <strong>
          {item.x}, {item.y}
        </strong>
      </div>
      <div>
        <span className="detail-label">Size</span>
        <strong>
          {item.width} x {item.height}
        </strong>
      </div>
      {table?.qr_code_url && (
        <a href={table.qr_code_url} target="_blank" rel="noreferrer">
          Open QR URL
        </a>
      )}
    </div>
  );
}

function statusClass(status: RestaurantTableStatus): string {
  return `status-${status.toLowerCase().replaceAll("_", "-")}`;
}
