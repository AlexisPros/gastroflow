import { apiRequest } from "./apiClient";

export type EmployeeShift = {
  id: number;
  user_id: number;
  status: string;
  opening_note: string | null;
  closing_note: string | null;
  started_at: string;
  ended_at: string | null;
};

export type ShiftReportItem = {
  product_id: number;
  product_name: string;
  quantity: number;
  total: string;
};

export type ShiftReportDiscount = {
  discount_id: number | null;
  name: string;
  type: string;
  value: string | null;
  uses: number;
  total_discount_amount: string;
};

export type ShiftReportPaymentMethod = {
  method: string;
  count: number;
  total: string;
};

export type EmployeeShiftReport = {
  shift_id: number;
  user_id: number;
  orders_count: number;
  items_count: number;
  total_sales: string;
  total_tips: string;
  total_discounts: string;
  cash_total: string;
  card_total: string;
  other_payment_total: string;
  report_data: {
    sold_items?: ShiftReportItem[];
    discounts?: ShiftReportDiscount[];
    payment_methods?: ShiftReportPaymentMethod[];
  };
};

export async function getCurrentShift(token: string): Promise<EmployeeShift | null> {
  return apiRequest<EmployeeShift | null>("/shifts/current", { token });
}

export async function startShift(token: string): Promise<EmployeeShift> {
  return apiRequest<EmployeeShift>("/shifts/start", {
    method: "POST",
    token,
    body: {},
  });
}

export async function closeCurrentShift(token: string): Promise<EmployeeShiftReport> {
  return apiRequest<EmployeeShiftReport>("/shifts/current/close", {
    method: "POST",
    token,
    body: {},
  });
}

export async function getCurrentShiftReport(
  token: string,
): Promise<EmployeeShiftReport | null> {
  return apiRequest<EmployeeShiftReport | null>("/shifts/current/report", {
    token,
  });
}
