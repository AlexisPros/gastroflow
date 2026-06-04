import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../api/apiClient";
import { getCurrentShift, getCurrentShiftReport, type EmployeeShiftReport } from "../api/shiftApi";
import { useAuth } from "../auth/useAuth";

type LoadingState = "idle" | "loading" | "ready" | "error";

export function ReportsPage() {
  const { token, user } = useAuth();
  const [report, setReport] = useState<EmployeeShiftReport | null>(null);
  const [status, setStatus] = useState<LoadingState>("idle");
  const [error, setError] = useState<string | null>(null);

  const loadReport = useCallback(async () => {
    if (!token) {
      return;
    }

    setStatus((current) => (current === "ready" ? current : "loading"));
    setError(null);
    try {
      const currentShift = await getCurrentShift(token);
      if (!currentShift) {
        setReport(null);
        setStatus("ready");
        return;
      }

      setReport(await getCurrentShiftReport(token));
      setStatus("ready");
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not load report.");
      setStatus("error");
    }
  }, [token]);

  useEffect(() => {
    void loadReport();
  }, [loadReport]);

  if (user?.role === "ADMIN" || user?.role === "MANAGER") {
    return (
      <section className="page-stack">
        <div>
          <span className="eyebrow">Reports</span>
          <h1>Management reports</h1>
          <p className="muted">Daily sales, kitchen and bar reports will be opened here.</p>
        </div>
        <div className="module-placeholder">
          <strong>Ready for implementation</strong>
          <p>The waiter live shift report is already available for service staff.</p>
        </div>
      </section>
    );
  }

  if (status === "idle" || status === "loading") {
    return (
      <section className="page-stack">
        <ReportsHeader onRefresh={loadReport} />
        <div className="module-placeholder">Loading shift report...</div>
      </section>
    );
  }

  if (status === "error") {
    return (
      <section className="page-stack">
        <ReportsHeader onRefresh={loadReport} />
        <div className="error-box">{error}</div>
      </section>
    );
  }

  if (!report) {
    return (
      <section className="page-stack">
        <ReportsHeader onRefresh={loadReport} />
        <div className="module-placeholder">
          <strong>No active shift</strong>
          <p>Start a shift to see live sales, tips, payments and sold items.</p>
        </div>
      </section>
    );
  }

  const soldItems = report.report_data.sold_items ?? [];
  const discounts = report.report_data.discounts ?? [];
  const paymentMethods = report.report_data.payment_methods ?? [];

  return (
    <section className="page-stack">
      <ReportsHeader onRefresh={loadReport} />

      <div className="report-metrics-grid">
        <MetricCard label="Sales" value={formatMoney(Number(report.total_sales))} />
        <MetricCard label="Tips" value={formatMoney(Number(report.total_tips))} />
        <MetricCard label="Discounts" value={formatMoney(Number(report.total_discounts))} />
        <MetricCard label="Orders" value={String(report.orders_count)} />
        <MetricCard label="Items" value={String(report.items_count)} />
        <MetricCard label="Card" value={formatMoney(Number(report.card_total))} />
        <MetricCard label="Cash" value={formatMoney(Number(report.cash_total))} />
        <MetricCard label="Other" value={formatMoney(Number(report.other_payment_total))} />
      </div>

      <div className="report-section-grid">
        <ReportTable
          title="Sold items"
          emptyText="No sold items yet."
          rows={soldItems.map((item) => ({
            label: item.product_name,
            meta: `${item.quantity} sold`,
            value: formatMoney(Number(item.total)),
          }))}
        />
        <ReportTable
          title="Discounts"
          emptyText="No discounts used yet."
          rows={discounts.map((discount) => ({
            label: discount.name,
            meta: `${discount.uses} uses`,
            value: formatMoney(Number(discount.total_discount_amount)),
          }))}
        />
        <ReportTable
          title="Payments"
          emptyText="No payments completed yet."
          rows={paymentMethods.map((payment) => ({
            label: payment.method,
            meta: `${payment.count} payments`,
            value: formatMoney(Number(payment.total)),
          }))}
        />
      </div>
    </section>
  );
}

function ReportsHeader({ onRefresh }: { onRefresh: () => void }) {
  return (
    <div className="floor-header">
      <div>
        <span className="eyebrow">RAPORTY</span>
        <h1>Obecna zmiana</h1>
      </div>
      <button type="button" className="ghost-button" onClick={onRefresh}>
        Odśwież
      </button>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="report-metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ReportTable({
  title,
  emptyText,
  rows,
}: {
  title: string;
  emptyText: string;
  rows: Array<{ label: string; meta: string; value: string }>;
}) {
  return (
    <div className="report-table-card">
      <h2>{title}</h2>
      <div className="report-row-list">
        {rows.map((row) => (
          <div key={`${row.label}-${row.meta}`} className="report-row">
            <div>
              <strong>{row.label}</strong>
              <span>{row.meta}</span>
            </div>
            <b>{row.value}</b>
          </div>
        ))}
        {rows.length === 0 && <p className="muted">{emptyText}</p>}
      </div>
    </div>
  );
}

function formatMoney(value: number): string {
  return new Intl.NumberFormat("pl-PL", {
    style: "currency",
    currency: "PLN",
  }).format(value);
}
