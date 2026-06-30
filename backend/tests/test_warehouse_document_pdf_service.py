from datetime import date, datetime, timezone
from decimal import Decimal

from app.models.ingredient import Ingredient
from app.models.user import User
from app.models.warehouse import Warehouse
from app.models.warehouse_document import WarehouseDocument
from app.models.warehouse_document_item import WarehouseDocumentItem
from app.services.warehouse_document_pdf_service import WarehouseDocumentPdfService


def test_inventory_pdf_is_generated_with_unicode_content() -> None:
    document = inventory_document()

    content = WarehouseDocumentPdfService().generate(document)

    assert content.startswith(b"%PDF")
    assert len(content) > 20_000


def inventory_document() -> WarehouseDocument:
    warehouse = Warehouse(
        id=1,
        name="Magazyn główny",
        type="GENERAL",
        is_active=True,
        is_default=True,
    )
    issuer = User(
        id=1,
        first_name="Aleksander",
        last_name="Żółć",
        email="admin@example.com",
        password_hash="hash",
        role="ADMIN",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    ingredient = Ingredient(id=1, name="Mąka pszenna", unit="kg", is_active=True)
    item = WarehouseDocumentItem(
        id=1,
        warehouse_document_id=1,
        ingredient_id=ingredient.id,
        quantity=Decimal("9.500"),
        unit="kg",
        unit_price=Decimal("12.50"),
        total_value=Decimal("118.75"),
        book_quantity=Decimal("10.000"),
        actual_quantity=Decimal("9.500"),
        difference_quantity=Decimal("-0.500"),
        difference_value=Decimal("-6.25"),
    )
    item.ingredient = ingredient
    document = WarehouseDocument(
        id=1,
        document_number="INW/2026/000001",
        document_type="INW",
        status="COMPLETED",
        source_warehouse_id=warehouse.id,
        issued_by_user_id=issuer.id,
        operation_date=date(2026, 6, 30),
        issued_at=datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc),
        reason="Inwentaryzacja okresowa",
        description="Spis z natury.",
    )
    document.source_warehouse = warehouse
    document.issued_by_user = issuer
    document.items = [item]
    return document
