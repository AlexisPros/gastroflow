import {
  MouseEvent,
  PointerEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { ApiError } from "../api/apiClient";
import {
  createFloorPlanDecoration,
  createRestaurantTableOnFloorPlan,
  deleteFloorPlanDecoration,
  deleteFloorPlanTable,
  deleteRestaurantTable,
  getFloorPlanView,
  updateFloorPlanDecoration,
  updateFloorPlanTablePosition,
  type FloorPlan,
  type FloorPlanDecoration,
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
  | { type: "DECOR"; id: number }
  | null;
type ResizeHandle = "nw" | "ne" | "sw" | "se";
type Interaction = {
  mode: "MOVE" | "RESIZE";
  selection: NonNullable<Selection>;
  startClientX: number;
  startClientY: number;
  startPosition: FloorPlanTablePositionInput;
  handle?: ResizeHandle;
} | null;

const statusLabels: Record<string, string> = {
  FREE: "Free",
  PENDING_ORDER: "Pending QR",
  OCCUPIED: "Occupied",
  RESERVED: "Reserved",
};

export function FloorPlanPage() {
  const { token, user } = useAuth();
  const [floorPlan, setFloorPlan] = useState<FloorPlan | null>(null);
  const [tables, setTables] = useState<FloorTableView[]>([]);
  const [decorations, setDecorations] = useState<FloorPlanDecoration[]>([]);
  const [selection, setSelection] = useState<Selection>(null);
  const [interaction, setInteraction] = useState<Interaction>(null);
  const [editorTool, setEditorTool] = useState<EditorTool>("SELECT");
  const [newTableNumber, setNewTableNumber] = useState("");
  const [newDecorationLabel, setNewDecorationLabel] = useState("");
  const [draftPosition, setDraftPosition] =
    useState<FloorPlanTablePositionInput | null>(null);
  const [status, setStatus] = useState<LoadingState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [mapScale, setMapScale] = useState(1);
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
      setDecorations(data.decorations);
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

  const selectedTable = useMemo(() => {
    if (selection?.type !== "TABLE") {
      return null;
    }
    return tables.find((item) => item.id === selection.id) ?? null;
  }, [selection, tables]);

  const selectedDecoration = useMemo(() => {
    if (selection?.type !== "DECOR") {
      return null;
    }
    return decorations.find((item) => item.id === selection.id) ?? null;
  }, [decorations, selection]);

  useEffect(() => {
    if (interaction) {
      return;
    }

    if (selectedTable) {
      setDraftPosition(toPosition(selectedTable));
      return;
    }

    if (selectedDecoration) {
      setDraftPosition(toPosition(selectedDecoration));
      return;
    }

    setDraftPosition(null);
  }, [interaction, selectedDecoration, selectedTable]);

  useEffect(() => {
    if (!interaction) {
      return;
    }

    const handleMove = (event: globalThis.PointerEvent) => {
      const dx = (event.clientX - interaction.startClientX) / mapScale;
      const dy = (event.clientY - interaction.startClientY) / mapScale;
      const nextPosition =
        interaction.mode === "MOVE"
          ? movePosition(interaction.startPosition, dx, dy)
          : resizePosition(interaction.startPosition, dx, dy, interaction.handle ?? "se");

      applyPositionLocally(interaction.selection, nextPosition);
      setDraftPosition(nextPosition);
    };

    const handleUp = () => {
      const finalSelection = interaction.selection;
      const finalPosition = getSelectedPosition(finalSelection);
      setInteraction(null);
      if (finalPosition) {
        void persistPosition(finalSelection, finalPosition);
      }
    };

    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp, { once: true });

    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
    };
  // The pointer effect must track the current in-flight interaction and latest objects.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interaction, decorations, mapScale, tables]);

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
            <StatusBadge label="Pending" value={counts.PENDING_ORDER ?? 0} status="PENDING_ORDER" />
            <StatusBadge label="Occupied" value={counts.OCCUPIED ?? 0} status="OCCUPIED" />
            <StatusBadge label="Reserved" value={counts.RESERVED ?? 0} status="RESERVED" />
            <div className="zoom-controls">
              <button
                type="button"
                className="tool-button"
                onClick={() => setMapScale((value) => clampScale(value - 0.1))}
              >
                -
              </button>
              <button
                type="button"
                className="tool-button"
                onClick={() => setMapScale(1)}
              >
                {Math.round(mapScale * 100)}%
              </button>
              <button
                type="button"
                className="tool-button"
                onClick={() => setMapScale((value) => clampScale(value + 0.1))}
              >
                +
              </button>
            </div>
          </div>

          {floorPlan ? (
            <div
              className="floor-map-scroll"
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
              <div
                className="floor-map"
                style={{
                  width: floorPlan.width,
                  height: floorPlan.height,
                  transform: `scale(${mapScale})`,
                  backgroundImage: floorPlan.background_image_url
                    ? `url(${floorPlan.background_image_url})`
                    : undefined,
                }}
                onClick={(event) => {
                  void handleMapClick(event);
                }}
              >
                {decorations.map((item) => (
                  <DecorObjectView
                    key={item.id}
                    item={item}
                    canEdit={canEdit}
                    isSelected={selection?.type === "DECOR" && selection.id === item.id}
                    onPointerDown={(event) => {
                      startInteraction(event, { type: "DECOR", id: item.id }, "MOVE");
                    }}
                    onResizePointerDown={(event, handle) => {
                      startInteraction(event, { type: "DECOR", id: item.id }, "RESIZE", handle);
                    }}
                  />
                ))}
                {tables.map((item) => (
                  <FloorTableButton
                    key={item.id}
                    item={item}
                    canEdit={canEdit}
                    isSelected={selection?.type === "TABLE" && selection.id === item.id}
                    onPointerDown={(event) => {
                      startInteraction(event, { type: "TABLE", id: item.id }, "MOVE");
                    }}
                    onResizePointerDown={(event, handle) => {
                      startInteraction(event, { type: "TABLE", id: item.id }, "RESIZE", handle);
                    }}
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
              decorationLabel={newDecorationLabel}
              error={editorError}
              onToolChange={setEditorTool}
              onTableNumberChange={setNewTableNumber}
              onDecorationLabelChange={setNewDecorationLabel}
            />
          )}

          <h2>{selectedDecoration ? "Object details" : "Table details"}</h2>
          {selectedTable && <TableDetails item={selectedTable} />}
          {selectedDecoration && <DecorationDetails item={selectedDecoration} />}
          {canEdit && selectedDecoration && (
            <DecorationLabelEditor
              decoration={selectedDecoration}
              isSaving={isSaving}
              onSave={(label) => {
                void saveDecorationLabel(selectedDecoration.id, label);
              }}
            />
          )}
          {!selectedTable && !selectedDecoration && (
            <p className="muted">Select an object on the map.</p>
          )}
          {canEdit && draftPosition && (
            <PositionEditor
              position={draftPosition}
              selection={selection}
              isSaving={isSaving}
              onChange={setDraftPosition}
              onSave={() => {
                void saveSelectedPosition();
              }}
              onDelete={() => {
                void deleteSelectedObject();
              }}
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
    const x = Math.max(0, Math.round((event.clientX - rect.left) / mapScale - 45));
    const y = Math.max(0, Math.round((event.clientY - rect.top) / mapScale - 35));

    if (editorTool === "TABLE_RECTANGLE" || editorTool === "TABLE_CIRCLE") {
      await createTableAtPosition({
        x,
        y,
        shape: editorTool === "TABLE_CIRCLE" ? "CIRCLE" : "RECTANGLE",
      });
      return;
    }

    await createDecorationAtPosition({
      x,
      y,
      shape: editorTool === "DECOR_CIRCLE" ? "CIRCLE" : "RECTANGLE",
    });
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

  async function createDecorationAtPosition({
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

    setIsSaving(true);
    setEditorError(null);
    try {
      await createFloorPlanDecoration(token, floorPlan.id, {
        floor_plan_id: floorPlan.id,
        x,
        y,
        width: shape === "CIRCLE" ? 80 : 140,
        height: shape === "CIRCLE" ? 80 : 36,
        rotation: 0,
        shape,
        color: "#252b2d",
        label: newDecorationLabel.trim() || null,
      });
      setNewDecorationLabel("");
      await loadFloorPlan();
    } catch (exc) {
      setEditorError(exc instanceof ApiError ? exc.message : "Could not create object.");
    } finally {
      setIsSaving(false);
    }
  }

  async function saveDecorationLabel(decorationId: number, label: string) {
    if (!token || !floorPlan) {
      return;
    }

    setIsSaving(true);
    setEditorError(null);
    try {
      await updateFloorPlanDecoration(token, floorPlan.id, decorationId, {
        label: label.trim() || null,
      });
      await loadFloorPlan();
    } catch (exc) {
      setEditorError(exc instanceof ApiError ? exc.message : "Could not save label.");
    } finally {
      setIsSaving(false);
    }
  }

  function startInteraction(
    event: PointerEvent<HTMLElement>,
    nextSelection: NonNullable<Selection>,
    mode: "MOVE" | "RESIZE",
    handle?: ResizeHandle,
  ) {
    event.stopPropagation();
    setSelection(nextSelection);

    if (!canEdit || editorTool !== "SELECT") {
      return;
    }

    const startPosition = getSelectedPosition(nextSelection);
    if (!startPosition) {
      return;
    }

    setInteraction({
      mode,
      selection: nextSelection,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startPosition,
      handle,
    });
  }

  async function saveSelectedPosition() {
    if (!selection || !draftPosition) {
      return;
    }

    applyPositionLocally(selection, draftPosition);
    await persistPosition(selection, draftPosition);
  }

  async function persistPosition(
    targetSelection: NonNullable<Selection>,
    position: FloorPlanTablePositionInput,
  ) {
    if (!token || !floorPlan) {
      return;
    }

    setIsSaving(true);
    setEditorError(null);
    try {
      if (targetSelection.type === "TABLE") {
        await updateFloorPlanTablePosition(token, floorPlan.id, targetSelection.id, position);
      } else {
        await updateFloorPlanDecoration(token, floorPlan.id, targetSelection.id, position);
      }
      await loadFloorPlan();
    } catch (exc) {
      setEditorError(exc instanceof ApiError ? exc.message : "Could not save position.");
      await loadFloorPlan();
    } finally {
      setIsSaving(false);
    }
  }

  async function deleteSelectedObject() {
    if (!selection || !token || !floorPlan) {
      return;
    }

    setIsSaving(true);
    setEditorError(null);
    try {
      if (selection.type === "DECOR") {
        await deleteFloorPlanDecoration(token, floorPlan.id, selection.id);
      } else {
        const table = tables.find((item) => item.id === selection.id);
        if (!table) {
          return;
        }
        await deleteFloorPlanTable(token, floorPlan.id, table.id);
        await deleteRestaurantTable(token, table.table_id);
      }
      setSelection(null);
      await loadFloorPlan();
    } catch (exc) {
      setEditorError(exc instanceof ApiError ? exc.message : "Could not delete object.");
    } finally {
      setIsSaving(false);
    }
  }

  function getSelectedPosition(targetSelection: NonNullable<Selection>) {
    if (targetSelection.type === "TABLE") {
      const item = tables.find((table) => table.id === targetSelection.id);
      return item ? toPosition(item) : null;
    }

    const item = decorations.find((decoration) => decoration.id === targetSelection.id);
    return item ? toPosition(item) : null;
  }

  function applyPositionLocally(
    targetSelection: NonNullable<Selection>,
    position: FloorPlanTablePositionInput,
  ) {
    if (targetSelection.type === "TABLE") {
      setTables((items) =>
        items.map((item) =>
          item.id === targetSelection.id ? applyPosition(item, position) : item,
        ),
      );
      return;
    }

    setDecorations((items) =>
      items.map((item) =>
        item.id === targetSelection.id ? applyPosition(item, position) : item,
      ),
    );
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
  canEdit,
  isSelected,
  onPointerDown,
  onResizePointerDown,
}: {
  item: FloorTableView;
  canEdit: boolean;
  isSelected: boolean;
  onPointerDown: (event: PointerEvent<HTMLButtonElement>) => void;
  onResizePointerDown: (
    event: PointerEvent<HTMLSpanElement>,
    handle: ResizeHandle,
  ) => void;
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
      onPointerDown={onPointerDown}
    >
      <strong>{item.table?.table_number ?? `#${item.table_id}`}</strong>
      <span>{statusLabels[tableStatus] ?? tableStatus}</span>
      {canEdit && isSelected && <ResizeHandles onPointerDown={onResizePointerDown} />}
    </button>
  );
}

function DecorObjectView({
  item,
  canEdit,
  isSelected,
  onPointerDown,
  onResizePointerDown,
}: {
  item: FloorPlanDecoration;
  canEdit: boolean;
  isSelected: boolean;
  onPointerDown: (event: PointerEvent<HTMLButtonElement>) => void;
  onResizePointerDown: (
    event: PointerEvent<HTMLSpanElement>,
    handle: ResizeHandle,
  ) => void;
}) {
  return (
    <button
      type="button"
      className={`decor-object ${
        item.shape === "CIRCLE" ? "circle" : "rectangle"
      } ${isSelected ? "selected" : ""}`}
      style={{
        left: Number(item.x),
        top: Number(item.y),
        width: Number(item.width),
        height: Number(item.height),
        transform: `rotate(${Number(item.rotation)}deg)`,
        background: item.color,
      }}
      onPointerDown={onPointerDown}
      aria-label="Decor object"
    >
      {item.label && <span className="decor-label">{item.label}</span>}
      {canEdit && isSelected && <ResizeHandles onPointerDown={onResizePointerDown} />}
    </button>
  );
}

function ResizeHandles({
  onPointerDown,
}: {
  onPointerDown: (event: PointerEvent<HTMLSpanElement>, handle: ResizeHandle) => void;
}) {
  const handles: ResizeHandle[] = ["nw", "ne", "sw", "se"];
  return (
    <>
      {handles.map((handle) => (
        <span
          key={handle}
          className={`resize-handle ${handle}`}
          onPointerDown={(event) => onPointerDown(event, handle)}
        />
      ))}
    </>
  );
}

function EditorPanel({
  tool,
  tableNumber,
  decorationLabel,
  error,
  onToolChange,
  onTableNumberChange,
  onDecorationLabelChange,
}: {
  tool: EditorTool;
  tableNumber: string;
  decorationLabel: string;
  error: string | null;
  onToolChange: (tool: EditorTool) => void;
  onTableNumberChange: (value: string) => void;
  onDecorationLabelChange: (value: string) => void;
}) {
  const isDecorationTool = tool === "DECOR_RECTANGLE" || tool === "DECOR_CIRCLE";

  return (
    <div className="editor-panel">
      <h2>Editor</h2>
      <div className="tool-grid">
        <ToolButton current={tool} value="SELECT" label="Select" onClick={onToolChange} />
        <ToolButton current={tool} value="TABLE_RECTANGLE" label="Table rect" onClick={onToolChange} />
        <ToolButton current={tool} value="TABLE_CIRCLE" label="Table circle" onClick={onToolChange} />
        <ToolButton current={tool} value="DECOR_RECTANGLE" label="Filled rect" onClick={onToolChange} />
        <ToolButton current={tool} value="DECOR_CIRCLE" label="Filled circle" onClick={onToolChange} />
      </div>
      <label className="compact-field">
        Table number
        <input
          value={tableNumber}
          onChange={(event) => onTableNumberChange(event.target.value)}
          placeholder="e.g. 12"
        />
      </label>
      {isDecorationTool && (
        <label className="compact-field">
          Object label
          <input
            value={decorationLabel}
            onChange={(event) => onDecorationLabelChange(event.target.value)}
            placeholder="e.g. Bar"
            maxLength={150}
          />
        </label>
      )}
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
  onDelete,
}: {
  position: FloorPlanTablePositionInput;
  selection: Selection;
  isSaving: boolean;
  onChange: (position: FloorPlanTablePositionInput) => void;
  onSave: () => void;
  onDelete: () => void;
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
        <NumberField label="Width" value={position.width} onChange={(value) => update("width", value)} />
        <NumberField label="Height" value={position.height} onChange={(value) => update("height", value)} />
        <NumberField label="Rotation" value={position.rotation ?? 0} onChange={(value) => update("rotation", value)} />
      </div>
      <div className="editor-actions">
        <button type="button" className="primary-button" onClick={onSave} disabled={isSaving}>
          {isSaving ? "Saving..." : "Save"}
        </button>
        {selection && (
          <button type="button" className="ghost-button danger" onClick={onDelete}>
            Delete
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

function DecorationDetails({ item }: { item: FloorPlanDecoration }) {
  return (
    <div className="table-details">
      <div>
        <span className="detail-label">Label</span>
        <strong>{item.label || "No label"}</strong>
      </div>
      <div>
        <span className="detail-label">Type</span>
        <strong>Filled {item.shape.toLowerCase()}</strong>
      </div>
      <div>
        <span className="detail-label">Storage</span>
        <strong>Database object</strong>
      </div>
    </div>
  );
}

function DecorationLabelEditor({
  decoration,
  isSaving,
  onSave,
}: {
  decoration: FloorPlanDecoration;
  isSaving: boolean;
  onSave: (label: string) => void;
}) {
  const [label, setLabel] = useState(decoration.label ?? "");

  useEffect(() => {
    setLabel(decoration.label ?? "");
  }, [decoration.id, decoration.label]);

  return (
    <div className="position-editor">
      <h2>Label</h2>
      <label className="compact-field">
        Object label
        <input
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          placeholder="e.g. Bar"
          maxLength={150}
        />
      </label>
      <button
        type="button"
        className="primary-button"
        onClick={() => onSave(label)}
        disabled={isSaving}
      >
        {isSaving ? "Saving..." : "Save label"}
      </button>
    </div>
  );
}

function toPosition(
  item: FloorTableView | FloorPlanDecoration,
): FloorPlanTablePositionInput {
  return {
    x: Number(item.x),
    y: Number(item.y),
    width: Number(item.width),
    height: Number(item.height),
    rotation: Number(item.rotation),
    shape: item.shape === "CIRCLE" ? "CIRCLE" : "RECTANGLE",
  };
}

function applyPosition<T extends FloorTableView | FloorPlanDecoration>(
  item: T,
  position: FloorPlanTablePositionInput,
): T {
  return {
    ...item,
    x: String(position.x),
    y: String(position.y),
    width: String(position.width),
    height: String(position.height),
    rotation: String(position.rotation ?? 0),
    shape: position.shape ?? item.shape,
  };
}

function movePosition(
  position: FloorPlanTablePositionInput,
  dx: number,
  dy: number,
): FloorPlanTablePositionInput {
  return {
    ...position,
    x: Math.max(0, Math.round(position.x + dx)),
    y: Math.max(0, Math.round(position.y + dy)),
  };
}

function resizePosition(
  position: FloorPlanTablePositionInput,
  dx: number,
  dy: number,
  handle: ResizeHandle,
): FloorPlanTablePositionInput {
  const minSize = 24;
  let x = position.x;
  let y = position.y;
  let width = position.width;
  let height = position.height;

  if (handle.includes("e")) {
    width = Math.max(minSize, position.width + dx);
  }
  if (handle.includes("s")) {
    height = Math.max(minSize, position.height + dy);
  }
  if (handle.includes("w")) {
    const nextWidth = Math.max(minSize, position.width - dx);
    x = position.x + (position.width - nextWidth);
    width = nextWidth;
  }
  if (handle.includes("n")) {
    const nextHeight = Math.max(minSize, position.height - dy);
    y = position.y + (position.height - nextHeight);
    height = nextHeight;
  }

  return {
    ...position,
    x: Math.max(0, Math.round(x)),
    y: Math.max(0, Math.round(y)),
    width: Math.round(width),
    height: Math.round(height),
  };
}

function statusClass(status: RestaurantTableStatus): string {
  return `status-${status.toLowerCase().replaceAll("_", "-")}`;
}

function clampScale(value: number): number {
  return Math.min(2, Math.max(0.5, Number(value.toFixed(2))));
}
