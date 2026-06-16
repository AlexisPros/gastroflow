import { apiBlobRequest, apiRequest } from "./apiClient";
import type { RestaurantTable, RestaurantTableStatus } from "./floorPlanApi";

export type ProductCategory = {
  id: number;
  parent_category_id: number | null;
  name: string;
  department: "KITCHEN" | "BAR";
  is_active: boolean;
};

export type Product = {
  id: number;
  category_id: number;
  kitchen_section_id: number | null;
  name: string;
  description: string | null;
  image_url: string | null;
  price: string;
  vat_rate: string;
  preparation_time: number | null;
  is_active: boolean;
  created_at: string;
};

export type Order = {
  id: number;
  version: number;
  idempotency_key: string | null;
  table_id: number | null;
  waiter_id: number | null;
  discount_id: number | null;
  shift_id: number | null;
  split_parent_order_id: number | null;
  split_sequence: number | null;
  guest_count: number | null;
  source: string;
  status: string;
  total_amount: string;
  subtotal_amount: string;
  discount_amount: string;
  tip_amount: string;
  estimated_time: number | null;
  closed_at: string | null;
  created_at: string;
};

export type Modifier = {
  id: number;
  name: string;
  price: string;
  is_active: boolean;
};

export type ProductModifier = {
  id: number;
  product_id: number;
  modifier_id: number;
  price_override: string | null;
  is_active: boolean;
};

export type Discount = {
  id: number;
  name: string;
  type: string;
  value: string;
  is_active: boolean;
};

export type Payment = {
  id: number;
  order_id: number;
  idempotency_key: string | null;
  method: string;
  amount: string;
  cash_received: string | null;
  change_given: string | null;
  status: string;
  created_at: string;
};

export type ClosedPayment = {
  payment_id: number;
  order_id: number;
  table_id: number | null;
  method: "CARD" | "CASH";
  amount: string;
  closed_at: string | null;
};

export type Invoice = {
  id: number;
  order_id: number;
  nip: string;
  company_name: string;
  invoice_number: string;
  status: string;
  created_at: string;
};

export type OrderItem = {
  id: number;
  order_id: number;
  product_id: number;
  quantity: number;
  position: number;
  course_number: number;
  unit_price: string;
  total_price: string;
  status: string;
  notes: string | null;
  modifiers?: Array<{
    name: string;
    price: string;
  }>;
};

export type PendingQrOrderItem = OrderItem & {
  modifiers: Array<{
    name: string;
    price: string;
  }>;
};

export type BillSplitOriginalItem = {
  id: number;
  product_id: number;
  product_name: string;
  quantity: string;
  assigned_quantity: string;
  remaining_quantity: string;
  unit_price: string;
  total_price: string;
  notes: string | null;
};

export type BillSegmentItem = {
  id: number;
  bill_segment_id: number;
  original_order_item_id: number;
  product_id: number;
  product_name: string;
  quantity: string;
  unit_price: string;
  total_price: string;
  notes: string | null;
  modifier_snapshot: string | null;
};

export type BillSegment = {
  id: number;
  order_id: number;
  name: string;
  position: number;
  status: string;
  total_amount: string;
  created_at: string;
  items: BillSegmentItem[];
};

export type BillSplitView = {
  order_id: number;
  original_items: BillSplitOriginalItem[];
  segments: BillSegment[];
  unassigned_total: string;
};

export type OrderMergeCandidate = {
  id: number;
  table_id: number | null;
  status: string;
  total_amount: string;
  created_at: string;
  item_count: number;
};

export type ActiveOrderWaiter = {
  id: number;
  first_name: string;
  last_name: string;
};

export type ActiveTransferWaiter = {
  id: number;
  first_name: string;
  last_name: string;
  open_orders_count: number;
};

export type OrderTransferLog = {
  id: number;
  order_id: number;
  from_waiter_id: number;
  to_waiter_id: number;
  transferred_at: string;
};

export type CartItem = {
  id: string;
  product: Product;
  quantity: number;
  position: number;
  courseNumber: number;
  notes?: string | null;
  productModifierIds: number[];
};

export type CartSeparator = {
  id: string;
  type: "SEPARATOR";
  nextCourseNumber: number;
};

export type CartEntry = CartItem | CartSeparator;

export async function getWaiterProducts(token: string): Promise<Product[]> {
  return apiRequest<Product[]>("/products?limit=500", { token });
}

export async function getProductCategories(token: string): Promise<ProductCategory[]> {
  return apiRequest<ProductCategory[]>("/product-categories?limit=500", { token });
}

export async function getModifiers(token: string): Promise<Modifier[]> {
  return apiRequest<Modifier[]>("/modifiers?limit=500", { token });
}

export async function getProductModifiers(token: string): Promise<ProductModifier[]> {
  return apiRequest<ProductModifier[]>("/product-modifiers?limit=1000", { token });
}

export async function getDiscounts(token: string): Promise<Discount[]> {
  return apiRequest<Discount[]>("/discounts?limit=500", { token });
}

export async function getWaiterTables(token: string): Promise<RestaurantTable[]> {
  return apiRequest<RestaurantTable[]>("/restaurant-tables?limit=500", { token });
}

export async function getWaiterOrders(token: string): Promise<Order[]> {
  return apiRequest<Order[]>("/orders/workspace", { token });
}

export async function getActiveOrderWaiters(token: string): Promise<ActiveOrderWaiter[]> {
  return apiRequest<ActiveOrderWaiter[]>("/orders/view/active-waiters", { token });
}

export async function getWaiterOrderItems(token: string): Promise<OrderItem[]> {
  return apiRequest<OrderItem[]>("/orders/workspace/items", { token });
}

export async function getPendingQrOrderItems(
  token: string,
  orderId: number,
): Promise<PendingQrOrderItem[]> {
  return apiRequest<PendingQrOrderItem[]>(`/qr/orders/${orderId}/items`, { token });
}

export async function createWaiterOrder(
  token: string,
  body: {
    table_id: number | null;
    waiter_id: number;
    guest_count: number | null;
    source: "WAITER";
    idempotency_key?: string | null;
    items: Array<{
      product_id: number;
      quantity: number;
      position: number;
      course_number: number;
      notes?: string | null;
      product_modifier_ids?: number[];
    }>;
  },
): Promise<Order> {
  return apiRequest<Order>("/orders/with-items", {
    method: "POST",
    token,
    body,
  });
}

export async function addItemsToWaiterOrder(
  token: string,
  orderId: number,
  body: {
    items: Array<{
      product_id: number;
      quantity: number;
      position: number;
      course_number: number;
      notes?: string | null;
      product_modifier_ids?: number[];
    }>;
  },
): Promise<Order> {
  return apiRequest<Order>(`/orders/${orderId}/items`, {
    method: "POST",
    token,
    body,
  });
}

export async function updateWaiterOrder(
  token: string,
  orderId: number,
  body: Partial<Pick<Order, "guest_count">>,
): Promise<Order> {
  return apiRequest<Order>(`/orders/${orderId}/guest-count`, {
    method: "PATCH",
    token,
    body,
  });
}

export async function changeWaiterOrderTable(
  token: string,
  orderId: number,
  tableId: number,
): Promise<Order> {
  return apiRequest<Order>(`/orders/${orderId}/table`, {
    method: "PATCH",
    token,
    body: { table_id: tableId },
  });
}

export async function splitWaiterOrder(
  token: string,
  orderId: number,
  orderItemIds: number[],
): Promise<Order> {
  return apiRequest<Order>(`/orders/${orderId}/split`, {
    method: "POST",
    token,
    body: {
      order_item_ids: orderItemIds,
    },
  });
}

export async function getWaiterBillSplit(
  token: string,
  orderId: number,
): Promise<BillSplitView> {
  return apiRequest<BillSplitView>(`/orders/${orderId}/bill-split`, { token });
}

export async function createWaiterBillSegment(
  token: string,
  orderId: number,
): Promise<BillSegment> {
  return apiRequest<BillSegment>(`/orders/${orderId}/bill-split/segments`, {
    method: "POST",
    token,
  });
}

export async function deleteWaiterBillSegment(
  token: string,
  orderId: number,
  segmentId: number,
): Promise<void> {
  return apiRequest<void>(`/orders/${orderId}/bill-split/segments/${segmentId}`, {
    method: "DELETE",
    token,
  });
}

export async function moveWaiterBillSplitItems(
  token: string,
  orderId: number,
  body: {
    target_segment_id: number;
    items: Array<{
      order_item_id: number;
      quantity?: string;
    }>;
  },
): Promise<BillSplitView> {
  return apiRequest<BillSplitView>(`/orders/${orderId}/bill-split/move-items`, {
    method: "POST",
    token,
    body,
  });
}

export async function splitWaiterBillSplitItem(
  token: string,
  orderId: number,
  body: {
    order_item_id: number;
    target_segment_ids: number[];
  },
): Promise<BillSplitView> {
  return apiRequest<BillSplitView>(`/orders/${orderId}/bill-split/split-item`, {
    method: "POST",
    token,
    body,
  });
}

export async function finalizeWaiterBillSplit(
  token: string,
  orderId: number,
  body: {
    segment_guest_counts: Array<{
      segment_id: number;
      guest_count: number;
    }>;
  },
): Promise<Order[]> {
  return apiRequest<Order[]>(`/orders/${orderId}/bill-split/finalize`, {
    method: "POST",
    token,
    body,
  });
}

export async function cancelWaiterOrder(
  token: string,
  orderId: number,
  managerPin: string,
): Promise<Order> {
  return apiRequest<Order>(`/orders/${orderId}/cancel`, {
    method: "POST",
    token,
    body: {
      manager_pin: managerPin,
    },
  });
}

export async function verifyManagerPin(
  token: string,
  managerPin: string,
): Promise<{ success: boolean }> {
  return apiRequest<{ success: boolean }>("/orders/manager-pin/verify", {
    method: "POST",
    token,
    body: {
      manager_pin: managerPin,
    },
  });
}

export async function voidWaiterOrderItem(
  token: string,
  orderId: number,
  orderItemId: number,
  managerPin?: string,
): Promise<Order> {
  return apiRequest<Order>(`/orders/${orderId}/items/${orderItemId}/void`, {
    method: "POST",
    token,
    body: {
      manager_pin: managerPin ?? null,
    },
  });
}

export async function applyDiscountToWaiterOrder(
  token: string,
  orderId: number,
  discountId: number,
): Promise<Order> {
  return apiRequest<Order>(`/orders/${orderId}/discount`, {
    method: "POST",
    token,
    body: {
      discount_id: discountId,
    },
  });
}

export async function removeDiscountFromWaiterOrder(
  token: string,
  orderId: number,
): Promise<Order> {
  return apiRequest<Order>(`/orders/${orderId}/discount`, {
    method: "DELETE",
    token,
  });
}

export async function updateWaiterOrderTip(
  token: string,
  orderId: number,
  tipAmount: string,
): Promise<Order> {
  return apiRequest<Order>(`/orders/${orderId}/tip`, {
    method: "PATCH",
    token,
    body: {
      tip_amount: tipAmount,
    },
  });
}

export async function registerWaiterPayment(
  token: string,
  orderId: number,
  body: {
    method: "CARD" | "CASH";
    amount: string;
    close_order: boolean;
  },
): Promise<Payment> {
  return apiRequest<Payment>(`/orders/${orderId}/payments`, {
    method: "POST",
    token,
    body,
  });
}

export type CloseOrderPaymentPart = {
  method: "CARD" | "CASH";
  amount: string;
  cash_received?: string | null;
  idempotency_key?: string | null;
};

export type CloseOrderWithPaymentsResponse = {
  order: Order;
  payments: Payment[];
  change_due: string;
};

export async function closeWaiterOrderWithPayments(
  token: string,
  orderId: number,
  payments: CloseOrderPaymentPart[],
): Promise<CloseOrderWithPaymentsResponse> {
  return apiRequest<CloseOrderWithPaymentsResponse>(
    `/orders/${orderId}/close-with-payments`,
    {
      method: "POST",
      token,
      body: { payments },
    },
  );
}

export async function getCurrentUserClosedPayments(token: string): Promise<ClosedPayment[]> {
  return apiRequest<ClosedPayment[]>("/payments/current-user/closed", { token });
}

export async function toggleWaiterPaymentMethod(
  token: string,
  paymentId: number,
  body: {
    reason: string;
    manager_pin?: string | null;
  },
): Promise<Payment> {
  return apiRequest<Payment>(`/payments/${paymentId}/toggle-method`, {
    method: "POST",
    token,
    body,
  });
}

export async function getPendingQrOrders(token: string): Promise<Order[]> {
  return apiRequest<Order[]>("/qr/orders/pending", { token });
}

export async function confirmPendingQrOrder(
  token: string,
  orderId: number,
  pin: string,
): Promise<Order> {
  return apiRequest<Order>(`/qr/orders/${orderId}/confirm`, {
    method: "POST",
    token,
    body: { pin },
  });
}

export async function rejectPendingQrOrder(
  token: string,
  orderId: number,
  pin: string,
  reason?: string | null,
): Promise<Order> {
  return apiRequest<Order>(`/qr/orders/${orderId}/reject`, {
    method: "POST",
    token,
    body: { pin, reason: reason ?? null },
  });
}

export async function createInvoiceForWaiterOrder(
  token: string,
  orderId: number,
  body: {
    nip: string;
    company_name: string;
  },
): Promise<Invoice> {
  return apiRequest<Invoice>(`/orders/${orderId}/invoice`, {
    method: "POST",
    token,
    body,
  });
}

export async function generateWaiterReceiptPdf(
  token: string,
  orderId: number,
): Promise<Blob> {
  return apiBlobRequest(`/orders/${orderId}/receipt/pdf`, {
    method: "POST",
    token,
    timeoutMs: 20000,
  });
}

export async function generateWaiterGuestCheckPdf(
  token: string,
  orderId: number,
): Promise<Blob> {
  return apiBlobRequest(`/orders/${orderId}/guest-check/pdf`, {
    method: "POST",
    token,
    timeoutMs: 20000,
  });
}

export function isOpenOrder(order: Order): boolean {
  return !["CLOSED", "CANCELLED", "REJECTED", "MERGED"].includes(order.status);
}

export function tableStatusLabel(status: RestaurantTableStatus): string {
  const labels: Record<string, string> = {
    FREE: "Free",
    PENDING_ORDER: "Pending QR",
    OCCUPIED: "Occupied",
    RESERVED: "Reserved",
  };

  return labels[status] ?? status;
}

export async function getWaiterMergeCandidates(
  token: string,
  targetOrderId: number,
): Promise<OrderMergeCandidate[]> {
  return apiRequest<OrderMergeCandidate[]>(`/orders/${targetOrderId}/merge-candidates`, { token });
}

export async function mergeWaiterOrder(
  token: string,
  targetOrderId: number,
  sourceOrderId: number,
): Promise<Order> {
  return apiRequest<Order>(`/orders/${targetOrderId}/merge`, {
    method: "POST",
    token,
    body: {
      source_order_id: sourceOrderId,
    },
  });
}

export async function getActiveTransferWaiters(
  token: string,
): Promise<ActiveTransferWaiter[]> {
  return apiRequest<ActiveTransferWaiter[]>("/orders/transfer/waiters", { token });
}

export async function getTransferableWaiterOrders(
  token: string,
  waiterId: number,
): Promise<Order[]> {
  return apiRequest<Order[]>(`/orders/transfer/waiters/${waiterId}`, { token });
}

export async function transferAllWaiterOrders(
  token: string,
  fromWaiterId: number,
): Promise<OrderTransferLog[]> {
  return apiRequest<OrderTransferLog[]>(`/orders/transfer/waiters/${fromWaiterId}/all`, {
    method: "POST",
    token,
  });
}

export async function transferWaiterOrderToCurrent(
  token: string,
  orderId: number,
  currentWaiterId: number,
): Promise<OrderTransferLog> {
  return apiRequest<OrderTransferLog>(`/orders/${orderId}/transfer`, {
    method: "POST",
    token,
    body: { to_waiter_id: currentWaiterId },
  });
}
