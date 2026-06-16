from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product

MONEY = Decimal("0.01")
VAT_RATE_LETTERS = {
    Decimal("23.00"): "A",
    Decimal("8.00"): "B",
}


class FiscalService:
    async def generate_html_receipt(
        self,
        db: AsyncSession,
        *,
        order: Order,
    ) -> str:
        receipt = await self.generate_text_receipt(db, order=order)
        escaped_receipt = escape(receipt)

        return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <style>
    body {{
      background: #f4f7f5;
      margin: 0;
      padding: 24px;
    }}

    pre {{
      width: 72mm;
      min-height: 180mm;
      margin: 0 auto;
      padding: 4mm;
      background: #ffffff;
      color: #111111;
      font-family: "Courier New", monospace;
      font-size: 10px;
      line-height: 1.25;
      white-space: pre-wrap;
    }}
  </style>
</head>
<body>
  <pre>{escaped_receipt}</pre>
</body>
</html>"""

    async def generate_guest_check_text(
        self,
        db: AsyncSession,
        *,
        order: Order,
    ) -> str:
        rows = await self._get_receipt_rows(db, order=order)
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        lines = [
            "GastroFlow",
            "RACHUNEK NIEFISKALNY",
            f"Rachunek: GF-{order.id:06d}",
            f"Order: #{order.id}",
            f"Date: {created_at}",
            "-" * 40,
        ]

        for order_item, product in rows:
            lines.append(product.name)
            lines.append(
                f"  {order_item.quantity} x {order_item.unit_price:.2f} "
                f"{order_item.total_price:.2f}",
            )

        lines.extend(
            [
                "-" * 40,
                f"Subtotal: {order.subtotal_amount:.2f}",
                f"Discount: -{order.discount_amount:.2f}",
                f"Tip: {order.tip_amount:.2f}",
                f"Total: {order.total_amount:.2f}",
                "-" * 40,
                "Dokument niefiskalny.",
            ],
        )

        return "\n".join(lines)

    async def generate_text_receipt(
        self,
        db: AsyncSession,
        *,
        order: Order,
    ) -> str:
        rows = await self._get_receipt_rows(db, order=order)
        invoice = await self._get_order_invoice(db, order=order)
        vat_summary = self.calculate_vat_summary(rows=rows, order=order)
        fiscal_total = sum(
            (summary["gross"] for summary in vat_summary.values()),
            Decimal("0.00"),
        )
        total_tax = sum(
            (summary["tax"] for summary in vat_summary.values()),
            Decimal("0.00"),
        )
        receipt_number = f"{order.id:06d}/{datetime.now(timezone.utc):%Y%m%d}"

        lines = [
            "GASTROFLOW SP. Z O.O.",
            "ul. Demo 1",
            "00-000 Warszawa",
            "NIP 0000000000",
            "-" * 32,
            "PARAGON FISKALNY",
            f"NR WYDRUKU {receipt_number}",
            f"DATA {datetime.now(timezone.utc):%Y-%m-%d %H:%M}",
        ]

        if invoice is not None:
            lines.append(f"NIP NABYWCY {invoice.nip}")

        lines.append("-" * 32)

        for order_item, product in rows:
            rate = self._normalize_rate(product.vat_rate)
            vat_letter = self._vat_letter(rate)
            lines.extend(
                [
                    self._fit_line(
                        product.name[:22],
                        f"{order_item.total_price:.2f}{vat_letter}",
                    ),
                    f"  {order_item.quantity} x {order_item.unit_price:.2f}",
                ],
            )

        if order.discount_amount > Decimal("0.00"):
            lines.append(self._fit_line("RABAT", f"-{order.discount_amount:.2f}"))

        lines.append("-" * 32)
        for rate, summary in vat_summary.items():
            vat_letter = self._vat_letter(rate)
            lines.append(
                self._fit_line(
                    f"SP.OP.{vat_letter} {rate:.2f}%",
                    f"{summary['gross']:.2f}",
                ),
            )
            lines.append(
                self._fit_line(
                    f"PTU {vat_letter} {rate:.2f}%",
                    f"{summary['tax']:.2f}",
                ),
            )

        lines.extend(
            [
                "-" * 32,
                self._fit_line("SUMA PTU", f"{total_tax:.2f}"),
                self._fit_line("SUMA PLN", f"{fiscal_total:.2f}"),
                self._fit_line("ZAPLACONO", f"{fiscal_total:.2f}"),
                "-" * 32,
                "PL 0000000000",
                "BF 0000000000",
                "DZIEKUJEMY",
            ],
        )

        return "\n".join(lines)

    def calculate_vat_summary(
        self,
        *,
        rows: list[tuple[OrderItem, Product]],
        order: Order,
    ) -> dict[Decimal, dict[str, Decimal]]:
        discounted_rows = self._apply_order_discount_to_rows(rows=rows, order=order)
        summary: dict[Decimal, dict[str, Decimal]] = {}

        for gross, product in discounted_rows:
            rate = self._normalize_rate(product.vat_rate)
            tax = self._round_money(gross * rate / (Decimal("100.00") + rate))
            net = gross - tax

            if rate not in summary:
                summary[rate] = {
                    "gross": Decimal("0.00"),
                    "net": Decimal("0.00"),
                    "tax": Decimal("0.00"),
                }

            summary[rate]["gross"] += gross
            summary[rate]["net"] += net
            summary[rate]["tax"] += tax

        return {
            rate: {
                "gross": self._round_money(values["gross"]),
                "net": self._round_money(values["net"]),
                "tax": self._round_money(values["tax"]),
            }
            for rate, values in sorted(summary.items(), reverse=True)
        }

    async def _get_receipt_rows(
        self,
        db: AsyncSession,
        *,
        order: Order,
    ) -> list[tuple[OrderItem, Product]]:
        result = await db.execute(
            select(OrderItem, Product)
            .join(Product, OrderItem.product_id == Product.id)
            .where(OrderItem.order_id == order.id)
            .order_by(OrderItem.position.asc(), OrderItem.id.asc()),
        )
        return [(order_item, product) for order_item, product in result.all()]

    async def _get_order_invoice(
        self,
        db: AsyncSession,
        *,
        order: Order,
    ) -> Invoice | None:
        result = await db.execute(
            select(Invoice).where(Invoice.order_id == order.id),
        )
        return result.scalar_one_or_none()

    def _apply_order_discount_to_rows(
        self,
        *,
        rows: list[tuple[OrderItem, Product]],
        order: Order,
    ) -> list[tuple[Decimal, Product]]:
        if not rows:
            return []

        subtotal = sum(
            (order_item.total_price for order_item, _product in rows),
            Decimal("0.00"),
        )
        discount = min(order.discount_amount, subtotal)
        if subtotal <= Decimal("0.00") or discount <= Decimal("0.00"):
            return [(self._round_money(order_item.total_price), product) for order_item, product in rows]

        discounted_rows: list[tuple[Decimal, Product]] = []
        allocated_discount = Decimal("0.00")

        for index, (order_item, product) in enumerate(rows):
            if index == len(rows) - 1:
                row_discount = discount - allocated_discount
            else:
                row_discount = self._round_money(order_item.total_price / subtotal * discount)
                allocated_discount += row_discount

            discounted_rows.append(
                (
                    self._round_money(order_item.total_price - row_discount),
                    product,
                ),
            )

        return discounted_rows

    def _vat_letter(self, rate: Decimal) -> str:
        return VAT_RATE_LETTERS.get(rate, "C")

    def _normalize_rate(self, rate: Decimal) -> Decimal:
        return Decimal(rate).quantize(MONEY, rounding=ROUND_HALF_UP)

    def _round_money(self, amount: Decimal) -> Decimal:
        return Decimal(amount).quantize(MONEY, rounding=ROUND_HALF_UP)

    def _fit_line(self, left: str, right: str, *, width: int = 32) -> str:
        left = left.strip()
        right = right.strip()
        gap = max(width - len(left) - len(right), 1)
        return f"{left}{' ' * gap}{right}"


fiscal_service = FiscalService()
