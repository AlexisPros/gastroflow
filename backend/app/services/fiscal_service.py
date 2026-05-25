from datetime import datetime, timezone
from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product


class FiscalService:
    async def generate_html_receipt(
        self,
        db: AsyncSession,
        *,
        order: Order,
    ) -> str:
        rows = await self._get_receipt_rows(db, order=order)
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        item_rows = "\n".join(
            self._render_item_row(order_item=order_item, product=product)
            for order_item, product in rows
        )

        return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <style>
    @page {{
      size: 80mm auto;
      margin: 4mm;
    }}

    body {{
      color: #111;
      font-family: "Courier New", monospace;
      font-size: 10px;
      line-height: 1.25;
      margin: 0;
      width: 72mm;
    }}

    .center {{
      text-align: center;
    }}

    .title {{
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0;
      margin-bottom: 2mm;
    }}

    .muted {{
      color: #444;
      font-size: 9px;
    }}

    .rule {{
      border-top: 1px dashed #111;
      margin: 3mm 0;
    }}

    .row {{
      display: table;
      width: 100%;
    }}

    .cell {{
      display: table-cell;
      vertical-align: top;
    }}

    .right {{
      text-align: right;
      white-space: nowrap;
    }}

    .total {{
      font-size: 12px;
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <div class="center title">GASTROFLOW</div>
  <div class="center">PARAGON NIEFISKALNY</div>
  <div class="center muted">Mock printer output</div>

  <div class="rule"></div>
  <div>Order: #{order.id}</div>
  <div>Date: {created_at}</div>
  <div>Source: {escape(order.source)}</div>
  <div class="rule"></div>

  {item_rows}

  <div class="rule"></div>
  <div class="row total">
    <div class="cell">TOTAL</div>
    <div class="cell right">{order.total_amount:.2f}</div>
  </div>
  <div class="row">
    <div class="cell">TIP</div>
    <div class="cell right">{order.tip_amount:.2f}</div>
  </div>
  <div class="rule"></div>

  <div class="center muted">
    This document is not a fiscal receipt.<br>
    Generated for GastroFlow prototype.
  </div>
</body>
</html>"""

    async def generate_text_receipt(
        self,
        db: AsyncSession,
        *,
        order: Order,
    ) -> str:
        rows = await self._get_receipt_rows(db, order=order)

        lines = [
            "GASTROFLOW",
            "PARAGON NIEFISKALNY",
            f"Order: #{order.id}",
            f"Date: {datetime.now(timezone.utc).isoformat()}",
            "-" * 32,
        ]

        for order_item, product in rows:
            lines.append(
                f"{product.name} x{order_item.quantity} "
                f"{order_item.total_price:.2f}",
            )

        lines.extend(
            [
                "-" * 32,
                f"TOTAL: {order.total_amount:.2f}",
                f"TIP: {order.tip_amount:.2f}",
                "This document is not a fiscal receipt.",
            ],
        )

        return "\n".join(lines)

    async def _get_receipt_rows(
        self,
        db: AsyncSession,
        *,
        order: Order,
    ):
        result = await db.execute(
            select(OrderItem, Product)
            .join(Product, OrderItem.product_id == Product.id)
            .where(OrderItem.order_id == order.id),
        )
        return result.all()

    def _render_item_row(self, *, order_item: OrderItem, product: Product) -> str:
        product_name = escape(product.name)

        return f"""
  <div class="row">
    <div class="cell">{product_name}</div>
    <div class="cell right">{order_item.total_price:.2f}</div>
  </div>
  <div class="row muted">
    <div class="cell">x{order_item.quantity} @ {order_item.unit_price:.2f}</div>
    <div class="cell right"></div>
  </div>"""


fiscal_service = FiscalService()
