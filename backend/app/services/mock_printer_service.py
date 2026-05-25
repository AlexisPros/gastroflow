from pathlib import Path

from app.core.config import settings


class MockPrinterService:
    def print_receipt_to_pdf(
        self,
        *,
        order_id: int,
        receipt_content: str,
    ) -> Path:
        from fpdf import FPDF

        output_dir = Path(settings.RECEIPTS_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"receipt_order_{order_id}.pdf"

        pdf = FPDF(unit="mm", format=(80, 220))
        pdf.set_auto_page_break(auto=True, margin=6)
        pdf.add_page()
        pdf.set_margins(left=4, top=4, right=4)
        pdf.set_font("Courier", size=9)

        for line in receipt_content.splitlines():
            pdf.multi_cell(w=72, h=4, text=line)

        pdf.output(str(output_path))

        return output_path


mock_printer_service = MockPrinterService()
