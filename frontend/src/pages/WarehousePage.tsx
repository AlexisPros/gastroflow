import { useCallback, useEffect, useMemo, useState, useRef } from "react";
import {
  ArrowRightLeft,
  ClipboardCheck,
  ClipboardMinus,
  Download,
  PackagePlus,
  Pencil,
  Plus,
  RefreshCw,
  Settings,
  ShieldCheck,
  Trash2,
  TriangleAlert,
  X,
} from "lucide-react";

import { ApiError } from "../api/apiClient";
import {
  addWarehouseItem,
  createInventoryDocument,
  createReceiptDocument,
  createTransferDocument,
  createWarehouse,
  createWriteOffDocument,
  deleteWarehouse,
  deleteWarehouseItem,
  downloadWarehouseDocumentPdf,
  getStockIngredients,
  getInventorySheet,
  getWarehouseAccess,
  getWarehouseDocuments,
  getWarehouseItems,
  getWarehouses,
  updateWarehouse,
  updateWarehouseAccess,
  updateWarehouseItem,
  type StockIngredient,
  type InventorySheet,
  type Warehouse,
  type WarehouseAccessUser,
  type WarehouseDocument,
  type WarehouseStockItem,
} from "../api/warehouseApi";
import { useAuth } from "../auth/useAuth";
import { usePrompt } from "../components/PromptProvider";

type ModalKind = "WAREHOUSE" | "ITEM" | "PZ" | "MM" | "RW" | "INVENTORY" | "ACCESS" | null;

type DocumentLineForm = {
  key: number;
  ingredient_id: number | null;
  quantity: string;
  unit_price: string;
};

type InventoryLineForm = {
  stock_item_id: number;
  ingredient_name: string;
  unit: string;
  book_quantity: string;
  actual_quantity: string;
  unit_price: string;
};

let lineKey = 0;

const number = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 3 });
const money = new Intl.NumberFormat("pl-PL", { style: "currency", currency: "PLN" });

export function WarehousePage() {
  const { token, user } = useAuth();
  const { confirm } = usePrompt();
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [selectedWarehouseId, setSelectedWarehouseId] = useState<number | null>(null);
  const [ingredients, setIngredients] = useState<StockIngredient[]>([]);
  const [items, setItems] = useState<WarehouseStockItem[]>([]);
  const [documents, setDocuments] = useState<WarehouseDocument[]>([]);
  const [viewingDocument, setViewingDocument] = useState<WarehouseDocument | null>(null);
  const [accessUsers, setAccessUsers] = useState<WarehouseAccessUser[]>([]);
  const [modal, setModal] = useState<ModalKind>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [downloadingDocumentId, setDownloadingDocumentId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [warehouseName, setWarehouseName] = useState("");
  const [warehouseDefault, setWarehouseDefault] = useState(false);
  const [editingWarehouseId, setEditingWarehouseId] = useState<number | null>(null);
  const [newIngredientId, setNewIngredientId] = useState<number | null>(null);
  const [newMinimum, setNewMinimum] = useState("");
  const [editingItem, setEditingItem] = useState<WarehouseStockItem | null>(null);
  const [itemName, setItemName] = useState("");
  const [itemUnit, setItemUnit] = useState("");
  const [operationDate, setOperationDate] = useState(today());
  const [description, setDescription] = useState("");
  const [reason, setReason] = useState("");
  const [destinationWarehouseId, setDestinationWarehouseId] = useState<number | null>(null);
  const [documentLines, setDocumentLines] = useState<DocumentLineForm[]>([emptyLine()]);
  const [inventorySheet, setInventorySheet] = useState<InventorySheet | null>(null);
  const [inventoryLines, setInventoryLines] = useState<InventoryLineForm[]>([]);

  const selectedWarehouse = warehouses.find((warehouse) => warehouse.id === selectedWarehouseId) ?? null;
  const lowStockItems = useMemo(() => items.filter((item) => item.is_low_stock), [items]);
  const availableIngredients = useMemo(
    () => ingredients.filter((ingredient) => ingredient.is_active),
    [ingredients],
  );

  const loadWarehouses = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    setError(null);
    try {
      const next = await getWarehouses(token);
      setWarehouses(next);
      setSelectedWarehouseId((current) => (
        current && next.some((warehouse) => warehouse.id === current)
          ? current
          : next[0]?.id ?? null
      ));
    } catch (exc) {
      setError(errorMessage(exc, "Nie udało się załadować magazynów."));
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  const loadWarehouseData = useCallback(async () => {
    if (!token || selectedWarehouseId === null) {
      setItems([]);
      setDocuments([]);
      setIngredients([]);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const [nextItems, nextDocuments, nextIngredients] = await Promise.all([
        getWarehouseItems(token, selectedWarehouseId),
        getWarehouseDocuments(token, selectedWarehouseId),
        getStockIngredients(token),
      ]);
      setItems(nextItems);
      setDocuments(nextDocuments);
      setIngredients(nextIngredients);
    } catch (exc) {
      setError(errorMessage(exc, "Nie udało się załadować stanu magazynu."));
    } finally {
      setIsLoading(false);
    }
  }, [selectedWarehouseId, token]);

  useEffect(() => {
    void loadWarehouses();
  }, [loadWarehouses]);

  useEffect(() => {
    void loadWarehouseData();
  }, [loadWarehouseData]);

  function openDocumentModal(kind: "PZ" | "MM" | "RW") {
    setOperationDate(today());
    setDescription("");
    setReason("");
    setDestinationWarehouseId(
      warehouses.find((warehouse) => warehouse.id !== selectedWarehouseId && warehouse.is_active)?.id ?? null,
    );
    setDocumentLines([emptyLine()]);
    setModal(kind);
  }

  async function openInventory() {
    if (!token || selectedWarehouseId === null) return;
    setIsLoading(true);
    setError(null);
    try {
      const sheet = await getInventorySheet(token, selectedWarehouseId);
      if (sheet.items.length === 0) {
        setError("Magazyn nie zawiera aktywnych towarów do inwentaryzacji.");
        return;
      }
      setOperationDate(today());
      setReason("Inwentaryzacja okresowa");
      setDescription("");
      setInventorySheet(sheet);
      setInventoryLines(sheet.items.map((item) => ({
        stock_item_id: item.stock_item_id,
        ingredient_name: item.ingredient_name,
        unit: item.unit,
        book_quantity: item.book_quantity,
        actual_quantity: "",
        unit_price: item.suggested_unit_price ?? "",
      })));
      setModal("INVENTORY");
    } catch (exc) {
      setError(errorMessage(exc, "Nie udało się przygotować arkusza inwentaryzacji."));
    } finally {
      setIsLoading(false);
    }
  }

  async function saveWarehouse() {
    if (!token || !warehouseName.trim()) return;
    await runSave(async () => {
      const wasEditing = editingWarehouseId !== null;
      const saved = editingWarehouseId === null
        ? await createWarehouse(token, {
            name: warehouseName.trim(),
            is_default: warehouseDefault,
          })
        : await updateWarehouse(token, editingWarehouseId, {
            name: warehouseName.trim(),
            is_default: warehouseDefault,
          });
      setModal(null);
      setEditingWarehouseId(null);
      setWarehouseName("");
      setWarehouseDefault(false);
      await loadWarehouses();
      setSelectedWarehouseId(saved.id);
      setNotice(
        wasEditing
          ? `Zapisano zmiany magazynu „${saved.name}”.`
          : `Utworzono magazyn „${saved.name}”.`,
      );
    });
  }

  async function removeWarehouse(warehouse: Warehouse) {
    if (!token) return;
    const accepted = await confirm({
      title: `Usunąć magazyn „${warehouse.name}”?`,
      message: "Magazyn z niezerowym stanem nie może zostać usunięty. Historia dokumentów pozostanie zachowana.",
      confirmText: "Usuń magazyn",
      cancelText: "Anuluj",
    });
    if (!accepted) return;
    await runSave(async () => {
      await deleteWarehouse(token, warehouse.id);
      setSelectedWarehouseId(null);
      await loadWarehouses();
      setNotice(`Usunięto magazyn „${warehouse.name}”.`);
    });
  }

  async function addItem() {
    if (!token || selectedWarehouseId === null || newIngredientId === null) return;
    await runSave(async () => {
      await addWarehouseItem(token, selectedWarehouseId, {
        ingredient_id: newIngredientId,
        minimum_quantity: newMinimum || null,
      });
      setModal(null);
      setNewIngredientId(null);
      setNewMinimum("");
      await loadWarehouseData();
      setNotice("Dodano towar do magazynu. Stan początkowy wynosi 0.");
    });
  }

  async function saveItem() {
    if (!token || editingItem === null || !itemName.trim() || !itemUnit.trim()) return;
    await runSave(async () => {
      await updateWarehouseItem(token, editingItem.id, {
        ingredient_name: itemName.trim(),
        unit: itemUnit.trim(),
        minimum_quantity: newMinimum || null,
      });
      setModal(null);
      setEditingItem(null);
      await loadWarehouseData();
      setNotice(`Zapisano zmiany towaru „${itemName.trim()}”.`);
    });
  }

  async function removeItem(item: WarehouseStockItem) {
    if (!token) return;
    const accepted = await confirm({
      title: `Usunąć towar „${item.ingredient_name}”?`,
      message: "Towar można usunąć tylko przy stanie 0. Historia ruchów magazynowych pozostanie zachowana.",
      confirmText: "Usuń towar",
      cancelText: "Anuluj",
    });
    if (!accepted) return;
    await runSave(async () => {
      await deleteWarehouseItem(token, item.id);
      await loadWarehouseData();
      setNotice(`Usunięto towar „${item.ingredient_name}”.`);
    });
  }

  async function saveDocument() {
    if (!token || selectedWarehouseId === null || modal === null) return;
    const lines = documentLines
      .filter((line) => line.ingredient_id !== null && Number(line.quantity) > 0)
      .map((line) => ({
        ingredient_id: line.ingredient_id as number,
        quantity: line.quantity,
        unit_price: line.unit_price || null,
      }));
    if (lines.length === 0) {
      setError("Dodaj co najmniej jedną pozycję z ilością większą od zera.");
      return;
    }

    await runSave(async () => {
      let saved: WarehouseDocument;
      if (modal === "PZ") {
        saved = await createReceiptDocument(token, {
          warehouse_id: selectedWarehouseId,
          operation_date: operationDate,
          description: description || null,
          items: lines,
        });
      } else if (modal === "MM") {
        if (destinationWarehouseId === null) {
          throw new Error("Wybierz magazyn docelowy.");
        }
        saved = await createTransferDocument(token, {
          source_warehouse_id: selectedWarehouseId,
          destination_warehouse_id: destinationWarehouseId,
          operation_date: operationDate,
          description: description || null,
          items: lines,
        });
      } else if (modal === "RW") {
        saved = await createWriteOffDocument(token, {
          warehouse_id: selectedWarehouseId,
          operation_date: operationDate,
          reason,
          description: description || null,
          items: lines,
        });
      } else {
        return;
      }
      setModal(null);
      await loadWarehouseData();
      setNotice(`Zapisano dokument ${saved.document_number}.`);
    });
  }

  async function saveInventory() {
    if (!token || selectedWarehouseId === null || inventorySheet === null) return;
    const invalidLine = inventoryLines.find((line) => (
      line.actual_quantity.trim() === ""
      || line.unit_price.trim() === ""
      || !isNonNegativeNumber(line.actual_quantity)
      || !isNonNegativeNumber(line.unit_price)
    ));
    if (invalidLine) {
      setError(`Uzupełnij poprawny stan faktyczny i cenę dla towaru „${invalidLine.ingredient_name}”.`);
      return;
    }
    if (!reason.trim()) {
      setError("Wybierz rodzaj lub podstawę inwentaryzacji.");
      return;
    }

    const accepted = await confirm({
      title: "Zatwierdzić inwentaryzację?",
      message: "Dokument skoryguje stany magazynowe do wartości faktycznych. Po zatwierdzeniu nie będzie można go edytować ani usunąć.",
      confirmText: "Zatwierdź dokument INW",
      cancelText: "Wróć do arkusza",
    });
    if (!accepted) return;

    await runSave(async () => {
      const saved = await createInventoryDocument(token, {
        warehouse_id: selectedWarehouseId,
        operation_date: operationDate,
        reason: reason.trim(),
        description: description.trim() || null,
        items: inventoryLines.map((line) => ({
          stock_item_id: line.stock_item_id,
          book_quantity: line.book_quantity,
          actual_quantity: normalizeDecimal(line.actual_quantity),
          unit_price: normalizeDecimal(line.unit_price),
        })),
      });
      setModal(null);
      setInventorySheet(null);
      setInventoryLines([]);
      await loadWarehouseData();
      setNotice(`Zatwierdzono inwentaryzację ${saved.document_number}.`);
    });
  }

  async function openAccess() {
    if (!token || selectedWarehouseId === null) return;
    setError(null);
    try {
      setAccessUsers(await getWarehouseAccess(token, selectedWarehouseId));
      setModal("ACCESS");
    } catch (exc) {
      setError(errorMessage(exc, "Nie udało się załadować dostępu pracowników."));
    }
  }

  async function saveAccess() {
    if (!token || selectedWarehouseId === null) return;
    await runSave(async () => {
      await updateWarehouseAccess(
        token,
        selectedWarehouseId,
        accessUsers.filter((employee) => employee.has_access).map((employee) => employee.id),
      );
      setModal(null);
      setNotice("Zaktualizowano dostęp do magazynu.");
    });
  }

  async function runSave(action: () => Promise<void>) {
    setIsSaving(true);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (exc) {
      setError(errorMessage(exc, "Nie udało się zapisać zmian."));
    } finally {
      setIsSaving(false);
    }
  }

  async function downloadDocument(document: WarehouseDocument) {
    if (!token) return;
    setDownloadingDocumentId(document.id);
    setError(null);
    try {
      const blob = await downloadWarehouseDocumentPdf(token, document.id);
      const url = URL.createObjectURL(blob);
      const link = window.document.createElement("a");
      link.href = url;
      link.download = `${document.document_number.replaceAll("/", "-")}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (exc) {
      setError(errorMessage(exc, "Nie udało się pobrać dokumentu PDF."));
    } finally {
      setDownloadingDocumentId(null);
    }
  }

  return (
    <section className="warehouse-page">
      <header className="warehouse-header">
        <div>
          <span className="eyebrow">Gospodarka magazynowa</span>
          <h1>Magazyn</h1>
        </div>
        <div className="warehouse-header-actions">
          <button type="button" className="icon-command" title="Odśwież" onClick={() => void loadWarehouseData()}>
            <RefreshCw size={18} />
            Odśwież
          </button>
          {user?.role === "ADMIN" && (
            <button
              type="button"
              className="admin-primary"
              onClick={() => {
                setEditingWarehouseId(null);
                setWarehouseName("");
                setWarehouseDefault(false);
                setModal("WAREHOUSE");
              }}
            >
              <Plus size={18} />
              Nowy magazyn
            </button>
          )}
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}
      {notice && <div className="form-notice">{notice}</div>}

      {warehouses.length === 0 && !isLoading ? (
        <div className="warehouse-empty">
          <PackagePlus size={36} />
          <h2>Brak dostępnych magazynów</h2>
          <p>Administrator może utworzyć pierwszy magazyn i nadać do niego dostęp.</p>
        </div>
      ) : (
        <>
          <div className="warehouse-tabs" role="tablist" aria-label="Magazyny">
            {warehouses.map((warehouse) => (
              <button
                key={warehouse.id}
                type="button"
                className={warehouse.id === selectedWarehouseId ? "active" : ""}
                onClick={() => setSelectedWarehouseId(warehouse.id)}
              >
                {warehouse.name}
                {warehouse.is_default && <small>domyślny</small>}
              </button>
            ))}
          </div>

          {selectedWarehouse && (
            <>
              <div className="warehouse-toolbar">
                <button type="button" onClick={() => openDocumentModal("PZ")}>
                  <PackagePlus size={18} /> Przyjęcie PZ
                </button>
                <button
                  type="button"
                  disabled={warehouses.filter((warehouse) => warehouse.is_active).length < 2}
                  onClick={() => openDocumentModal("MM")}
                >
                  <ArrowRightLeft size={18} /> Przesunięcie MM
                </button>
                <button type="button" className="danger-outline" onClick={() => openDocumentModal("RW")}>
                  <ClipboardMinus size={18} /> Rozchód / odpis RW
                </button>
                <button type="button" onClick={() => void openInventory()}>
                  <ClipboardCheck size={18} /> Inwentaryzacja
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setEditingItem(null);
                    setNewIngredientId(null);
                    setNewMinimum("");
                    setModal("ITEM");
                  }}
                >
                  <Plus size={18} /> Dodaj towar
                </button>
                {user?.role === "ADMIN" && (
                  <button type="button" onClick={() => void openAccess()}>
                    <ShieldCheck size={18} /> Dostęp pracowników
                  </button>
                )}
              </div>

              {lowStockItems.length > 0 && (
                <div className="low-stock-alert">
                  <TriangleAlert size={20} />
                  <strong>Niski stan:</strong>
                  {lowStockItems.map((item) => item.ingredient_name).join(", ")}
                </div>
              )}

              <div className="warehouse-content-grid">
                <section className="warehouse-section">
                  <div className="warehouse-section-heading">
                    <div>
                      <span className="eyebrow">Stan bieżący</span>
                      <h2>{selectedWarehouse.name}</h2>
                    </div>
                    {user?.role === "ADMIN" && (
                      <div className="warehouse-admin-actions">
                        <button
                          type="button"
                          className="icon-command"
                          disabled={selectedWarehouse.is_default}
                          onClick={() => void runSave(async () => {
                            await updateWarehouse(token as string, selectedWarehouse.id, {
                              is_default: !selectedWarehouse.is_default,
                            });
                            await loadWarehouses();
                          })}
                        >
                          <Settings size={16} />
                          {selectedWarehouse.is_default ? "Magazyn domyślny" : "Ustaw jako domyślny"}
                        </button>
                        <button
                          type="button"
                          className="icon-command warehouse-edit-button"
                          onClick={() => {
                            setEditingWarehouseId(selectedWarehouse.id);
                            setWarehouseName(selectedWarehouse.name);
                            setWarehouseDefault(selectedWarehouse.is_default);
                            setModal("WAREHOUSE");
                          }}
                        >
                          <Pencil size={16} /> Edytuj
                        </button>
                        <button
                          type="button"
                          className="icon-command warehouse-delete-button"
                          onClick={() => void removeWarehouse(selectedWarehouse)}
                        >
                          <Trash2 size={16} /> Usuń
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="stock-table">
                    <div className="stock-table-heading">
                      <span>Towar</span><span>Stan</span><span>Minimum</span><span>Status</span><span>Akcje</span>
                    </div>
                    {items.map((item) => (
                      <div key={item.id} className={`stock-table-row ${item.is_low_stock ? "low" : ""}`}>
                        <strong>{item.ingredient_name}</strong>
                        <span>{number.format(Number(item.quantity))} {item.unit}</span>
                        <span>{item.minimum_quantity === null ? "brak" : `${number.format(Number(item.minimum_quantity))} ${item.unit}`}</span>
                        <span className={item.is_low_stock ? "stock-status low" : "stock-status ok"}>
                          {item.is_low_stock ? "Niski stan" : "OK"}
                        </span>
                        <div className="stock-row-actions">
                          <button
                            type="button"
                            className="stock-edit-button"
                            title="Edytuj towar"
                            onClick={() => {
                              setEditingItem(item);
                              setItemName(item.ingredient_name);
                              setItemUnit(item.unit);
                              setNewMinimum(item.minimum_quantity ?? "");
                              setModal("ITEM");
                            }}
                          >
                            <Pencil size={16} />
                          </button>
                          <button
                            type="button"
                            className="stock-delete-button"
                            title="Usuń towar"
                            onClick={() => void removeItem(item)}
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </div>
                    ))}
                    {items.length === 0 && <p className="warehouse-list-empty">Brak towarów w magazynie.</p>}
                  </div>
                </section>

                <section className="warehouse-section">
                  <div className="warehouse-section-heading">
                    <div>
                      <span className="eyebrow">Ewidencja</span>
                      <h2>Dokumenty magazynowe</h2>
                    </div>
                  </div>
                  <div className="warehouse-document-list">
                    {documents.map((document) => (
                      <article 
                        key={document.id}
                        onClick={() => setViewingDocument(document)}
                        style={{ cursor: "pointer" }}
                      >
                        <div>
                          <strong>{document.document_number}</strong>
                          <small>{document.operation_date} · {document.issued_by_name ?? "system"}</small>
                        </div>
                        <span>{document.source_warehouse_name ?? "—"}</span>
                        <ArrowRightLeft size={16} aria-hidden="true" />
                        <span>{document.destination_warehouse_name ?? "—"}</span>
                        <b>{document.items.length} poz.</b>
                      </article>
                    ))}
                    {documents.length === 0 && <p className="warehouse-list-empty">Brak dokumentów.</p>}
                  </div>
                </section>
              </div>
            </>
          )}
        </>
      )}

      {modal !== null && (
        <div className="admin-modal-backdrop">
          <section className="admin-modal warehouse-modal">
            <button type="button" className="modal-close-icon" title="Zamknij" onClick={() => setModal(null)}>
              <X size={20} />
            </button>
            {modal === "WAREHOUSE" && (
              <>
                <h2>{editingWarehouseId === null ? "Nowy magazyn" : "Edytuj magazyn"}</h2>
                <label>Nazwa<input value={warehouseName} onChange={(event) => setWarehouseName(event.target.value)} /></label>
                <label className="switch-row compact">
                  <input type="checkbox" checked={warehouseDefault} onChange={(event) => setWarehouseDefault(event.target.checked)} />
                  Magazyn domyślny dla automatycznego rozchodu
                </label>
                <ModalActions saving={isSaving} onCancel={() => setModal(null)} onSave={() => void saveWarehouse()} />
              </>
            )}
            {modal === "ITEM" && (
              <>
                <h2>{editingItem === null ? "Dodaj towar" : "Edytuj towar"}</h2>
                {editingItem === null ? (
                  <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                    Składnik
                    <SearchableSelect
                      value={newIngredientId}
                      options={availableIngredients.filter((ingredient) => !items.some((item) => item.ingredient_id === ingredient.id))}
                      placeholder="Wybierz składnik"
                      onChange={setNewIngredientId}
                    />
                  </label>
                ) : (
                  <>
                    <label>Nazwa towaru<input value={itemName} onChange={(event) => setItemName(event.target.value)} /></label>
                    <label>Jednostka<input value={itemUnit} onChange={(event) => setItemUnit(event.target.value)} /></label>
                    <p className="field-help">Nazwa i jednostka należą do wspólnego składnika, więc ich zmiana będzie widoczna także w menu i innych magazynach.</p>
                  </>
                )}
                <label>Minimalny stan<input type="number" min="0" step="0.001" value={newMinimum} onChange={(event) => setNewMinimum(event.target.value)} /></label>
                {editingItem === null && <p className="field-help">Ilość początkowa wynosi 0. Przyjęcie ilości wykonaj dokumentem PZ.</p>}
                <ModalActions
                  saving={isSaving}
                  onCancel={() => setModal(null)}
                  onSave={() => void (editingItem === null ? addItem() : saveItem())}
                />
              </>
            )}
            {(modal === "PZ" || modal === "MM" || modal === "RW") && (
              <>
                <h2>{modalTitle(modal)}</h2>
                <div className="warehouse-document-meta">
                  <label>Data operacji<input type="date" value={operationDate} onChange={(event) => setOperationDate(event.target.value)} /></label>
                  {modal === "MM" && (
                    <label>
                      Magazyn docelowy
                      <select value={destinationWarehouseId ?? ""} onChange={(event) => setDestinationWarehouseId(Number(event.target.value) || null)}>
                        <option value="">Wybierz magazyn</option>
                        {warehouses.filter((warehouse) => warehouse.id !== selectedWarehouseId && warehouse.is_active).map((warehouse) => (
                          <option key={warehouse.id} value={warehouse.id}>{warehouse.name}</option>
                        ))}
                      </select>
                    </label>
                  )}
                  {modal === "RW" && (
                    <label className="wide">Powód rozchodu / odpisu<textarea value={reason} onChange={(event) => setReason(event.target.value)} /></label>
                  )}
                  <label className="wide">Uwagi<textarea value={description} onChange={(event) => setDescription(event.target.value)} /></label>
                </div>
                <DocumentLines
                  lines={documentLines}
                  ingredients={availableIngredients}
                  showPrice={modal === "PZ"}
                  onChange={setDocumentLines}
                />
                <ModalActions saving={isSaving} onCancel={() => setModal(null)} onSave={() => void saveDocument()} />
              </>
            )}
            {modal === "INVENTORY" && inventorySheet && (
              <>
                <div className="inventory-modal-heading">
                  <div>
                    <span className="eyebrow">Arkusz spisu z natury</span>
                    <h2>Inwentaryzacja · {inventorySheet.warehouse_name}</h2>
                  </div>
                  <small>Stan na moment otwarcia: {formatDateTime(inventorySheet.generated_at)}</small>
                </div>
                <div className="warehouse-document-meta">
                  <label>
                    Data inwentaryzacji
                    <input type="date" value={operationDate} onChange={(event) => setOperationDate(event.target.value)} />
                  </label>
                  <label>
                    Rodzaj / podstawa
                    <select value={reason} onChange={(event) => setReason(event.target.value)}>
                      <option>Inwentaryzacja okresowa</option>
                      <option>Inwentaryzacja doraźna</option>
                      <option>Inwentaryzacja kontrolna</option>
                      <option>Zmiana osoby odpowiedzialnej</option>
                    </select>
                  </label>
                  <label className="wide">
                    Uwagi komisji / osoby dokonującej spisu
                    <textarea value={description} onChange={(event) => setDescription(event.target.value)} />
                  </label>
                </div>
                <InventoryLines lines={inventoryLines} onChange={setInventoryLines} />
                <ModalActions saving={isSaving} onCancel={() => setModal(null)} onSave={() => void saveInventory()} />
              </>
            )}
            {modal === "ACCESS" && (
              <>
                <h2>Dostęp pracowników</h2>
                <div className="warehouse-access-list">
                  {accessUsers.map((employee) => (
                    <label key={employee.id} className={!employee.is_active ? "inactive" : ""}>
                      <input
                        type="checkbox"
                        checked={employee.has_access}
                        disabled={!employee.is_active}
                        onChange={(event) => setAccessUsers((current) => current.map((item) => (
                          item.id === employee.id ? { ...item, has_access: event.target.checked } : item
                        )))}
                      />
                      <span><strong>{employee.first_name} {employee.last_name}</strong><small>{employee.role}</small></span>
                    </label>
                  ))}
                </div>
                <ModalActions saving={isSaving} onCancel={() => setModal(null)} onSave={() => void saveAccess()} />
              </>
            )}
          </section>
        </div>
      )}

      {viewingDocument && (
        <div className="admin-modal-backdrop" onClick={() => setViewingDocument(null)}>
          <section 
            className="admin-modal warehouse-modal" 
            style={{
              maxWidth: viewingDocument.document_type === "INW" ? "1000px" : "600px",
              width: "100%",
              padding: "24px",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <button 
              type="button" 
              className="modal-close-icon" 
              title="Zamknij" 
              onClick={() => setViewingDocument(null)}
            >
              <X size={20} />
            </button>
            <h2>Szczegóły dokumentu: {viewingDocument.document_number}</h2>
            <div className="warehouse-document-meta" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "20px", marginTop: "16px" }}>
              <div>
                <strong>Typ dokumentu:</strong> {viewingDocument.document_type}
              </div>
              <div>
                <strong>Status:</strong> {viewingDocument.status}
              </div>
              <div>
                <strong>Magazyn źródłowy:</strong> {viewingDocument.source_warehouse_name ?? "—"}
              </div>
              <div>
                <strong>Magazyn docelowy:</strong> {viewingDocument.destination_warehouse_name ?? "—"}
              </div>
              <div>
                <strong>Wystawił:</strong> {viewingDocument.issued_by_name ?? "system"}
              </div>
              <div>
                <strong>Data operacji:</strong> {viewingDocument.operation_date}
              </div>
              {viewingDocument.reason && (
                <div style={{ gridColumn: "1 / -1" }}>
                  <strong>{viewingDocument.document_type === "INW" ? "Rodzaj / podstawa:" : "Powód RW:"}</strong> {viewingDocument.reason}
                </div>
              )}
              {viewingDocument.description && (
                <div style={{ gridColumn: "1 / -1" }}>
                  <strong>Uwagi:</strong> {viewingDocument.description}
                </div>
              )}
            </div>

            <h3 style={{ margin: "20px 0 10px 0" }}>Pozycje dokumentu</h3>
            <div style={{ maxHeight: "350px", overflow: "auto", border: "1px solid #edf2f7", borderRadius: "8px", padding: "8px", background: "rgba(0,0,0,0.01)" }}>
              <table style={{ width: "100%", minWidth: viewingDocument.document_type === "INW" ? "820px" : undefined, borderCollapse: "collapse", fontSize: "0.9rem" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #cbd5e0", textAlign: "left" }}>
                    <th style={{ padding: "6px" }}>Towar</th>
                    {viewingDocument.document_type === "INW" ? (
                      <>
                        <th style={{ padding: "6px", textAlign: "right" }}>Stan księgowy</th>
                        <th style={{ padding: "6px", textAlign: "right" }}>Stan faktyczny</th>
                        <th style={{ padding: "6px", textAlign: "right" }}>Różnica</th>
                        <th style={{ padding: "6px", textAlign: "right" }}>Cena jedn.</th>
                        <th style={{ padding: "6px", textAlign: "right" }}>Wartość różnicy</th>
                      </>
                    ) : (
                      <>
                        <th style={{ padding: "6px", textAlign: "right" }}>Ilość</th>
                        {viewingDocument.document_type === "PZ" && (
                          <>
                            <th style={{ padding: "6px", textAlign: "right" }}>Cena jedn.</th>
                            <th style={{ padding: "6px", textAlign: "right" }}>Wartość</th>
                          </>
                        )}
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {viewingDocument.items.map((item) => (
                    <tr key={item.id} style={{ borderBottom: "1px solid #edf2f7" }}>
                      <td style={{ padding: "6px" }}>{item.ingredient_name}</td>
                      {viewingDocument.document_type === "INW" ? (
                        <>
                          <td style={{ padding: "6px", textAlign: "right" }}>{formatQuantity(item.book_quantity, item.unit)}</td>
                          <td style={{ padding: "6px", textAlign: "right" }}>{formatQuantity(item.actual_quantity, item.unit)}</td>
                          <td style={{ padding: "6px", textAlign: "right" }}>{formatSignedQuantity(item.difference_quantity, item.unit)}</td>
                          <td style={{ padding: "6px", textAlign: "right" }}>
                            {item.unit_price ? `${number.format(Number(item.unit_price))} PLN` : "—"}
                          </td>
                          <td style={{ padding: "6px", textAlign: "right" }}>
                            {formatSignedMoney(item.difference_value)}
                          </td>
                        </>
                      ) : (
                        <>
                          <td style={{ padding: "6px", textAlign: "right" }}>{number.format(Number(item.quantity))} {item.unit}</td>
                          {viewingDocument.document_type === "PZ" && (
                            <>
                              <td style={{ padding: "6px", textAlign: "right" }}>
                                {item.unit_price ? `${number.format(Number(item.unit_price))} PLN` : "—"}
                              </td>
                              <td style={{ padding: "6px", textAlign: "right" }}>
                                {item.total_value ? `${number.format(Number(item.total_value))} PLN` : "—"}
                              </td>
                            </>
                          )}
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "20px" }}>
              <button type="button" className="ghost-button" onClick={() => setViewingDocument(null)}>
                Zamknij
              </button>
              <button
                type="button"
                className="admin-primary"
                disabled={downloadingDocumentId === viewingDocument.id}
                onClick={() => void downloadDocument(viewingDocument)}
              >
                <Download size={17} />
                {downloadingDocumentId === viewingDocument.id ? "Generowanie..." : "Pobierz PDF"}
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

function InventoryLines({
  lines,
  onChange,
}: {
  lines: InventoryLineForm[];
  onChange: (lines: InventoryLineForm[]) => void;
}) {
  const summary = lines.reduce(
    (total, line) => {
      const unitPrice = parseDecimal(line.unit_price);
      const book = parseDecimal(line.book_quantity);
      const actual = parseDecimal(line.actual_quantity);
      return {
        bookValue: total.bookValue + book * unitPrice,
        actualValue: total.actualValue + actual * unitPrice,
      };
    },
    { bookValue: 0, actualValue: 0 },
  );

  return (
    <div className="inventory-sheet">
      <div className="inventory-sheet-scroll">
        <div className="inventory-line inventory-line-header">
          <span>Lp.</span>
          <span>Towar</span>
          <span>Jedn.</span>
          <span>Stan księgowy</span>
          <span>Stan faktyczny</span>
          <span>Różnica</span>
          <span>Cena jedn.</span>
          <span>Wartość faktyczna</span>
        </div>
        {lines.map((line, index) => {
          const difference = line.actual_quantity.trim() === ""
            ? null
            : parseDecimal(line.actual_quantity) - parseDecimal(line.book_quantity);
          const actualValue = parseDecimal(line.actual_quantity) * parseDecimal(line.unit_price);
          return (
            <div className="inventory-line" key={line.stock_item_id}>
              <span>{index + 1}</span>
              <strong>{line.ingredient_name}</strong>
              <span>{line.unit}</span>
              <span>{number.format(parseDecimal(line.book_quantity))}</span>
              <input
                type="number"
                min="0"
                step="0.001"
                value={line.actual_quantity}
                placeholder="Wpisz ilość"
                aria-label={`Stan faktyczny: ${line.ingredient_name}`}
                onChange={(event) => updateInventoryLine(lines, index, { actual_quantity: event.target.value }, onChange)}
              />
              <span className={difference === null ? "" : difference < 0 ? "inventory-negative" : difference > 0 ? "inventory-positive" : ""}>
                {difference === null ? "—" : signedNumber(difference)}
              </span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={line.unit_price}
                placeholder="0,00"
                aria-label={`Cena jednostkowa: ${line.ingredient_name}`}
                onChange={(event) => updateInventoryLine(lines, index, { unit_price: event.target.value }, onChange)}
              />
              <span>{money.format(actualValue)}</span>
            </div>
          );
        })}
      </div>
      <div className="inventory-summary">
        <span>Wartość księgowa <strong>{money.format(summary.bookValue)}</strong></span>
        <span>Wartość faktyczna <strong>{money.format(summary.actualValue)}</strong></span>
        <span>Różnica <strong className={summary.actualValue < summary.bookValue ? "inventory-negative" : "inventory-positive"}>{formatSignedMoney(String(summary.actualValue - summary.bookValue))}</strong></span>
      </div>
      <p className="field-help">Wpisz wynik rzeczywistego liczenia, ważenia lub mierzenia każdego towaru. Stan księgowy jest tylko punktem odniesienia.</p>
    </div>
  );
}

function DocumentLines({
  lines,
  ingredients,
  showPrice,
  onChange,
}: {
  lines: DocumentLineForm[];
  ingredients: StockIngredient[];
  showPrice: boolean;
  onChange: (lines: DocumentLineForm[]) => void;
}) {
  return (
    <div className="warehouse-document-lines">
      <div className="warehouse-document-lines-heading">
        <h3>Pozycje dokumentu</h3>
        <button type="button" className="icon-command" onClick={() => onChange([...lines, emptyLine()])}>
          <Plus size={16} /> Dodaj pozycję
        </button>
      </div>
      {lines.map((line, index) => {
        const ingredient = ingredients.find((item) => item.id === line.ingredient_id);
        return (
          <div key={line.key} className="warehouse-document-line">
            <SearchableSelect
              value={line.ingredient_id}
              options={ingredients}
              placeholder="Wybierz towar"
              onChange={(val) => updateLine(lines, index, { ...line, ingredient_id: val }, onChange)}
            />
            <label>
              <input type="number" min="0.001" step="0.001" value={line.quantity} onChange={(event) => updateLine(lines, index, { ...line, quantity: event.target.value }, onChange)} placeholder="Ilość" />
              <small>{ingredient?.unit ?? "jedn."}</small>
            </label>
            {showPrice && <input type="number" min="0" step="0.01" value={line.unit_price} onChange={(event) => updateLine(lines, index, { ...line, unit_price: event.target.value }, onChange)} placeholder="Cena jedn. (opcjonalnie)" />}
            <button type="button" className="remove-line" title="Usuń pozycję" disabled={lines.length === 1} onClick={() => onChange(lines.filter((_, itemIndex) => itemIndex !== index))}>
              <Trash2 size={18} />
            </button>
          </div>
        );
      })}
    </div>
  );
}

function ModalActions({ saving, onCancel, onSave }: { saving: boolean; onCancel: () => void; onSave: () => void }) {
  return (
    <div className="admin-form-actions">
      <button type="button" className="ghost-button" onClick={onCancel}>Anuluj</button>
      <button type="button" className="admin-primary" disabled={saving} onClick={onSave}>
        {saving ? "Zapisywanie..." : "Zapisz"}
      </button>
    </div>
  );
}

function emptyLine(): DocumentLineForm {
  lineKey += 1;
  return { key: lineKey, ingredient_id: null, quantity: "", unit_price: "" };
}

function updateLine(lines: DocumentLineForm[], index: number, line: DocumentLineForm, onChange: (lines: DocumentLineForm[]) => void) {
  onChange(lines.map((item, itemIndex) => itemIndex === index ? line : item));
}

function updateInventoryLine(
  lines: InventoryLineForm[],
  index: number,
  patch: Partial<InventoryLineForm>,
  onChange: (lines: InventoryLineForm[]) => void,
) {
  onChange(lines.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
}

function parseDecimal(value: string): number {
  const parsed = Number(value.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : 0;
}

function normalizeDecimal(value: string): string {
  return value.trim().replace(",", ".");
}

function isNonNegativeNumber(value: string): boolean {
  const parsed = Number(normalizeDecimal(value));
  return Number.isFinite(parsed) && parsed >= 0;
}

function signedNumber(value: number): string {
  if (value === 0) return "0";
  return `${value > 0 ? "+" : ""}${number.format(value)}`;
}

function formatQuantity(value: string | null, unit: string): string {
  return value === null ? "—" : `${number.format(Number(value))} ${unit}`;
}

function formatSignedQuantity(value: string | null, unit: string): string {
  if (value === null) return "—";
  return `${signedNumber(Number(value))} ${unit}`;
}

function formatSignedMoney(value: string | null): string {
  if (value === null) return "—";
  const parsed = Number(value);
  return `${parsed > 0 ? "+" : ""}${money.format(parsed)}`;
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("pl-PL", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function today(): string {
  const current = new Date();
  const local = new Date(current.getTime() - current.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

function modalTitle(kind: "PZ" | "MM" | "RW"): string {
  if (kind === "PZ") return "Przyjęcie zewnętrzne (PZ)";
  if (kind === "MM") return "Przesunięcie międzymagazynowe (MM)";
  return "Rozchód / odpis (RW)";
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return fallback;
}

function SearchableSelect({
  value,
  options,
  placeholder,
  onChange,
}: {
  value: number | null;
  options: { id: number; name: string; unit: string }[];
  placeholder: string;
  onChange: (id: number | null) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedOption = options.find((opt) => opt.id === value);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredOptions = options.filter((opt) =>
    opt.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div ref={containerRef} className="searchable-select-container" style={{ position: "relative", width: "100%" }}>
      <div
        className="searchable-select-trigger"
        onClick={() => {
          setIsOpen(!isOpen);
          setSearch("");
        }}
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "8px 12px",
          border: "1px solid #cbd5e0",
          borderRadius: "6px",
          background: "#fff",
          cursor: "pointer",
          userSelect: "none",
          minHeight: "38px"
        }}
      >
        <span>{selectedOption ? `${selectedOption.name} (${selectedOption.unit})` : placeholder}</span>
        <span style={{ fontSize: "0.8rem", color: "#718096" }}>▼</span>
      </div>

      {isOpen && (
        <div
          className="searchable-select-dropdown"
          style={{
            position: "absolute",
            top: "105%",
            left: 0,
            right: 0,
            zIndex: 100,
            background: "#fff",
            border: "1px solid #cbd5e0",
            borderRadius: "6px",
            boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.1)",
            maxHeight: "240px",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden"
          }}
        >
          <input
            autoFocus
            type="text"
            placeholder="Szukaj..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              width: "100%",
              padding: "8px 12px",
              border: "none",
              borderBottom: "1px solid #e2e8f0",
              outline: "none"
            }}
          />
          <div style={{ overflowY: "auto", flex: 1 }}>
            {filteredOptions.length > 0 ? (
              filteredOptions.map((opt) => (
                <div
                  key={opt.id}
                  onClick={() => {
                    onChange(opt.id);
                    setIsOpen(false);
                  }}
                  style={{
                    padding: "8px 12px",
                    cursor: "pointer",
                    background: opt.id === value ? "#edf2f7" : "#fff",
                    fontWeight: opt.id === value ? "bold" : "normal"
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#f7fafc")}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = opt.id === value ? "#edf2f7" : "#fff")}
                >
                  {opt.name} ({opt.unit})
                </div>
              ))
            ) : (
              <div style={{ padding: "8px 12px", color: "#a0aec0", textAlign: "center" }}>Brak wyników</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
