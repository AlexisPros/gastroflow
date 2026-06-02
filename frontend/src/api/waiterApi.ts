import { apiRequest } from "./apiClient";
import type { RestaurantTable, RestaurantTableStatus } from "./floorPlanApi";

export type ProductCategory = {
  id: number;
  parent_category_id: number | null;
  name: string;
  is_active: boolean;
};

export type Product = {
  id: number;
  category_id: number;
  kitchen_section_id: number | null;
  name: string;
  description: string | null;
  price: string;
  preparation_time: number | null;
  is_active: boolean;
  created_at: string;
};

export type Order = {
  id: number;
  table_id: number | null;
  waiter_id: number | null;
  discount_id: number | null;
  shift_id: number | null;
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

export type OrderItem = {
  id: number;
  order_id: number;
  product_id: number;
  quantity: number;
  unit_price: string;
  total_price: string;
  status: string;
  notes: string | null;
};

export type CartItem = {
  product: Product;
  quantity: number;
  notes?: string | null;
};

export async function getWaiterProducts(token: string): Promise<Product[]> {
  return apiRequest<Product[]>("/products?limit=500", { token });
}

export async function getProductCategories(token: string): Promise<ProductCategory[]> {
  return apiRequest<ProductCategory[]>("/product-categories?limit=500", { token });
}

export async function getWaiterTables(token: string): Promise<RestaurantTable[]> {
  return apiRequest<RestaurantTable[]>("/restaurant-tables?limit=500", { token });
}

export async function getWaiterOrders(token: string): Promise<Order[]> {
  return apiRequest<Order[]>("/orders?limit=500", { token });
}

export async function getWaiterOrderItems(token: string): Promise<OrderItem[]> {
  return apiRequest<OrderItem[]>("/order-items?limit=1000", { token });
}

export async function createWaiterOrder(
  token: string,
  body: {
    table_id: number | null;
    waiter_id: number;
    guest_count: number | null;
    source: "WAITER";
    items: Array<{
      product_id: number;
      quantity: number;
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

export function isOpenOrder(order: Order): boolean {
  return !["CLOSED", "CANCELLED", "REJECTED"].includes(order.status);
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
