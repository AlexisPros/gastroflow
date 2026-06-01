import { MouseEvent, useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/apiClient";
import {
  createRestaurantTableOnFloorPlan,
  getFloorPlanView,
  updateFloorPlanTablePosition,
  type FloorPlan,
  type FloorPlanTablePositionInput,
  type FloorTableView,
  type RestaurantTableStatus,
} from "../api/floorPlanApi";
import { useAuth } from "../auth/useAuth";
import { connectLiveUpdates } from "../ws/liveUpdates";

type LoadingState = "idle" | "loading" | "ready" | "error";
type EditorTool =
  | "SELECT"
  | "TABLE_RECTANGLE"
  | "TABLE_CIRCLE"
  | "DECOR_RECTANGLE"
  | "DECOR_CIRCLE";
type Selection =
  | { type: "TABLE"; id: number }
  | { type: "DECOR"; id: string }
  | null;
type DecorObject = {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  shape: "RECTANGLE" | "CIRCLE";
};

const statusLabels: Record<string, string> = {
  FREE: "Free",
  PENDING_ORDER: "Pending QR",
  OCCUPIED: "Occupied",
  RESERVED: "Reserved",
};
const DECOR_STORAGE_KEY = "gastroflow.floor.decorations";

export function FloorPlanPage() {
  const { token, user } = useAuth();
  const [floorPlan, setFloorPlan] = useState<FloorPlan | null>(null);
  const [tables, setTables] = useState<FloorTableView[]>([]);
  const [decorObjects, setDecorObjects] = useState<DecorObject[]>(() =>
    loadDecorObjects(),
  );
  const [selection, setSelection] = useState<Selection>(null);
  const [editorTool, setEditorTool] = useState<EditorTool>("SELECT");
  const [newTableNumber, setNewTableNumber] = useState("");
  const [draftPosition, setDraftPosition] =
    useState<FloorPlanTablePositionInput | null>(null);
  const [status, setStatus] = useState<LoadingState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [wsStatus, setWsStatus] = useState("disconnected");
  const [lastEvent, setLastEvent] = useState<string | null>(null);
  const canEdit = user?.role === "ADMIN" || user?.role === "MANAGER";

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
    saveDecorObjects(decorObjects);
  }, [decorObjects]);

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

  const selectedTable = useMemo(() => {
    if (selection?.type !== "TABLE") {
      return null;
    }
    return tables.find((item) => item.id === selection.id) ?? null;
  }, [selection, tables]);

  const selectedDecor = useMemo(() => {
    if (selection?.type !== "DECOR") {
      return null;
    }
    return decorObjects.find((item) => item.id === selection.id) ?? null;
  }, [decorObjects, selection]);

  useEffect(() => {
    if (selectedTable) {
      setDraftPosition({
        x: Number(selectedTable.x),
        y: Number(selectedTable.y),
        width: Number(selectedTable.width),
        height: Number(selectedTable.height),
        rotation: Number(selectedTable.rotation),
        shape: selectedTable.shape === "CIRCLE" ? "CIRCLE" : "RECTANGLE",
      });
      return;
    }

    if (selectedDecor) {
      setDraftPosition({
        x: selectedDecor.x,
        y: selectedDecor.y,
        width: selectedDecor.width,
        height: selectedDecor.height,
        rotation: selectedDecor.rotation,
        shape: selectedDecor.shape,
      });
      return;
    }

    setDraftPosition(null);
  }, [selectedDecor, selectedTable]);

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
                onClick={(event) => {
                  void handleMapClick(event);
                }}
              >
                {decorObjects.map((item) => (
                  <DecorObjectView
                    key={item.id}
                    item={item}
                    isSelected={selection?.type === "DECOR" && selection.id === item.id}
                    onSelect={() => setSelection({ type: "DECOR", id: item.id })}
                  />
                ))}
                {tables.map((item) => (
                  <FloorTableButton
                    key={item.id}
                    item={item}
                    isSelected={selection?.type === "TABLE" && selection.id === item.id}
                    onSelect={() => setSelection({ type: "TABLE", id: item.id })}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="module-placeholder">No active floor plan.</div>
          )}
        </div>

        <aside className="floor-details-panel">
          {canEdit && (
            <EditorPanel
              tool={editorTool}
              tableNumber={newTableNumber}
              error={editorError}
              onToolChange={setEditorTool}
              onTableNumberChange={setNewTableNumber}
            />
          )}

          <h2>{selectedDecor ? "Object details" : "Table details"}</h2>
          {selectedTable && <TableDetails item={selectedTable} />}
          {selectedDecor && <DecorDetails item={selectedDecor} />}
          {!selectedTable && !selectedDecor && (
            <p className="muted">Select an object on the map.</p>
          )}
          {canEdit && draftPosition && (
            <PositionEditor
              position={draftPosition}
              isSaving={isSaving}
              selection={selection}
              onChange={setDraftPosition}
              onSave={() => {
                void saveSelectedPosition();
              }}
              onDeleteDecor={deleteSelectedDecor}
            />
          )}
        </aside>
      </div>
    </section>
  );

  async function handleMapClick(event: MouseEvent<HTMLDivElement>) {
    if (!floorPlan || !canEdit || editorTool === "SELECT") {
      return;
    }

    const target = event.target as HTMLElement;
    if (target.closest(".floor-table") || target.closest(".decor-object")) {
      return;
    }

    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.round(event.clientX - rect.left - 45));
    const y = Math.max(0, Math.round(event.clientY - rect.top - 35));

    if (editorTool === "TABLE_RECTANGLE" || editorTool === "TABLE_CIRCLE") {
      await createTableAtPosition({
        x,
        y,
        shape: editorTool === "TABLE_CIRCLE" ? "CIRCLE" : "RECTANGLE",
      });
      return;
    }

    setDecorObjects((items) => [
      ...items,
      {
        id: crypto.randomUUID(),
        x,
        y,
        width: editorTool === "DECOR_CIRCLE" ? 80 : 140,
        height: editorTool === "DECOR_CIRCLE" ? 80 : 36,
        rotation: 0,
        shape: editorTool === "DECOR_CIRCLE" ? "CIRCLE" : "RECTANGLE",
      },
    ]);
  }

  async function createTableAtPosition({
    x,
    y,
    shape,
  }: {
    x: number;
    y: number;
    shape: "RECTANGLE" | "CIRCLE";
  }) {
    if (!token || !floorPlan) {
      return;
    }

    if (!newTableNumber.trim()) {
      setEditorError("Enter table number before placing a table.");
      return;
    }

    setIsSaving(true);
    setEditorError(null);
    try {
      await createRestaurantTableOnFloorPlan(token, floorPlan.id, {
        table_number: newTableNumber.trim(),
        current_guests: null,
        is_active: true,
        position: {
          x,
          y,
          width: shape === "CIRCLE" ? 90 : 120,
          height: shape === "CIRCLE" ? 90 : 78,
          rotation: 0,
          shape,
        },
      });
      setNewTableNumber("");
      await loadFloorPlan();
    } catch (exc) {
      setEditorError(exc instanceof ApiError ? exc.message : "Could not create table.");
    } finally {
      setIsSaving(false);
    }
  }

  async function saveSelectedPosition() {
    if (!draftPosition) {
      return;
    }

    if (selection?.type === "DECOR") {
      setDecorObjects((items) =>
        items.map((item) =>
          item.id === selection.id
            ? {
                ...item,
                x: draftPosition.x,
                y: draftPosition.y,
                width: draftPosition.width,
                height: draftPosition.height,
                rotation: draftPosition.rotation ?? 0,
                shape: draftPosition.shape ?? item.shape,
              }
            : item,
        ),
      );
      return;
    }

    if (!token || !floorPlan || !selectedTable || selection?.type !== "TABLE") {
      return;
    }

    setIsSaving(true);
    setEditorError(null);
    try {
      await updateFloorPlanTablePosition(
        token,
        floorPlan.id,
        selectedTable.id,
        draftPosition,
      );
      await loadFloorPlan();
    } catch (exc) {
      setEditorError(exc instanceof ApiError ? exc.message : "Could not save position.");
    } finally {
      setIsSaving(false);
    }
  }

  function deleteSelectedDecor() {
    if (selection?.type !== "DECOR") {
      return;
    }

    setDecorObjects((items) => items.filter((item) => item.id !== selection.id));
    setSelection(null);
  }
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
      onClick={(event) => {
        event.stopPropagation();
        onSelect();
      }}
    >
      <strong>{item.table?.table_number ?? `#${item.table_id}`}</strong>
      <span>{statusLabels[tableStatus] ?? tableStatus}</span>
    </button>
  );
}

function DecorObjectView({
  item,
  isSelected,
  onSelect,
}: {
  item: DecorObject;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={`decor-object ${
        item.shape === "CIRCLE" ? "circle" : "rectangle"
      } ${isSelected ? "selected" : ""}`}
      style={{
        left: item.x,
        top: item.y,
        width: item.width,
        height: item.height,
        transform: `rotate(${item.rotation}deg)`,
      }}
      onClick={(event) => {
        event.stopPropagation();
        onSelect();
      }}
      aria-label="Decor object"
    />
  );
}

function EditorPanel({
  tool,
  tableNumber,
  error,
  onToolChange,
  onTableNumberChange,
}: {
  tool: EditorTool;
  tableNumber: string;
  error: string | null;
  onToolChange: (tool: EditorTool) => void;
  onTableNumberChange: (value: string) => void;
}) {
  return (
    <div className="editor-panel">
      <h2>Editor</h2>
      <div className="tool-grid">
        <ToolButton current={tool} value="SELECT" label="Select" onClick={onToolChange} />
        <ToolButton
          current={tool}
          value="TABLE_RECTANGLE"
          label="Table rect"
          onClick={onToolChange}
        />
        <ToolButton
          current={tool}
          value="TABLE_CIRCLE"
          label="Table circle"
          onClick={onToolChange}
        />
        <ToolButton
          current={tool}
          value="DECOR_RECTANGLE"
          label="Filled rect"
          onClick={onToolChange}
        />
        <ToolButton
          current={tool}
          value="DECOR_CIRCLE"
          label="Filled circle"
          onClick={onToolChange}
        />
      </div>
      <label className="compact-field">
        Table number
        <input
          value={tableNumber}
          onChange={(event) => onTableNumberChange(event.target.value)}
          placeholder="e.g. 12"
        />
      </label>
      {error && <div className="error-box">{error}</div>}
    </div>
  );
}

function ToolButton({
  current,
  value,
  label,
  onClick,
}: {
  current: EditorTool;
  value: EditorTool;
  label: string;
  onClick: (value: EditorTool) => void;
}) {
  return (
    <button
      type="button"
      className={`tool-button ${current === value ? "active" : ""}`}
      onClick={() => onClick(value)}
    >
      {label}
    </button>
  );
}

function PositionEditor({
  position,
  selection,
  isSaving,
  onChange,
  onSave,
  onDeleteDecor,
}: {
  position: FloorPlanTablePositionInput;
  selection: Selection;
  isSaving: boolean;
  onChange: (position: FloorPlanTablePositionInput) => void;
  onSave: () => void;
  onDeleteDecor: () => void;
}) {
  const update = (field: keyof FloorPlanTablePositionInput, value: string) => {
    onChange({
      ...position,
      [field]: field === "shape" ? value : Number(value),
    });
  };

  return (
    <div className="position-editor">
      <h2>Position</h2>
      <div className="position-grid">
        <NumberField label="X" value={position.x} onChange={(value) => update("x", value)} />
        <NumberField label="Y" value={position.y} onChange={(value) => update("y", value)} />
        <NumberField
          label="Width"
          value={position.width}
          onChange={(value) => update("width", value)}
        />
        <NumberField
          label="Height"
          value={position.height}
          onChange={(value) => update("height", value)}
        />
        <NumberField
          label="Rotation"
          value={position.rotation ?? 0}
          onChange={(value) => update("rotation", value)}
        />
      </div>
      <div className="editor-actions">
        <button type="button" className="primary-button" onClick={onSave} disabled={isSaving}>
          {isSaving ? "Saving..." : "Save"}
        </button>
        {selection?.type === "DECOR" && (
          <button type="button" className="ghost-button danger" onClick={onDeleteDecor}>
            Remove
          </button>
        )}
      </div>
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: string) => void;
}) {
  return (
    <label className="compact-field">
      {label}
      <input
        type="number"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
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

function DecorDetails({ item }: { item: DecorObject }) {
  return (
    <div className="table-details">
      <div>
        <span className="detail-label">Type</span>
        <strong>Filled {item.shape.toLowerCase()}</strong>
      </div>
      <div>
        <span className="detail-label">Storage</span>
        <strong>Local map object</strong>
      </div>
    </div>
  );
}

function statusClass(status: RestaurantTableStatus): string {
  return `status-${status.toLowerCase().replaceAll("_", "-")}`;
}

function loadDecorObjects(): DecorObject[] {
  const rawValue = window.localStorage.getItem(DECOR_STORAGE_KEY);
  if (!rawValue) {
    return [];
  }

  try {
    return JSON.parse(rawValue) as DecorObject[];
  } catch {
    window.localStorage.removeItem(DECOR_STORAGE_KEY);
    return [];
  }
}

function saveDecorObjects(items: DecorObject[]): void {
  window.localStorage.setItem(DECOR_STORAGE_KEY, JSON.stringify(items));
}
