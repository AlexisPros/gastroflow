import { apiRequest, apiBlobRequest } from "./apiClient";
import type { Order } from "./waiterApi";

export type ReservationTable = { id: number; table_number: string };
export type ReservationItem = {
  id: number;
  product_id: number;
  product_name: string;
  quantity: number;
  unit_price: string;
  total_price: string;
  notes: string | null;
};
export type ReservationPayment = {
  id: number;
  method: string;
  amount: string;
  cash_received: string | null;
  change_given: string | null;
  status: string;
  created_at: string;
};
export type Reservation = {
  id: number;
  table_id: number;
  customer_name: string;
  customer_phone: string;
  customer_email: string | null;
  invoice_nip: string | null;
  guest_count: number;
  reservation_time: string;
  duration_minutes: number;
  status: string;
  notes: string | null;
  total_amount: string;
  prepaid_amount: string;
  payment_status: string;
  created_by_user_id: number | null;
  started_order_id: number | null;
  started_at: string | null;
  created_at: string;
  tables: ReservationTable[];
  items: ReservationItem[];
  payments: ReservationPayment[];
};
export type ReservationMenuProduct = {
  id: number;
  name: string;
  price: string;
  image_url: string | null;
  category_id: number;
  category_name: string;
  department: "KITCHEN" | "BAR";
};
export type ReservationPayload = {
  table_ids: number[];
  customer_name: string;
  customer_phone: string;
  customer_email: string | null;
  guest_count: number;
  reservation_time: string;
  duration_minutes: number;
  notes: string | null;
  items: Array<{ product_id: number; quantity: number; notes?: string | null }>;
  payment_method: "ON_SITE" | "CARD" | "CASH";
  cash_received?: string | null;
  invoice_nip?: string | null;
};

export const getReservations = (token: string) =>
  apiRequest<Reservation[]>("/reservations", { token });
export const getReservationMenu = (token: string) =>
  apiRequest<ReservationMenuProduct[]>("/reservations/menu", { token });
export const createReservation = (token: string, body: ReservationPayload) =>
  apiRequest<Reservation>("/reservations", { method: "POST", token, body });
export const cancelReservation = (token: string, reservationId: number) =>
  apiRequest<Reservation>(`/reservations/${reservationId}/cancel`, { method: "POST", token });
export const startReservation = (token: string, reservationId: number) =>
  apiRequest<Order>(`/reservations/${reservationId}/start`, { method: "POST", token });
export const completePrepaidReservation = (token: string, reservationId: number) =>
  apiRequest<Order>(`/reservations/${reservationId}/complete-prepaid`, { method: "POST", token });

export async function generateReservationReceiptPdf(
  token: string,
  reservationId: number,
): Promise<Blob> {
  return apiBlobRequest(`/reservations/${reservationId}/receipt/pdf`, {
    method: "POST",
    token,
    timeoutMs: 20000,
  });
}

export async function generateReservationGuestCheckPdf(
  token: string,
  reservationId: number,
): Promise<Blob> {
  return apiBlobRequest(`/reservations/${reservationId}/guest-check/pdf`, {
    method: "POST",
    token,
    timeoutMs: 20000,
  });
}
