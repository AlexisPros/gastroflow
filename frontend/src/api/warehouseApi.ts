import { apiBlobRequest, apiRequest } from "./apiClient";

export type Warehouse = {
  id: number;
  name: string;
  type: string;
  is_active: boolean;
  is_default: boolean;
};

export type StockIngredient = {
  id: number;
  name: string;
  unit: string;
  is_active: boolean;
};

export type WarehouseStockItem = {
  id: number;
  warehouse_id: number;
  ingredient_id: number;
  ingredient_name: string;
  unit: string;
  quantity: string;
  minimum_quantity: string | null;
  is_low_stock: boolean;
  is_active: boolean;
};

export type WarehouseAccessUser = {
  id: number;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
  has_access: boolean;
};

export type WarehouseDocumentLine = {
  ingredient_id: number;
  quantity: string;
  unit_price: string | null;
};

export type WarehouseDocument = {
  id: number;
  document_number: string;
  document_type: string;
  status: string;
  source_warehouse_id: number | null;
  source_warehouse_name: string | null;
  destination_warehouse_id: number | null;
  destination_warehouse_name: string | null;
  order_id: number | null;
  issued_by_user_id: number | null;
  issued_by_name: string | null;
  operation_date: string;
  issued_at: string;
  reason: string | null;
  description: string | null;
  items: Array<{
    id: number;
    ingredient_id: number;
    ingredient_name: string;
    quantity: string;
    unit: string;
    unit_price: string | null;
    total_value: string | null;
    book_quantity: string | null;
    actual_quantity: string | null;
    difference_quantity: string | null;
    difference_value: string | null;
  }>;
};

export type InventorySheetItem = {
  stock_item_id: number;
  ingredient_id: number;
  ingredient_name: string;
  unit: string;
  book_quantity: string;
  suggested_unit_price: string | null;
};

export type InventorySheet = {
  warehouse_id: number;
  warehouse_name: string;
  generated_at: string;
  items: InventorySheetItem[];
};

export async function getWarehouses(token: string): Promise<Warehouse[]> {
  return apiRequest<Warehouse[]>("/stock/warehouses", { token });
}

export async function createWarehouse(
  token: string,
  body: { name: string; is_default: boolean },
): Promise<Warehouse> {
  return apiRequest<Warehouse>("/stock/warehouses", { method: "POST", token, body });
}

export async function updateWarehouse(
  token: string,
  warehouseId: number,
  body: Partial<Pick<Warehouse, "name" | "is_active" | "is_default">>,
): Promise<Warehouse> {
  return apiRequest<Warehouse>(`/stock/warehouses/${warehouseId}`, {
    method: "PATCH",
    token,
    body,
  });
}

export async function deleteWarehouse(token: string, warehouseId: number): Promise<Warehouse> {
  return apiRequest<Warehouse>(`/stock/warehouses/${warehouseId}`, {
    method: "DELETE",
    token,
  });
}

export async function getStockIngredients(token: string): Promise<StockIngredient[]> {
  return apiRequest<StockIngredient[]>("/stock/ingredients", { token });
}

export async function getWarehouseItems(
  token: string,
  warehouseId: number,
): Promise<WarehouseStockItem[]> {
  return apiRequest<WarehouseStockItem[]>(`/stock/warehouses/${warehouseId}/items`, { token });
}

export async function addWarehouseItem(
  token: string,
  warehouseId: number,
  body: { ingredient_id: number; minimum_quantity: string | null },
): Promise<WarehouseStockItem> {
  return apiRequest<WarehouseStockItem>(`/stock/warehouses/${warehouseId}/items`, {
    method: "POST",
    token,
    body,
  });
}

export async function updateStockThreshold(
  token: string,
  stockItemId: number,
  minimumQuantity: string | null,
): Promise<WarehouseStockItem> {
  return apiRequest<WarehouseStockItem>(`/stock/items/${stockItemId}/threshold`, {
    method: "PATCH",
    token,
    body: { minimum_quantity: minimumQuantity },
  });
}

export async function updateWarehouseItem(
  token: string,
  stockItemId: number,
  body: {
    ingredient_name?: string;
    unit?: string;
    minimum_quantity?: string | null;
  },
): Promise<WarehouseStockItem> {
  return apiRequest<WarehouseStockItem>(`/stock/items/${stockItemId}`, {
    method: "PATCH",
    token,
    body,
  });
}

export async function deleteWarehouseItem(
  token: string,
  stockItemId: number,
): Promise<WarehouseStockItem> {
  return apiRequest<WarehouseStockItem>(`/stock/items/${stockItemId}`, {
    method: "DELETE",
    token,
  });
}

export async function getWarehouseDocuments(
  token: string,
  warehouseId: number,
): Promise<WarehouseDocument[]> {
  return apiRequest<WarehouseDocument[]>(`/stock/documents?warehouse_id=${warehouseId}`, { token });
}

export async function downloadWarehouseDocumentPdf(
  token: string,
  documentId: number,
): Promise<Blob> {
  return apiBlobRequest(`/stock/documents/${documentId}/pdf`, { token });
}

export async function createReceiptDocument(
  token: string,
  body: {
    warehouse_id: number;
    operation_date: string;
    description: string | null;
    items: WarehouseDocumentLine[];
  },
): Promise<WarehouseDocument> {
  return apiRequest<WarehouseDocument>("/stock/documents/receipts", {
    method: "POST",
    token,
    body,
  });
}

export async function createTransferDocument(
  token: string,
  body: {
    source_warehouse_id: number;
    destination_warehouse_id: number;
    operation_date: string;
    description: string | null;
    items: WarehouseDocumentLine[];
  },
): Promise<WarehouseDocument> {
  return apiRequest<WarehouseDocument>("/stock/documents/transfers", {
    method: "POST",
    token,
    body,
  });
}

export async function createWriteOffDocument(
  token: string,
  body: {
    warehouse_id: number;
    operation_date: string;
    reason: string;
    description: string | null;
    items: WarehouseDocumentLine[];
  },
): Promise<WarehouseDocument> {
  return apiRequest<WarehouseDocument>("/stock/documents/write-offs", {
    method: "POST",
    token,
    body,
  });
}

export async function getInventorySheet(
  token: string,
  warehouseId: number,
): Promise<InventorySheet> {
  return apiRequest<InventorySheet>(`/stock/warehouses/${warehouseId}/inventory-sheet`, {
    token,
  });
}

export async function createInventoryDocument(
  token: string,
  body: {
    warehouse_id: number;
    operation_date: string;
    reason: string;
    description: string | null;
    items: Array<{
      stock_item_id: number;
      book_quantity: string;
      actual_quantity: string;
      unit_price: string;
    }>;
  },
): Promise<WarehouseDocument> {
  return apiRequest<WarehouseDocument>("/stock/documents/inventory", {
    method: "POST",
    token,
    body,
  });
}

export async function getWarehouseAccess(
  token: string,
  warehouseId: number,
): Promise<WarehouseAccessUser[]> {
  return apiRequest<WarehouseAccessUser[]>(`/stock/warehouses/${warehouseId}/access`, { token });
}

export async function updateWarehouseAccess(
  token: string,
  warehouseId: number,
  userIds: number[],
): Promise<WarehouseAccessUser[]> {
  return apiRequest<WarehouseAccessUser[]>(`/stock/warehouses/${warehouseId}/access`, {
    method: "PUT",
    token,
    body: { user_ids: userIds },
  });
}
