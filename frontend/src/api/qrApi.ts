import { apiRequest } from "./apiClient";

export type PublicQrTable = {
  id: number;
  table_number: string;
  status: string;
  qr_code_url: string | null;
  is_active: boolean;
};

export type PublicQrModifier = {
  product_modifier_id: number;
  name: string;
  price: string;
};

export type PublicQrProduct = {
  id: number;
  category_id: number;
  name: string;
  description: string | null;
  image_url: string | null;
  ingredients: string[];
  price: string;
  modifiers: PublicQrModifier[];
};

export type PublicQrCategory = {
  id: number;
  parent_category_id: number | null;
  name: string;
  department: "KITCHEN" | "BAR";
  products: PublicQrProduct[];
};

export type PublicQrOrder = {
  id: number;
  status: string;
  total_amount: string;
};

export type PublicQrOrderStatus = {
  order_id: number;
  target_order_id: number | null;
  status: string;
  public_status: "PENDING_CONFIRMATION" | "PREPARING" | "READY" | "REJECTED" | "CLOSED" | string;
  progress_percent: number;
  estimated_ready_at: string | null;
  can_order_more: boolean;
  items: PublicQrOrderDetailItem[];
};

export type PublicQrOrderDetailItem = {
  id: number;
  product_id: number;
  product_name: string;
  quantity: number;
  course_number: number;
  unit_price: string;
  total_price: string;
  status: string;
  notes: string | null;
  modifiers: Array<{
    name: string;
    price: string;
  }>;
};

export async function getPublicQrTable(qrToken: string): Promise<PublicQrTable> {
  return apiRequest<PublicQrTable>(`/qr/${encodeURIComponent(qrToken)}/table`);
}

export async function getPublicQrMenu(qrToken: string): Promise<PublicQrCategory[]> {
  return apiRequest<PublicQrCategory[]>(`/qr/${encodeURIComponent(qrToken)}/menu`);
}

export async function createPublicQrOrder(
  qrToken: string,
  body: {
    guest_count: number;
    order_code?: string | null;
    items: Array<{
      product_id: number;
      quantity: number;
      notes?: string | null;
      product_modifier_ids: number[];
    }>;
  },
): Promise<PublicQrOrder> {
  return apiRequest<PublicQrOrder>(`/qr/${encodeURIComponent(qrToken)}/orders`, {
    method: "POST",
    body,
  });
}

export async function unlockPublicQrOrder(
  qrToken: string,
  body: { order_code: string },
): Promise<PublicQrOrderStatus> {
  return apiRequest<PublicQrOrderStatus>(`/qr/${encodeURIComponent(qrToken)}/orders/unlock`, {
    method: "POST",
    body,
  });
}

export async function getPublicQrOrderStatus(
  qrToken: string,
  orderId: number,
): Promise<PublicQrOrderStatus> {
  return apiRequest<PublicQrOrderStatus>(
    `/qr/${encodeURIComponent(qrToken)}/orders/${orderId}/status`,
  );
}
