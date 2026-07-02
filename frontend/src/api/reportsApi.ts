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

export interface WarehouseReportDocumentItem {
  id: number;
  ingredient_id: number;
  ingredient_name: string;
  quantity: number;
  unit: string;
  unit_price: number | null;
  total_value: number | null;
  book_quantity: number | null;
  actual_quantity: number | null;
  difference_quantity: number | null;
  difference_value: number | null;
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
  items: WarehouseReportDocumentItem[];
}

export interface WarehouseUnitBreakdown {
  unit: string;
  total_quantity: number;
}

export interface WarehouseReport {
  start_date: string;
  end_date: string;
  document_count: number;
  total_positions_count: number;
  unit_breakdown: WarehouseUnitBreakdown[];
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
  const report = await apiRequest<AdvancedSalesReport>(
    `/reports/sales/advanced?${query.toString()}`,
    { token },
  );
  return {
    ...report,
    sold_items: report?.sold_items ?? [],
    discounts: report?.discounts ?? [],
    payment_methods: report?.payment_methods ?? [],
    chart_data: report?.chart_data ?? [],
    employee_comparison: (report?.employee_comparison ?? []).map((employee) => ({
      ...employee,
      sold_items: employee?.sold_items ?? [],
    })),
  };
}

export async function getWarehouseReport(
  token: string,
  params: { period: string; date?: string; document_type?: string }
): Promise<WarehouseReport> {
  const query = new URLSearchParams();
  query.append("period", params.period);
  if (params.date) query.append("date", params.date);
  if (params.document_type) query.append("document_type", params.document_type);
  const report = await apiRequest<WarehouseReport>(
    `/reports/warehouse?${query.toString()}`,
    { token }
  );
  return {
    ...report,
    unit_breakdown: report?.unit_breakdown ?? [],
    documents: (report?.documents ?? []).map((doc) => ({
      ...doc,
      items: doc?.items ?? [],
    })),
  };
}

export async function getUserActionLogs(
  token: string,
  params: { date?: string; user_id?: number }
): Promise<UserActionLogReport[]> {
  const query = new URLSearchParams();
  if (params.date) query.append("date", params.date);
  if (params.user_id) query.append("user_id", String(params.user_id));
  const logs = await apiRequest<UserActionLogReport[]>(
    `/reports/logs?${query.toString()}`,
    { token },
  );
  return Array.isArray(logs) ? logs : [];
}

export async function getDailyProductionReport(
  token: string,
  scope: "KITCHEN" | "BAR",
  date?: string
): Promise<DailyProductionReport> {
  const path = scope === "KITCHEN" ? "/reports/kitchen/daily" : "/reports/bar/daily";
  const query = date ? `?report_date=${date}` : "";
  const report = await apiRequest<DailyProductionReport>(`${path}${query}`, { token });
  return {
    ...report,
    sections: (report?.sections ?? []).map((section) => ({
      ...section,
      sold_items: section?.sold_items ?? [],
    })),
  };
}
