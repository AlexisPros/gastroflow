from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace

from app.models.warehouse_document import WarehouseDocument
from app.models.warehouse_document_item import WarehouseDocumentItem


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
REGULAR_FONT = ASSETS_DIR / "fonts" / "DejaVuSans.ttf"
BOLD_FONT = ASSETS_DIR / "fonts" / "DejaVuSans-Bold.ttf"
LOGO_PATH = ASSETS_DIR / "logo.png"

NAVY = (19, 51, 86)
GREEN = (18, 174, 98)
GREEN_SOFT = (232, 247, 239)
INK = (25, 32, 38)
MUTED = (93, 111, 104)
BORDER = (211, 222, 216)
TABLE_ALT = (247, 250, 248)


class WarehouseDocumentPdf(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("DejaVu", size=7)
        self.set_text_color(*MUTED)
        self.cell(0, 5, f"GastroFlow  |  strona {self.page_no()}/{{nb}}", align="C")


class WarehouseDocumentPdfService:
    def generate(self, document: WarehouseDocument) -> bytes:
        pdf = WarehouseDocumentPdf(unit="mm", format="A4")
        pdf.set_margins(15, 12, 15)
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_font("DejaVu", fname=str(REGULAR_FONT))
        pdf.add_font("DejaVu", style="B", fname=str(BOLD_FONT))
        pdf.alias_nb_pages()
        pdf.add_page()

        self._draw_header(pdf, document)
        self._draw_metadata(pdf, document)
        self._draw_items(pdf, document)
        self._draw_totals(pdf, document)
        self._draw_signature(pdf, document)

        return bytes(pdf.output())

    def _draw_header(self, pdf: WarehouseDocumentPdf, document: WarehouseDocument) -> None:
        if LOGO_PATH.exists():
            pdf.image(str(LOGO_PATH), x=15, y=11, w=34)

        pdf.set_xy(55, 15)
        pdf.set_font("DejaVu", style="B", size=8)
        pdf.set_text_color(*GREEN)
        pdf.cell(0, 5, "DOKUMENT MAGAZYNOWY")
        pdf.set_xy(55, 21)
        pdf.set_font("DejaVu", style="B", size=18)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 9, document_type_label(document.document_type))
        pdf.set_xy(55, 31)
        pdf.set_font("DejaVu", size=9)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 5, document.document_number)

        pdf.set_draw_color(*GREEN)
        pdf.set_line_width(0.8)
        pdf.line(15, 42, 195, 42)
        pdf.set_y(48)

    def _draw_metadata(self, pdf: WarehouseDocumentPdf, document: WarehouseDocument) -> None:
        issued_at = document.issued_at.astimezone().strftime("%d.%m.%Y, %H:%M")
        metadata = [
            ("Numer dokumentu", document.document_number),
            ("Data operacji", document.operation_date.strftime("%d.%m.%Y")),
            ("Data wystawienia", issued_at),
            ("Magazyn źródłowy", warehouse_name(document.source_warehouse)),
            ("Magazyn docelowy", warehouse_name(document.destination_warehouse)),
            ("Status", "Zatwierdzony" if document.status == "COMPLETED" else document.status),
        ]
        if document.order_id is not None:
            metadata[-1] = ("Powiązane zamówienie", f"#{document.order_id}")

        start_x = 15.0
        start_y = pdf.get_y()
        gap = 3.0
        width = 58.0
        height = 17.0
        for index, (label, value) in enumerate(metadata):
            column = index % 3
            row = index // 3
            self._draw_metadata_box(
                pdf,
                x=start_x + column * (width + gap),
                y=start_y + row * (height + gap),
                width=width,
                height=height,
                label=label,
                value=value,
            )
        pdf.set_y(start_y + 2 * (height + gap) + 2)

        if document.reason:
            self._draw_note(pdf, "Rodzaj / podstawa" if document.document_type == "INW" else "Powód", document.reason)
        if document.description:
            self._draw_note(pdf, "Uwagi", document.description)

        pdf.ln(3)

    def _draw_metadata_box(
        self,
        pdf: WarehouseDocumentPdf,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        label: str,
        value: str,
    ) -> None:
        pdf.set_draw_color(*BORDER)
        pdf.set_fill_color(250, 252, 251)
        pdf.rect(x, y, width, height, style="DF", round_corners=True)
        pdf.set_xy(x + 3, y + 2.5)
        pdf.set_font("DejaVu", style="B", size=6.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(width - 6, 3, label.upper())
        pdf.set_xy(x + 3, y + 7.5)
        pdf.set_font("DejaVu", style="B", size=8.5)
        pdf.set_text_color(*INK)
        pdf.multi_cell(width - 6, 4, value or "—", max_line_height=4)

    def _draw_note(self, pdf: WarehouseDocumentPdf, label: str, value: str) -> None:
        pdf.set_font("DejaVu", style="B", size=7)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 4, label.upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("DejaVu", size=8.5)
        pdf.set_text_color(*INK)
        pdf.multi_cell(0, 4.5, value, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    def _draw_items(self, pdf: WarehouseDocumentPdf, document: WarehouseDocument) -> None:
        pdf.set_font("DejaVu", style="B", size=11)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 7, "Pozycje dokumentu", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

        inventory = document.document_type == "INW"
        headers = (
            ["Lp.", "Towar", "Jedn.", "Stan księg.", "Stan fakt.", "Różnica", "Cena jedn.", "Wartość różnicy"]
            if inventory
            else ["Lp.", "Towar", "Ilość", "Jedn.", "Cena jedn.", "Wartość"]
        )
        widths = (8, 47, 13, 24, 24, 20, 22, 26) if inventory else (10, 72, 27, 18, 26, 27)
        heading_style = FontFace(
            family="DejaVu",
            emphasis="B",
            size_pt=7,
            color=(255, 255, 255),
            fill_color=NAVY,
        )
        pdf.set_font("DejaVu", size=7.5 if inventory else 8)
        pdf.set_text_color(*INK)
        with pdf.table(
            width=180,
            col_widths=widths,
            line_height=5.5,
            headings_style=heading_style,
            repeat_headings=1,
            padding=1.5,
            gutter_height=0,
            text_align="LEFT",
        ) as table:
            heading = table.row()
            for title in headers:
                heading.cell(title, align="CENTER")

            for index, item in enumerate(document.items, start=1):
                row = table.row(style=FontFace(fill_color=TABLE_ALT if index % 2 == 0 else (255, 255, 255)))
                values = inventory_item_values(index, item) if inventory else document_item_values(index, item)
                for column, value in enumerate(values):
                    row.cell(value, align="LEFT" if column == 1 else "RIGHT")

        pdf.ln(4)

    def _draw_totals(self, pdf: WarehouseDocumentPdf, document: WarehouseDocument) -> None:
        total_value = sum((item.total_value or Decimal("0")) for item in document.items)
        difference_value = sum((item.difference_value or Decimal("0")) for item in document.items)

        pdf.set_fill_color(*GREEN_SOFT)
        pdf.set_draw_color(*BORDER)
        pdf.set_text_color(*INK)
        pdf.set_font("DejaVu", style="B", size=8)
        if document.document_type == "INW":
            pdf.cell(90, 10, f"Wartość stanu faktycznego: {money(total_value)}", border=1, fill=True, align="C")
            pdf.cell(90, 10, f"Wartość różnicy: {signed_money(difference_value)}", border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
        elif any(item.total_value is not None for item in document.items):
            pdf.cell(0, 10, f"Łączna wartość: {money(total_value)}", border=1, fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    def _draw_signature(self, pdf: WarehouseDocumentPdf, document: WarehouseDocument) -> None:
        if pdf.get_y() > 232:
            pdf.add_page()

        pdf.set_y(-48)
        pdf.set_x(118)
        pdf.set_font("DejaVu", style="B", size=7)
        pdf.set_text_color(*MUTED)
        pdf.cell(70, 5, "WYSTAWIŁ:", new_x="LEFT", new_y="NEXT")
        pdf.set_x(118)
        pdf.set_font("DejaVu", size=9)
        pdf.set_text_color(*INK)
        pdf.cell(70, 7, issued_by_name(document), align="C", new_x="LEFT", new_y="NEXT")
        pdf.set_x(118)
        pdf.set_draw_color(*INK)
        pdf.line(118, pdf.get_y() + 1, 188, pdf.get_y() + 1)
        pdf.ln(2)
        pdf.set_x(118)
        pdf.set_font("DejaVu", size=6.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(70, 4, "podpis osoby wystawiającej", align="C")


def document_type_label(document_type: str) -> str:
    return {
        "PZ": "Przyjęcie zewnętrzne (PZ)",
        "MM": "Przesunięcie międzymagazynowe (MM)",
        "RW": "Rozchód wewnętrzny (RW)",
        "INW": "Arkusz inwentaryzacyjny (INW)",
        "AUTO_RW": "Automatyczny rozchód składników",
    }.get(document_type, document_type)


def warehouse_name(warehouse: object | None) -> str:
    return str(getattr(warehouse, "name", "—")) if warehouse is not None else "—"


def issued_by_name(document: WarehouseDocument) -> str:
    user = document.issued_by_user
    if user is None:
        return "System"
    return f"{user.first_name} {user.last_name}"


def document_item_values(index: int, item: WarehouseDocumentItem) -> list[str]:
    return [
        str(index),
        item.ingredient.name,
        quantity(item.quantity),
        item.unit,
        money(item.unit_price) if item.unit_price is not None else "—",
        money(item.total_value) if item.total_value is not None else "—",
    ]


def inventory_item_values(index: int, item: WarehouseDocumentItem) -> list[str]:
    return [
        str(index),
        item.ingredient.name,
        item.unit,
        quantity(item.book_quantity),
        quantity(item.actual_quantity),
        signed_quantity(item.difference_quantity),
        money(item.unit_price),
        signed_money(item.difference_value),
    ]


def quantity(value: Decimal | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def signed_quantity(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.3f}" if value != 0 else "0.000"


def money(value: Decimal | None) -> str:
    return "—" if value is None else f"{value:.2f} zł"


def signed_money(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.2f} zł" if value != 0 else "0.00 zł"


warehouse_document_pdf_service = WarehouseDocumentPdfService()
