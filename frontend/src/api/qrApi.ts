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
  name: string;
  products: PublicQrProduct[];
};

export type PublicQrOrder = {
  id: number;
  status: string;
  total_amount: string;
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
