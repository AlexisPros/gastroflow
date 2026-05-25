from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.invoice import Invoice
from app.models.order import Order


class InvoiceService:
    async def create_invoice(
        self,
        db: AsyncSession,
        *,
        order: Order,
        nip: str,
        company_name: str,
    ) -> Invoice:
        existing_invoice = await self.get_by_order(db, order_id=order.id)
        if existing_invoice is not None:
            raise ValueError("Invoice already exists for this order.")

        invoice = Invoice(
            order_id=order.id,
            nip=nip,
            company_name=company_name,
            invoice_number=self.generate_invoice_number(order_id=order.id),
        )

        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)
        return invoice

    def generate_invoice_pdf(self, *, invoice: Invoice, order: Order) -> Path:
        from fpdf import FPDF

        output_dir = Path(settings.RECEIPTS_DIR) / "invoices"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"invoice_order_{order.id}.pdf"

        pdf = FPDF(unit="mm", format="A4")
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)

        pdf.cell(0, 10, "GastroFlow - Faktura VAT (MOCK)", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Invoice number: {invoice.invoice_number}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Order: #{order.id}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Company: {invoice.company_name}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"NIP: {invoice.nip}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Amount: {order.total_amount:.2f}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Status: {invoice.status}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(8)
        pdf.multi_cell(
            0,
            8,
            "This PDF simulates invoice generation for the GastroFlow prototype. "
            "It is not an official accounting document.",
        )

        pdf.output(str(output_path))
        return output_path

    async def send_to_ksef_mock(
        self,
        db: AsyncSession,
        *,
        invoice: Invoice,
    ) -> str:
        reference_number = self.generate_ksef_reference_number(invoice=invoice)
        invoice.status = "SENT_TO_KSEF_MOCK"

        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)
        return reference_number

    async def mark_sent(self, db: AsyncSession, *, invoice: Invoice) -> Invoice:
        invoice.status = "SENT"

        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)
        return invoice

    async def get_by_order(self, db: AsyncSession, *, order_id: int) -> Invoice | None:
        result = await db.execute(
            select(Invoice).where(Invoice.order_id == order_id),
        )
        return result.scalar_one_or_none()

    def generate_invoice_number(self, *, order_id: int) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"FV/{timestamp}/{order_id}"

    def generate_ksef_reference_number(self, *, invoice: Invoice) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"KSEF-MOCK-{timestamp}-{invoice.id}"


invoice_service = InvoiceService()
