import { useCallback, useEffect, useMemo, useState } from "react";
import { Search, X, Download } from "lucide-react";
import { downloadWarehouseDocumentPdf } from "../api/warehouseApi";

import { ApiError } from "../api/apiClient";
import { useAuth } from "../auth/useAuth";
import {
  getAdvancedSalesReport,
  getWarehouseReport,
  getUserActionLogs,
  getDailyProductionReport,
  type AdvancedSalesReport,
  type WarehouseReport,
  type WarehouseReportDocument,
  type UserActionLogReport,
  type DailyProductionReport,
} from "../api/reportsApi";
import { getAdminUsers, type AdminUser } from "../api/adminUsersApi";
import { getAdminMenu, type AdminProduct } from "../api/adminMenuApi";
import { getCurrentShift, getCurrentShiftReport, type EmployeeShiftReport } from "../api/shiftApi";

type Tab = "sales" | "kitchen" | "bar" | "warehouse" | "logs";
type LoadingState = "idle" | "loading" | "ready" | "error";

export function ReportsPage() {
  const { token, user } = useAuth();

  // Basic role check
  const isAdminOrManager = user?.role === "ADMIN" || user?.role === "MANAGER";

  // State for Waiter Shift Report
  const [waiterReport, setWaiterReport] = useState<EmployeeShiftReport | null>(null);
  const [waiterStatus, setWaiterStatus] = useState<LoadingState>("idle");
  const [waiterError, setWaiterError] = useState<string | null>(null);

  // Tab State
  const [activeTab, setActiveTab] = useState<Tab>("sales");

  // Filter States
  const [selectedDate, setSelectedDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [selectedPeriod, setSelectedPeriod] = useState<string>("week"); // week, month, quarter, half_year, year
  const [selectedWarehousePeriod, setSelectedWarehousePeriod] = useState<string>("week"); // day, week, month
  const [selectedUserFilter, setSelectedUserFilter] = useState<number | null>(null);
  const [selectedWarehouseDocType, setSelectedWarehouseDocType] = useState<string>("ALL");

  // Data States
  const [salesReport, setSalesReport] = useState<AdvancedSalesReport | null>(null);
  const [productionReport, setProductionReport] = useState<DailyProductionReport | null>(null);
  const [warehouseReport, setWarehouseReport] = useState<WarehouseReport | null>(null);
  const [actionLogs, setActionLogs] = useState<UserActionLogReport[]>([]);

  // Lookup data states
  const [allUsers, setAllUsers] = useState<AdminUser[]>([]);
  const [menuProducts, setMenuProducts] = useState<AdminProduct[]>([]);

  // Productivity View comparison states
  const [selectedCompareProduct, setSelectedCompareProduct] = useState<number | null>(null);
  const [productSearch, setProductSearch] = useState<string>("");
  const [isProductDropdownOpen, setIsProductDropdownOpen] = useState(false);
  const [productivitySortKey, setProductivitySortKey] = useState<"sales" | "tips" | "product">("sales");

  // Warehouse Detail modal state
  const [activeWarehouseDoc, setActiveWarehouseDoc] = useState<WarehouseReportDocument | null>(null);
  const [downloadingDocumentId, setDownloadingDocumentId] = useState<number | null>(null);

  const downloadDocument = async (document: WarehouseReportDocument) => {
    if (!token) return;
    try {
      setDownloadingDocumentId(document.id);
      const blob = await downloadWarehouseDocumentPdf(token, document.id);
      const url = window.URL.createObjectURL(blob);
      const link = window.document.createElement("a");
      link.href = url;
      link.download = `${document.document_number.replaceAll("/", "-")}.pdf`;
      window.document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Nie udało się pobrać dokumentu PDF.");
    } finally {
      setDownloadingDocumentId(null);
    }
  };

  // Global status states
  const [status, setStatus] = useState<LoadingState>("idle");
  const [error, setError] = useState<string | null>(null);

  // Load Waiter Report
  const loadWaiterReport = useCallback(async () => {
    if (!token) return;
    setWaiterStatus((curr) => (curr === "ready" ? curr : "loading"));
    setWaiterError(null);
    try {
      const currentShift = await getCurrentShift(token);
      if (!currentShift) {
        setWaiterReport(null);
        setWaiterStatus("ready");
        return;
      }
      setWaiterReport(await getCurrentShiftReport(token));
      setWaiterStatus("ready");
    } catch (exc) {
      setWaiterError(exc instanceof ApiError ? exc.message : "Could not load report.");
      setWaiterStatus("error");
    }
  }, [token]);

  // Load lookup users & products
  useEffect(() => {
    if (!token || !isAdminOrManager) return;
    void (async () => {
      try {
        const users = await getAdminUsers(token);
        setAllUsers(users.filter((u) => u.is_active));
        const menu = await getAdminMenu(token);
        setMenuProducts(menu.products.filter((p) => p.is_active));
      } catch (e) {
        console.error("Failed to load metadata options", e);
      }
    })();
  }, [token, isAdminOrManager]);

  // Load Admin reports based on active tab & filters
  const loadAdminReports = useCallback(async () => {
    if (!token || !isAdminOrManager) return;
    setStatus("loading");
    setError(null);
    try {
      if (activeTab === "sales") {
        const res = await getAdvancedSalesReport(token, {
          period: selectedPeriod,
          date: selectedDate,
          user_id: selectedUserFilter || undefined,
        });
        setSalesReport(res);
      } else if (activeTab === "kitchen" || activeTab === "bar") {
        const scope = activeTab === "kitchen" ? "KITCHEN" : "BAR";
        const res = await getDailyProductionReport(token, scope, selectedDate);
        setProductionReport(res);
      } else if (activeTab === "warehouse") {
        const res = await getWarehouseReport(token, {
          period: selectedWarehousePeriod,
          date: selectedDate,
          document_type: selectedWarehouseDocType,
        });
        setWarehouseReport(res);
      } else if (activeTab === "logs") {
        const res = await getUserActionLogs(token, {
          date: selectedDate,
          user_id: selectedUserFilter || undefined,
        });
        setActionLogs(res);
      }
      setStatus("ready");
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Failed to load report data.");
      setStatus("error");
    }
  }, [
    token,
    isAdminOrManager,
    activeTab,
    selectedPeriod,
    selectedWarehousePeriod,
    selectedDate,
    selectedUserFilter,
    selectedWarehouseDocType,
  ]);

  useEffect(() => {
    if (isAdminOrManager) {
      void loadAdminReports();
    } else {
      void loadWaiterReport();
    }
  }, [isAdminOrManager, loadAdminReports, loadWaiterReport]);

  // Filter products by input query
  const filteredProducts = useMemo(() => {
    const q = productSearch.toLowerCase().trim();
    if (!q) return menuProducts;
    return menuProducts.filter((p) => p.name.toLowerCase().includes(q));
  }, [menuProducts, productSearch]);

  // Selected compare product object
  const activeProduct = useMemo(() => {
    if (selectedCompareProduct === null) return null;
    return menuProducts.find((p) => p.id === selectedCompareProduct) || null;
  }, [menuProducts, selectedCompareProduct]);

  // Sort and process employees compare stats
  const processedEmployees = useMemo(() => {
    if (!salesReport) return [];
    const base = [...salesReport.employee_comparison];

    return base.sort((a, b) => {
      if (productivitySortKey === "tips") {
        return Number(b.total_tips) - Number(a.total_tips);
      }
      if (productivitySortKey === "product" && selectedCompareProduct !== null) {
        const aCount = a.sold_items.find((i) => i.product_id === selectedCompareProduct)?.quantity ?? 0;
        const bCount = b.sold_items.find((i) => i.product_id === selectedCompareProduct)?.quantity ?? 0;
        return bCount - aCount;
      }
      return Number(b.total_sales) - Number(a.total_sales);
    });
  }, [salesReport, productivitySortKey, selectedCompareProduct]);

  // RENDER: Waiter view
  if (!isAdminOrManager) {
    if (waiterStatus === "idle" || waiterStatus === "loading") {
      return (
        <section className="page-stack">
          <div className="floor-header">
            <div>
              <span className="eyebrow">RAPORTY</span>
              <h1>Obecna zmiana</h1>
            </div>
            <button type="button" className="ghost-button" onClick={loadWaiterReport}>
              Odśwież
            </button>
          </div>
          <div className="module-placeholder">Ładowanie raportu zmiany...</div>
        </section>
      );
    }

    if (waiterStatus === "error") {
      return (
        <section className="page-stack">
          <div className="floor-header">
            <div>
              <span className="eyebrow">RAPORTY</span>
              <h1>Obecna zmiana</h1>
            </div>
            <button type="button" className="ghost-button" onClick={loadWaiterReport}>
              Odśwież
            </button>
          </div>
          <div className="error-box">{waiterError}</div>
        </section>
      );
    }

    if (!waiterReport) {
      return (
        <section className="page-stack">
          <div className="floor-header">
            <div>
              <span className="eyebrow">RAPORTY</span>
              <h1>Obecna zmiana</h1>
            </div>
            <button type="button" className="ghost-button" onClick={loadWaiterReport}>
              Odśwież
            </button>
          </div>
          <div className="module-placeholder">
            <strong>Brak aktywnej zmiany</strong>
            <p>Rozpocznij zmianę, aby zobaczyć aktualne statystyki.</p>
          </div>
        </section>
      );
    }

    const soldItems = waiterReport.report_data.sold_items ?? [];
    const discounts = waiterReport.report_data.discounts ?? [];
    const paymentMethods = waiterReport.report_data.payment_methods ?? [];

    return (
      <section className="page-stack">
        <div className="floor-header">
          <div>
            <span className="eyebrow">RAPORTY</span>
            <h1>Obecna zmiana</h1>
          </div>
          <button type="button" className="ghost-button" onClick={loadWaiterReport}>
            Odśwież
          </button>
        </div>

        <div className="report-metrics-grid">
          <div className="report-metric-card">
            <span>Sprzedaż</span>
            <strong>{formatMoney(Number(waiterReport.total_sales))}</strong>
          </div>
          <div className="report-metric-card">
            <span>Napiwki</span>
            <strong>{formatMoney(Number(waiterReport.total_tips))}</strong>
          </div>
          <div className="report-metric-card">
            <span>Rabaty</span>
            <strong>{formatMoney(Number(waiterReport.total_discounts))}</strong>
          </div>
          <div className="report-metric-card">
            <span>Rachunki</span>
            <strong>{String(waiterReport.orders_count)}</strong>
          </div>
          <div className="report-metric-card">
            <span>Pozycje</span>
            <strong>{String(waiterReport.items_count)}</strong>
          </div>
          <div className="report-metric-card">
            <span>Karta</span>
            <strong>{formatMoney(Number(waiterReport.card_total))}</strong>
          </div>
          <div className="report-metric-card">
            <span>Gotówka</span>
            <strong>{formatMoney(Number(waiterReport.cash_total))}</strong>
          </div>
          <div className="report-metric-card">
            <span>Inne</span>
            <strong>{formatMoney(Number(waiterReport.other_payment_total))}</strong>
          </div>
        </div>

        <div className="report-section-grid">
          <div className="report-table-card">
            <h2>Sprzedane pozycje</h2>
            <div className="report-row-list">
              {soldItems.map((item) => (
                <div key={item.product_id} className="report-row">
                  <div>
                    <strong>{item.product_name}</strong>
                    <span>Sprzedane: {item.quantity}</span>
                  </div>
                  <b>{formatMoney(Number(item.total))}</b>
                </div>
              ))}
              {soldItems.length === 0 && <p className="muted">Brak sprzedanych pozycji.</p>}
            </div>
          </div>

          <div className="report-table-card">
            <h2>Użyte rabaty</h2>
            <div className="report-row-list">
              {discounts.map((discount) => (
                <div key={discount.name} className="report-row">
                  <div>
                    <strong>{discount.name}</strong>
                    <span>Użyty: {discount.uses} razy</span>
                  </div>
                  <b>{formatMoney(Number(discount.total_discount_amount))}</b>
                </div>
              ))}
              {discounts.length === 0 && <p className="muted">Brak użytych rabatów.</p>}
            </div>
          </div>

          <div className="report-table-card">
            <h2>Metody płatności</h2>
            <div className="report-row-list">
              {paymentMethods.map((payment) => (
                <div key={payment.method} className="report-row">
                  <div>
                    <strong>{payment.method}</strong>
                    <span>Płatności: {payment.count}</span>
                  </div>
                  <b>{formatMoney(Number(payment.total))}</b>
                </div>
              ))}
              {paymentMethods.length === 0 && <p className="muted">Brak zrealizowanych płatności.</p>}
            </div>
          </div>
        </div>
      </section>
    );
  }

  // RENDER: Admin/Manager view
  return (
    <section className="page-stack">
      {/* Header */}
      <div className="floor-header">
        <div>
          <span className="eyebrow">RAPORTY ADMINISTRATORA</span>
          <h1>Statystyki i Analizy</h1>
        </div>
        <button
          type="button"
          className="ghost-button"
          disabled={status === "loading"}
          onClick={() => void loadAdminReports()}
        >
          Odśwież
        </button>
      </div>

      {/* Categories Tabs */}
      <div className="admin-tabs" style={{ display: "flex", gap: "10px", borderBottom: "1px solid #d7dfda", paddingBottom: "10px" }}>
        {(["sales", "kitchen", "bar", "warehouse", "logs"] as const).map((tab) => (
          <button
            key={tab}
            className={`admin-tab-btn ${activeTab === tab ? "active" : ""}`}
            style={{
              padding: "8px 16px",
              background: activeTab === tab ? "var(--brand-green)" : "#ffffff",
              color: activeTab === tab ? "#ffffff" : "#172026",
              border: "1px solid #c8d2cc",
              borderRadius: "6px",
              fontWeight: "600",
              cursor: "pointer",
            }}
            onClick={() => setActiveTab(tab)}
          >
            {tab === "sales" && "Sprzedaż"}
            {tab === "kitchen" && "Kuchnia"}
            {tab === "bar" && "Bar"}
            {tab === "warehouse" && "Magazyn"}
            {tab === "logs" && "Logi"}
          </button>
        ))}
      </div>

      {/* Global Filters Panel */}
      <div className="report-filters-bar" style={{ display: "flex", flexWrap: "wrap", gap: "16px", padding: "16px", background: "#f8faf9", borderRadius: "8px", border: "1px solid #d7dfda" }}>
        {/* Date Filter (Used in all tabs) */}
        <label style={{ display: "grid", gap: "4px" }}>
          <span style={{ fontSize: "11px", color: "#60716c", fontWeight: "600", textTransform: "uppercase" }}>Wybierz datę</span>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            style={{ padding: "8px 12px", borderRadius: "6px", border: "1px solid #c8d2cc" }}
          />
        </label>

        {/* Sales Period (Sales Tab only) */}
        {activeTab === "sales" && (
          <label style={{ display: "grid", gap: "4px" }}>
            <span style={{ fontSize: "11px", color: "#60716c", fontWeight: "600", textTransform: "uppercase" }}>Okres raportu</span>
            <select
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value)}
              style={{ padding: "8px 12px", borderRadius: "6px", border: "1px solid #c8d2cc", background: "#fff" }}
            >
              <option value="week">Tygodniowy</option>
              <option value="month">Miesięczny</option>
              <option value="quarter">Kwartalny</option>
              <option value="half_year">Półroczny</option>
              <option value="year">Roczny</option>
            </select>
          </label>
        )}

        {/* Warehouse Period (Warehouse Tab only) */}
        {activeTab === "warehouse" && (
          <label style={{ display: "grid", gap: "4px" }}>
            <span style={{ fontSize: "11px", color: "#60716c", fontWeight: "600", textTransform: "uppercase" }}>Okres raportu</span>
            <select
              value={selectedWarehousePeriod}
              onChange={(e) => setSelectedWarehousePeriod(e.target.value)}
              style={{ padding: "8px 12px", borderRadius: "6px", border: "1px solid #c8d2cc", background: "#fff" }}
            >
              <option value="day">Dzienny</option>
              <option value="week">Tygodniowy</option>
              <option value="month">Miesięczny</option>
            </select>
          </label>
        )}

        {/* User filter (Sales, Logs Tabs) */}
        {(activeTab === "sales" || activeTab === "logs") && (
          <label style={{ display: "grid", gap: "4px" }}>
            <span style={{ fontSize: "11px", color: "#60716c", fontWeight: "600", textTransform: "uppercase" }}>Pracownik</span>
            <select
              value={selectedUserFilter || ""}
              onChange={(e) => setSelectedUserFilter(e.target.value ? Number(e.target.value) : null)}
              style={{ padding: "8px 12px", borderRadius: "6px", border: "1px solid #c8d2cc", background: "#fff" }}
            >
              <option value="">Wszyscy pracownicy</option>
              {allUsers.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.first_name} {u.last_name} ({u.role})
                </option>
              ))}
            </select>
          </label>
        )}

        {/* Warehouse Doc type filter (Warehouse Tab only) */}
        {activeTab === "warehouse" && (
          <label style={{ display: "grid", gap: "4px" }}>
            <span style={{ fontSize: "11px", color: "#60716c", fontWeight: "600", textTransform: "uppercase" }}>Rodzaj dokumentu</span>
            <select
              value={selectedWarehouseDocType}
              onChange={(e) => setSelectedWarehouseDocType(e.target.value)}
              style={{ padding: "8px 12px", borderRadius: "6px", border: "1px solid #c8d2cc", background: "#fff" }}
            >
              <option value="ALL">Wszystkie dokumenty</option>
              <option value="PZ">Przyjęcie Zewnętrzne (PZ)</option>
              <option value="MM">Przesunięcie Międzymagazynowe (MM)</option>
              <option value="RW">Rozchód Wewnętrzny (RW)</option>
              <option value="INW">Inwentaryzacja (INW)</option>
            </select>
          </label>
        )}
      </div>

      {status === "loading" && <div className="module-placeholder">Ładowanie raportów...</div>}
      {status === "error" && <div className="error-box">{error}</div>}

      {status === "ready" && (
        <div className="admin-reports-content" style={{ display: "grid", gap: "24px" }}>
          {/* TAB: SALES */}
          {activeTab === "sales" && salesReport && (
            <>
              {/* Metrics */}
              <div className="report-metrics-grid">
                <div className="report-metric-card">
                  <span>Przychody całkowite</span>
                  <strong>{formatMoney(Number(salesReport.total_sales))}</strong>
                </div>
                <div className="report-metric-card">
                  <span>Napiwki</span>
                  <strong>{formatMoney(Number(salesReport.total_tips))}</strong>
                </div>
                <div className="report-metric-card">
                  <span>Rabaty</span>
                  <strong>{formatMoney(Number(salesReport.total_discounts))}</strong>
                </div>
                <div className="report-metric-card">
                  <span>Liczba zamówień</span>
                  <strong>{String(salesReport.orders_count)}</strong>
                </div>
                <div className="report-metric-card">
                  <span>Karta</span>
                  <strong>{formatMoney(Number(salesReport.card_total))}</strong>
                </div>
                <div className="report-metric-card">
                  <span>Gotówka</span>
                  <strong>{formatMoney(Number(salesReport.cash_total))}</strong>
                </div>
                <div className="report-metric-card">
                  <span>Inne płatności</span>
                  <strong>{formatMoney(Number(salesReport.other_payment_total))}</strong>
                </div>
                <div className="report-metric-card">
                  <span>Śr. wartość rachunku</span>
                  <strong>{formatMoney(Number(salesReport.average_check))}</strong>
                </div>
                <div className="report-metric-card">
                  <span>Śr. dzienna sprzedaż</span>
                  <strong>{formatMoney(Number(salesReport.average_daily_sales))}</strong>
                </div>
              </div>

              {/* Column revenue chart */}
              <div className="report-chart-section">
                <h3 style={{ margin: "0 0 10px 0", fontSize: "16px" }}>Wykres kolumnowy przychodów ze średnią rachunku i średnią dzienną</h3>
                {salesReport.chart_data.length > 0 ? (
                  <SVGRevenueChart
                    data={salesReport.chart_data}
                    averageCheck={salesReport.average_check}
                    averageDailySales={salesReport.average_daily_sales}
                  />
                ) : (
                  <p className="muted">Brak danych przychodu dla wybranego okresu.</p>
                )}
              </div>

              {/* Employees Productivity ranking (Only when listing all workers) */}
              {selectedUserFilter === null && (
                <div className="report-productivity-section" style={{ background: "#ffffff", padding: "20px", borderRadius: "8px", border: "1px solid #d7dfda" }}>
                  <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", gap: "16px" }}>
                    <div>
                      <h3 style={{ margin: 0, fontSize: "16px" }}>Porównanie wydajności pracowników</h3>
                      <p className="muted" style={{ margin: "2px 0 0" }}>Wybierz kryteria sortowania do analizy produktywności.</p>
                    </div>

                    {/* Filter product comparison */}
                    <div style={{ display: "flex", gap: "10px", alignItems: "center", position: "relative" }}>
                      <span style={{ fontSize: "12px", color: "#60716c", fontWeight: "600" }}>Wybierz danie:</span>
                      <div style={{ position: "relative" }}>
                        <button
                          type="button"
                          className="ghost-button"
                          onClick={() => setIsProductDropdownOpen(!isProductDropdownOpen)}
                          style={{ minHeight: "36px", display: "flex", alignItems: "center", gap: "6px" }}
                        >
                          {activeProduct ? activeProduct.name : "Wszystkie dania"}
                        </button>
                        {isProductDropdownOpen && (
                          <div style={{ position: "absolute", right: 0, top: "42px", background: "#ffffff", border: "1px solid #c8d2cc", borderRadius: "6px", boxShadow: "0 4px 12px rgba(0,0,0,0.1)", zIndex: 100, width: "240px", padding: "8px" }}>
                            <div style={{ display: "flex", alignItems: "center", borderBottom: "1px solid #eef1ef", paddingBottom: "6px", marginBottom: "6px" }}>
                              <Search size={14} style={{ marginRight: "6px", color: "#60716c" }} />
                              <input
                                type="text"
                                placeholder="Wyszukaj..."
                                value={productSearch}
                                onChange={(e) => setProductSearch(e.target.value)}
                                style={{ border: 0, outline: 0, fontSize: "12px", width: "100%" }}
                              />
                            </div>
                            <div style={{ maxHeight: "180px", overflowY: "auto" }}>
                              <div
                                style={{ padding: "6px", cursor: "pointer", fontSize: "12px", borderRadius: "4px", background: selectedCompareProduct === null ? "#eef7f2" : "transparent" }}
                                onClick={() => {
                                  setSelectedCompareProduct(null);
                                  setIsProductDropdownOpen(false);
                                  setProductSearch("");
                                }}
                              >
                                Wszystkie dania
                              </div>
                              {filteredProducts.map((p) => (
                                <div
                                  key={p.id}
                                  style={{ padding: "6px", cursor: "pointer", fontSize: "12px", borderRadius: "4px", background: selectedCompareProduct === p.id ? "#eef7f2" : "transparent" }}
                                  onClick={() => {
                                    setSelectedCompareProduct(p.id);
                                    setIsProductDropdownOpen(false);
                                    setProductSearch("");
                                  }}
                                >
                                  {p.name}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Criteria Tabs */}
                  <div style={{ display: "flex", gap: "10px", marginBottom: "16px" }}>
                    <button
                      className={`ghost-button ${productivitySortKey === "sales" ? "active" : ""}`}
                      onClick={() => setProductivitySortKey("sales")}
                      style={{ fontSize: "12px", minHeight: "32px", padding: "0 12px" }}
                    >
                      Sortuj wg sprzedaży
                    </button>
                    <button
                      className={`ghost-button ${productivitySortKey === "tips" ? "active" : ""}`}
                      onClick={() => setProductivitySortKey("tips")}
                      style={{ fontSize: "12px", minHeight: "32px", padding: "0 12px" }}
                    >
                      Sortuj wg napiwków
                    </button>
                    {selectedCompareProduct !== null && (
                      <button
                        className={`ghost-button ${productivitySortKey === "product" ? "active" : ""}`}
                        onClick={() => setProductivitySortKey("product")}
                        style={{ fontSize: "12px", minHeight: "32px", padding: "0 12px" }}
                      >
                        Sortuj wg dania: {activeProduct?.name}
                      </button>
                    )}
                  </div>

                  {/* Compare Table */}
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                      <thead>
                        <tr style={{ background: "#f8faf9", borderBottom: "1px solid #d7dfda", textAlign: "left" }}>
                          <th style={{ padding: "10px 12px" }}>Pracownik</th>
                          <th style={{ padding: "10px 12px", textAlign: "right" }}>Obroty całkowite</th>
                          <th style={{ padding: "10px 12px", textAlign: "right" }}>Suma Napiwków</th>
                          {selectedCompareProduct !== null && (
                            <th style={{ padding: "10px 12px", textAlign: "right" }}>Sprzedano: {activeProduct?.name}</th>
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {processedEmployees.map((emp) => {
                          const productSales = emp.sold_items.find((i) => i.product_id === selectedCompareProduct)?.quantity ?? 0;
                          return (
                            <tr key={emp.user_id} style={{ borderBottom: "1px solid #eef1ef" }}>
                              <td style={{ padding: "10px 12px", fontWeight: "600" }}>{emp.first_name} {emp.last_name}</td>
                              <td style={{ padding: "10px 12px", textAlign: "right" }}>{formatMoney(emp.total_sales)}</td>
                              <td style={{ padding: "10px 12px", textAlign: "right" }}>{formatMoney(emp.total_tips)}</td>
                              {selectedCompareProduct !== null && (
                                <td style={{ padding: "10px 12px", textAlign: "right", fontWeight: "700", color: "var(--brand-green)" }}>
                                  {productSales} szt.
                                </td>
                              )}
                            </tr>
                          );
                        })}
                        {processedEmployees.length === 0 && (
                          <tr>
                            <td colSpan={4} style={{ padding: "16px", textAnchor: "middle", textAlign: "center" }} className="muted">
                              Brak aktywności pracowników w tym okresie.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Tables breakdowns */}
              <div className="report-section-grid">
                <div className="report-table-card">
                  <h2>Sprzedane pozycje</h2>
                  <div className="report-row-list">
                    {salesReport.sold_items.map((item) => (
                      <div key={item.product_id} className="report-row">
                        <div>
                          <strong>{item.product_name}</strong>
                          <span>Sprzedane: {item.quantity}</span>
                        </div>
                        <b>{formatMoney(Number(item.total))}</b>
                      </div>
                    ))}
                    {salesReport.sold_items.length === 0 && <p className="muted">Brak sprzedanych pozycji.</p>}
                  </div>
                </div>

                <div className="report-table-card">
                  <h2>Metody płatności</h2>
                  <div className="report-row-list">
                    {salesReport.payment_methods.map((payment) => (
                      <div key={payment.method} className="report-row">
                        <div>
                          <strong>{payment.method}</strong>
                          <span>Płatności: {payment.count}</span>
                        </div>
                        <b>{formatMoney(Number(payment.total))}</b>
                      </div>
                    ))}
                    {salesReport.payment_methods.length === 0 && <p className="muted">Brak płatności.</p>}
                  </div>
                </div>

                <div className="report-table-card">
                  <h2>Użyte rabaty</h2>
                  <div className="report-row-list">
                    {salesReport.discounts.map((discount) => (
                      <div key={discount.name} className="report-row">
                        <div>
                          <strong>{discount.name}</strong>
                          <span>Użyty: {discount.uses} razy</span>
                        </div>
                        <b>{formatMoney(Number(discount.total_discount_amount))}</b>
                      </div>
                    ))}
                    {salesReport.discounts.length === 0 && <p className="muted">Brak rabatów.</p>}
                  </div>
                </div>
              </div>
            </>
          )}

          {/* TAB: KITCHEN & BAR PRODUCTION */}
          {(activeTab === "kitchen" || activeTab === "bar") && productionReport && (
            <>
              {/* Summary Stats */}
              <div className="report-metrics-grid" style={{ gridTemplateColumns: "repeat(5, 1fr)" }}>
                <div className="report-metric-card">
                  <span>Czas planowany (suma)</span>
                  <strong>{productionReport.estimated_minutes} min</strong>
                </div>
                <div className="report-metric-card">
                  <span>Czas rzeczywisty (suma)</span>
                  <strong>{productionReport.actual_minutes} min</strong>
                </div>
                <div className="report-metric-card">
                  <span>Liczba zadań</span>
                  <strong>{productionReport.tasks_count}</strong>
                </div>
                <div className="report-metric-card">
                  <span>Zakończone zadania</span>
                  <strong>{productionReport.completed_tasks_count}</strong>
                </div>
                <div className="report-metric-card">
                  <span>Pozycje zamówień</span>
                  <strong>{productionReport.items_count}</strong>
                </div>
              </div>

              {/* Section performance grids */}
              <div className="report-section-grid" style={{ gridTemplateColumns: "1fr" }}>
                {productionReport.sections.map((sec) => {
                  const efficiency = sec.tasks_count > 0 ? (sec.completed_tasks_count / sec.tasks_count) * 100 : 0;
                  return (
                    <div key={sec.section_id} className="report-table-card" style={{ padding: "20px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid #d7dfda", paddingBottom: "10px", marginBottom: "16px" }}>
                        <h2 style={{ margin: 0 }}>Sekcja: {sec.section_name}</h2>
                        <strong style={{ color: "var(--brand-green)" }}>Wydajność: {efficiency.toFixed(0)}%</strong>
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px", marginBottom: "20px" }}>
                        <div><small style={{ color: "#60716c" }}>Liczba zadań:</small> <strong>{sec.tasks_count}</strong></div>
                        <div><small style={{ color: "#60716c" }}>Zadania ukończone:</small> <strong>{sec.completed_tasks_count}</strong></div>
                        <div><small style={{ color: "#60716c" }}>Czas szacowany:</small> <strong>{sec.estimated_minutes} min</strong></div>
                        <div><small style={{ color: "#60716c" }}>Czas rzeczywisty:</small> <strong>{sec.actual_minutes} min</strong></div>
                      </div>
                      <h4 style={{ margin: "0 0 10px 0", fontSize: "12px", color: "#60716c", textTransform: "uppercase" }}>Pozycje wydane w sekcji</h4>
                      <div className="report-row-list">
                        {sec.sold_items.map((item) => (
                          <div key={item.product_id} className="report-row" style={{ padding: "8px 12px" }}>
                            <div>
                              <strong>{item.product_name}</strong>
                              <span>Ilość: {item.quantity}</span>
                            </div>
                            <b>{formatMoney(Number(item.total))}</b>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
                {productionReport.sections.length === 0 && (
                  <div className="module-placeholder">Brak zadań w wybranym dniu dla tej sekcji.</div>
                )}
              </div>
            </>
          )}

          {/* TAB: WAREHOUSE */}
          {activeTab === "warehouse" && warehouseReport && (
            <>
              {/* Summary */}
              <div className="report-metrics-grid" style={{ gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "20px" }}>
                <div className="report-metric-card">
                  <span>Liczba dokumentów</span>
                  <strong>{warehouseReport.document_count}</strong>
                </div>
                <div className="report-metric-card">
                  <span>Łączna liczba pozycji</span>
                  <strong>{warehouseReport.total_positions_count}</strong>
                </div>
              </div>

              {warehouseReport.unit_breakdown && warehouseReport.unit_breakdown.length > 0 && (
                <div style={{ background: "#ffffff", padding: "16px", borderRadius: "8px", border: "1px solid #d7dfda", marginBottom: "20px" }}>
                  <span style={{ fontSize: "11px", color: "#60716c", display: "block", marginBottom: "8px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                    Łączny obrót według jednostek miar
                  </span>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                    {warehouseReport.unit_breakdown.map((item) => (
                      <div key={item.unit} style={{ padding: "6px 12px", background: "#f8faf9", borderRadius: "6px", fontSize: "13px", border: "1px solid #eef1ef" }}>
                        <strong style={{ color: "#10b066" }}>{numberFormat.format(item.total_quantity)}</strong>{" "}
                        <span style={{ color: "#60716c" }}>{item.unit}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Documents table */}
              <div style={{ background: "#ffffff", padding: "20px", borderRadius: "8px", border: "1px solid #d7dfda" }}>
                <h3 style={{ margin: "0 0 16px 0", fontSize: "16px" }}>Spis dokumentów magazynowych</h3>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                    <thead>
                      <tr style={{ background: "#f8faf9", borderBottom: "1px solid #d7dfda", textAlign: "left" }}>
                        <th style={{ padding: "10px 12px" }}>Numer</th>
                        <th style={{ padding: "10px 12px" }}>Typ</th>
                        <th style={{ padding: "10px 12px" }}>Data operacji</th>
                        <th style={{ padding: "10px 12px" }}>Źródło</th>
                        <th style={{ padding: "10px 12px" }}>Cel</th>
                        <th style={{ padding: "10px 12px" }}>Wystawił</th>
                        <th style={{ padding: "10px 12px", textAlign: "right" }}>Pozycje</th>
                        <th style={{ padding: "10px 12px" }}>Szczegóły</th>
                      </tr>
                    </thead>
                    <tbody>
                      {warehouseReport.documents.map((doc) => (
                        <tr key={doc.id} style={{ borderBottom: "1px solid #eef1ef" }}>
                          <td style={{ padding: "10px 12px", fontWeight: "600" }}>{doc.document_number}</td>
                          <td style={{ padding: "10px 12px" }}>
                            {doc.document_type === "PZ" && "Przyjęcie (PZ)"}
                            {doc.document_type === "MM" && "Przesunięcie (MM)"}
                            {doc.document_type === "RW" && "Spisanie (RW)"}
                            {doc.document_type === "RW_AUTO" && "Automatyczny (RW_AUTO)"}
                            {doc.document_type === "INW" && "Inwentaryzacja (INW)"}
                          </td>
                          <td style={{ padding: "10px 12px" }}>{doc.operation_date}</td>
                          <td style={{ padding: "10px 12px" }}>{doc.source_warehouse_name || "—"}</td>
                          <td style={{ padding: "10px 12px" }}>{doc.destination_warehouse_name || "—"}</td>
                          <td style={{ padding: "10px 12px" }}>{doc.issued_by_user_name || "System"}</td>
                          <td style={{ padding: "10px 12px", textAlign: "right", fontWeight: "700" }}>{doc.items_count}</td>
                          <td style={{ padding: "10px 12px" }}>
                            <button
                              type="button"
                              className="ghost-button"
                              onClick={() => setActiveWarehouseDoc(doc)}
                              style={{ padding: "4px 8px", fontSize: "11px", minHeight: "26px" }}
                            >
                              Szczegóły
                            </button>
                          </td>
                        </tr>
                      ))}
                      {warehouseReport.documents.length === 0 && (
                        <tr>
                          <td colSpan={8} style={{ padding: "16px", textAnchor: "middle", textAlign: "center" }} className="muted">
                            Brak dokumentów magazynowych w tym okresie.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {/* TAB: ACTION LOGS */}
          {activeTab === "logs" && (
            <div style={{ background: "#ffffff", padding: "20px", borderRadius: "8px", border: "1px solid #d7dfda" }}>
              <h3 style={{ margin: "0 0 16px 0", fontSize: "16px" }}>Chronologiczny dziennik działań</h3>
              <div style={{ display: "grid", gap: "10px" }}>
                {actionLogs.map((log) => (
                  <div key={log.id} style={{ display: "flex", justifySelf: "stretch", justifyContent: "space-between", padding: "12px 16px", border: "1px solid #eef1ef", borderRadius: "6px", fontSize: "13px" }}>
                    <div>
                      <div style={{ display: "flex", gap: "10px", alignItems: "center", marginBottom: "4px" }}>
                        <strong style={{ color: "var(--brand-green)" }}>{log.action_type}</strong>
                        <span style={{ fontSize: "11px", color: "#60716c" }}>
                          Użytkownik: <b>{log.user_name}</b>
                        </span>
                        {log.order_id && (
                          <span style={{ fontSize: "11px", color: "#60716c" }}>
                            Zamówienie: <b>#{log.order_id}</b>
                          </span>
                        )}
                      </div>
                      <p style={{ margin: 0, color: "#172026" }}>{log.description || "Brak dodatkowego opisu."}</p>
                    </div>
                    <span style={{ fontSize: "11px", color: "#60716c" }}>
                      {new Date(log.created_at).toLocaleTimeString("pl-PL")}
                    </span>
                  </div>
                ))}
                {actionLogs.length === 0 && (
                  <p className="muted" style={{ textAlign: "center", padding: "20px" }}>
                    Brak zarejestrowanych logów z tego dnia dla wybranych filtrów.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Warehouse Document details modal */}
      {activeWarehouseDoc && (
        <div className="admin-modal-backdrop" onClick={() => setActiveWarehouseDoc(null)}>
          <section
            className="admin-modal warehouse-modal"
            style={{
              maxWidth: activeWarehouseDoc.document_type === "INW" ? "1000px" : "600px",
              width: "100%",
              padding: "24px",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="modal-close-icon"
              title="Zamknij"
              onClick={() => setActiveWarehouseDoc(null)}
              style={{
                position: "absolute",
                top: "16px",
                right: "16px",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                color: "#64748b",
              }}
            >
              <X size={20} />
            </button>
            <h2 style={{ fontSize: "1.5rem", fontWeight: "600", marginBottom: "16px" }}>Szczegóły dokumentu: {activeWarehouseDoc.document_number}</h2>
            <div className="warehouse-document-meta" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "20px", marginTop: "16px" }}>
              <div>
                <strong>Typ dokumentu:</strong> {activeWarehouseDoc.document_type}
              </div>
              <div>
                <strong>Status:</strong> {activeWarehouseDoc.status}
              </div>
              <div>
                <strong>Magazyn źródłowy:</strong> {activeWarehouseDoc.source_warehouse_name ?? "—"}
              </div>
              <div>
                <strong>Magazyn docelowy:</strong> {activeWarehouseDoc.destination_warehouse_name ?? "—"}
              </div>
              <div>
                <strong>Wystawił:</strong> {activeWarehouseDoc.issued_by_user_name ?? "System"}
              </div>
              <div>
                <strong>Data operacji:</strong> {activeWarehouseDoc.operation_date}
              </div>
              {activeWarehouseDoc.reason && (
                <div style={{ gridColumn: "1 / -1" }}>
                  <strong>{activeWarehouseDoc.document_type === "INW" ? "Rodzaj / podstawa:" : "Powód RW:"}</strong> {activeWarehouseDoc.reason}
                </div>
              )}
              {activeWarehouseDoc.description && (
                <div style={{ gridColumn: "1 / -1" }}>
                  <strong>Uwagi:</strong> {activeWarehouseDoc.description}
                </div>
              )}
            </div>

            <h3 style={{ margin: "20px 0 10px 0", fontSize: "1.1rem", fontWeight: "600" }}>Pozycje dokumentu</h3>
            <div style={{ maxHeight: "350px", overflow: "auto", border: "1px solid #edf2f7", borderRadius: "8px", padding: "8px", background: "rgba(0,0,0,0.01)" }}>
              <table style={{ width: "100%", minWidth: activeWarehouseDoc.document_type === "INW" ? "820px" : undefined, borderCollapse: "collapse", fontSize: "0.9rem" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #cbd5e0", textAlign: "left" }}>
                    <th style={{ padding: "6px" }}>Towar</th>
                    {activeWarehouseDoc.document_type === "INW" ? (
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
                        {activeWarehouseDoc.document_type === "PZ" && (
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
                  {(activeWarehouseDoc.items || []).map((item) => (
                    <tr key={item.id} style={{ borderBottom: "1px solid #edf2f7" }}>
                      <td style={{ padding: "6px" }}>{item.ingredient_name}</td>
                      {activeWarehouseDoc.document_type === "INW" ? (
                        <>
                          <td style={{ padding: "6px", textAlign: "right" }}>{formatQuantity(item.book_quantity, item.unit)}</td>
                          <td style={{ padding: "6px", textAlign: "right" }}>{formatQuantity(item.actual_quantity, item.unit)}</td>
                          <td style={{ padding: "6px", textAlign: "right" }}>{formatSignedQuantity(item.difference_quantity, item.unit)}</td>
                          <td style={{ padding: "6px", textAlign: "right" }}>
                            {item.unit_price ? `${Number(item.unit_price).toFixed(2)} PLN` : "—"}
                          </td>
                          <td style={{ padding: "6px", textAlign: "right" }}>
                            {formatSignedMoney(item.difference_value)}
                          </td>
                        </>
                      ) : (
                        <>
                          <td style={{ padding: "6px", textAlign: "right" }}>{Number(item.quantity)} {item.unit}</td>
                          {activeWarehouseDoc.document_type === "PZ" && (
                            <>
                              <td style={{ padding: "6px", textAlign: "right" }}>
                                {item.unit_price ? `${Number(item.unit_price).toFixed(2)} PLN` : "—"}
                              </td>
                              <td style={{ padding: "6px", textAlign: "right" }}>
                                {item.total_value ? `${Number(item.total_value).toFixed(2)} PLN` : "—"}
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
              <button type="button" className="ghost-button" onClick={() => setActiveWarehouseDoc(null)}>
                Zamknij
              </button>
              <button
                type="button"
                className="admin-primary"
                disabled={downloadingDocumentId === activeWarehouseDoc.id}
                onClick={() => void downloadDocument(activeWarehouseDoc)}
                style={{ display: "flex", alignItems: "center", gap: "6px" }}
              >
                <Download size={17} />
                {downloadingDocumentId === activeWarehouseDoc.id ? "Generowanie..." : "Pobierz PDF"}
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

function SVGRevenueChart({
  data,
  averageCheck,
  averageDailySales,
}: {
  data: { label: string; value: number | string }[];
  averageCheck: number | string;
  averageDailySales: number | string;
}) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const width = 800;
  const height = 300;
  const paddingLeft = 60;
  const paddingRight = 20;
  const paddingTop = 30;
  const paddingBottom = 40;

  const plotWidth = width - paddingLeft - paddingRight;
  const plotHeight = height - paddingTop - paddingBottom;

  const maxVal = useMemo(() => {
    const vals = data.map((d) => Number(d.value));
    const max = Math.max(...vals, 100);
    return max * 1.15; // 15% padding on top
  }, [data]);

  const avgCheckNum = Number(averageCheck);
  const avgDailyNum = Number(averageDailySales);
  const yAvgCheck = height - paddingBottom - (avgCheckNum / maxVal) * plotHeight;
  const yAvgDaily = height - paddingBottom - (avgDailyNum / maxVal) * plotHeight;

  // Grid lines (Y axis splits)
  const gridLines = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div style={{ position: "relative", width: "100%", background: "#ffffff", padding: "16px", borderRadius: "8px", border: "1px solid #d7dfda" }}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="100%">
        {/* Gradients */}
        <defs>
          <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10b066" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#dcf5e8" stopOpacity="0.3" />
          </linearGradient>
          <linearGradient id="barGradHover" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0d8f52" stopOpacity="1" />
            <stop offset="100%" stopColor="#bcecd1" stopOpacity="0.6" />
          </linearGradient>
        </defs>

        {/* Grid lines & Y axis labels */}
        {gridLines.map((ratio) => {
          const y = height - paddingBottom - ratio * plotHeight;
          const labelVal = ratio * maxVal;
          return (
            <g key={ratio}>
              <line x1={paddingLeft} y1={y} x2={width - paddingRight} y2={y} stroke="#e2e8f0" strokeWidth={1} strokeDasharray="3,3" />
              <text x={paddingLeft - 8} y={y + 4} textAnchor="end" fontSize="10" fill="#64748b" fontFamily="sans-serif">
                {formatMoneyCompact(labelVal)}
              </text>
            </g>
          );
        })}

        {/* Columns */}
        {data.map((d, idx) => {
          const colWidth = (plotWidth / data.length) * 0.75;
          const gap = (plotWidth / data.length) * 0.25;
          const x = paddingLeft + idx * (plotWidth / data.length) + gap / 2;
          const colVal = Number(d.value);
          const colHeight = (colVal / maxVal) * plotHeight;
          const y = height - paddingBottom - colHeight;

          return (
            <g
              key={idx}
              onMouseEnter={() => setHoveredIdx(idx)}
              onMouseLeave={() => setHoveredIdx(null)}
              style={{ cursor: "pointer" }}
            >
              <rect
                x={x}
                y={y}
                width={colWidth}
                height={Math.max(colHeight, 2)}
                fill={hoveredIdx === idx ? "url(#barGradHover)" : "url(#barGrad)"}
                stroke={hoveredIdx === idx ? "#10b066" : "transparent"}
                strokeWidth={1}
                rx={Math.min(colWidth / 4, 4)}
                ry={Math.min(colWidth / 4, 4)}
                style={{ transition: "fill 0.2s, stroke 0.2s" }}
              />
              {/* X axis labels */}
              {data.length <= 15 || idx % 2 === 0 ? (
                <text
                  x={x + colWidth / 2}
                  y={height - paddingBottom + 16}
                  textAnchor="middle"
                  fontSize="10"
                  fill="#64748b"
                  fontFamily="sans-serif"
                >
                  {formatLabelShort(d.label, data.length)}
                </text>
              ) : null}
            </g>
          );
        })}

        {/* Average Check Line */}
        {avgCheckNum > 0 && (
          <g>
            <line
              x1={paddingLeft}
              y1={yAvgCheck}
              x2={width - paddingRight}
              y2={yAvgCheck}
              stroke="#f59e0b"
              strokeWidth={2}
              strokeDasharray="4,4"
            />
            <text
              x={paddingLeft + 8}
              y={yAvgCheck - 6}
              textAnchor="start"
              fontSize="11"
              fontWeight="600"
              fill="#f59e0b"
              fontFamily="sans-serif"
            >
              Śr. rachunek: {formatMoneyCompact(avgCheckNum)}
            </text>
          </g>
        )}

        {/* Average Daily Sales Line */}
        {avgDailyNum > 0 && (
          <g>
            <line
              x1={paddingLeft}
              y1={yAvgDaily}
              x2={width - paddingRight}
              y2={yAvgDaily}
              stroke="#ff5157"
              strokeWidth={2}
              strokeDasharray="6,4"
            />
            <text
              x={width - paddingRight - 8}
              y={yAvgDaily - 6}
              textAnchor="end"
              fontSize="11"
              fontWeight="600"
              fill="#ff5157"
              fontFamily="sans-serif"
            >
              Śr. dzienna sprzedaż: {formatMoneyCompact(avgDailyNum)}
            </text>
          </g>
        )}
      </svg>

      {/* Tooltip */}
      {hoveredIdx !== null && (
        <div
          style={{
            position: "absolute",
            top: "8px",
            right: "8px",
            background: "#1e293b",
            color: "#ffffff",
            padding: "8px 12px",
            borderRadius: "6px",
            fontSize: "12px",
            boxShadow: "0 4px 6px rgba(0,0,0,0.1)",
            pointerEvents: "none",
            zIndex: 10,
            fontFamily: "sans-serif",
          }}
        >
          <strong>{data[hoveredIdx].label}</strong>
          <div style={{ marginTop: "2px" }}>Przychód: <b>{formatMoney(data[hoveredIdx].value)}</b></div>
        </div>
      )}
    </div>
  );
}

function formatLabelShort(label: string, totalCount: number): string {
  if (totalCount > 15) {
    if (label.includes("-") && label.length === 10) {
      return label.split("-")[2];
    }
  }
  // format YYYY-MM label
  if (label.length === 7 && label.includes("-")) {
    const [, month] = label.split("-");
    const monthNames = [
      "Sty", "Lut", "Mar", "Kwi", "Maj", "Cze", 
      "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"
    ];
    return monthNames[Number(month) - 1] || label;
  }
  return label;
}

function formatMoneyCompact(val: number | string | null | undefined): string {
  const num = Number(val);
  if (isNaN(num)) return "0 zł";
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M zł`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}k zł`;
  return `${num.toFixed(0)} zł`;
}

function formatMoney(value: number | string | null | undefined): string {
  const num = Number(value);
  if (isNaN(num)) return "0,00 zł";
  return new Intl.NumberFormat("pl-PL", {
    style: "currency",
    currency: "PLN",
  }).format(num);
}

const numberFormat = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 3 });
const moneyFormat = new Intl.NumberFormat("pl-PL", { style: "currency", currency: "PLN" });

function signedNumber(value: number): string {
  if (value === 0) return "0";
  return `${value > 0 ? "+" : ""}${numberFormat.format(value)}`;
}

function formatQuantity(value: string | number | null, unit: string): string {
  return value === null || value === undefined ? "—" : `${numberFormat.format(Number(value))} ${unit}`;
}

function formatSignedQuantity(value: string | number | null, unit: string): string {
  if (value === null || value === undefined) return "—";
  return `${signedNumber(Number(value))} ${unit}`;
}

function formatSignedMoney(value: string | number | null): string {
  if (value === null || value === undefined) return "—";
  const parsed = Number(value);
  return `${parsed > 0 ? "+" : ""}${moneyFormat.format(parsed)}`;
}
