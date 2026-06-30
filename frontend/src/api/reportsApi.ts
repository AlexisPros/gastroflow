import { apiRequest } from "./apiClient";

export interface ReportSoldItem {
  product_id: number;
  product_name: string;
  quantity: number;
  total: number;
}

export interface ReportPaymentMethod {
  method: string;
  count: number;
  total: number;
}

export interface ReportDiscount {
  discount_id: number | null;
  name: string;
  type: string;
  value: number | null;
  uses: number;
  total_discount_amount: number;
}

export interface ChartDataPoint {
  label: string;
  value: number;
}

export interface EmployeeProductivityCompare {
  user_id: number;
  first_name: string;
  last_name: string;
  total_sales: number;
  total_tips: number;
  sold_items: ReportSoldItem[];
}

export interface AdvancedSalesReport {
  start_date: string;
  end_date: string;
  orders_count: number;
  items_count: number;
  total_sales: number;
  total_tips: number;
  total_discounts: number;
  cash_total: number;
  card_total: number;
  other_payment_total: number;
  sold_items: ReportSoldItem[];
  discounts: ReportDiscount[];
  payment_methods: ReportPaymentMethod[];
  chart_data: ChartDataPoint[];
  average_check: number;
  average_daily_sales: number;
  employee_comparison: EmployeeProductivityCompare[];
}

export interface WarehouseReportDocument {
  id: number;
  document_number: string;
  document_type: string;
  operation_date: string;
  status: string;
  source_warehouse_name: string | null;
  destination_warehouse_name: string | null;
  issued_by_user_name: string | null;
  items_count: number;
  reason: string | null;
  description: string | null;
}

export interface WarehouseReport {
  start_date: string;
  end_date: string;
  document_count: number;
  total_items_count: number;
  documents: WarehouseReportDocument[];
}

export interface UserActionLogReport {
  id: number;
  user_id: number;
  user_name: string;
  action_type: string;
  description: string | null;
  created_at: string;
  order_id: number;
}

export interface DailyProductionSectionReport {
  section_id: number;
  section_name: string;
  tasks_count: number;
  completed_tasks_count: number;
  items_count: number;
  estimated_minutes: number;
  actual_minutes: number;
  sold_items: ReportSoldItem[];
}

export interface DailyProductionReport {
  report_date: string;
  scope: string;
  sections: DailyProductionSectionReport[];
  tasks_count: number;
  completed_tasks_count: number;
  items_count: number;
  estimated_minutes: number;
  actual_minutes: number;
}

export async function getAdvancedSalesReport(
  token: string,
  params: { period: string; date?: string; user_id?: number }
): Promise<AdvancedSalesReport> {
  const query = new URLSearchParams();
  query.append("period", params.period);
  if (params.date) query.append("date", params.date);
  if (params.user_id) query.append("user_id", String(params.user_id));
  return apiRequest<AdvancedSalesReport>(`/reports/sales/advanced?${query.toString()}`, { token });
}

export async function getWarehouseReport(
  token: string,
  params: { period: string; date?: string; document_type?: string }
): Promise<WarehouseReport> {
  const query = new URLSearchParams();
  query.append("period", params.period);
  if (params.date) query.append("date", params.date);
  if (params.document_type) query.append("document_type", params.document_type);
  return apiRequest<WarehouseReport>(`/reports/warehouse?${query.toString()}`, { token });
}

export async function getUserActionLogs(
  token: string,
  params: { date?: string; user_id?: number }
): Promise<UserActionLogReport[]> {
  const query = new URLSearchParams();
  if (params.date) query.append("date", params.date);
  if (params.user_id) query.append("user_id", String(params.user_id));
  return apiRequest<UserActionLogReport[]>(`/reports/logs?${query.toString()}`, { token });
}

export async function getDailyProductionReport(
  token: string,
  scope: "KITCHEN" | "BAR",
  date?: string
): Promise<DailyProductionReport> {
  const path = scope === "KITCHEN" ? "/reports/kitchen/daily" : "/reports/bar/daily";
  const query = date ? `?report_date=${date}` : "";
  return apiRequest<DailyProductionReport>(`${path}${query}`, { token });
}
