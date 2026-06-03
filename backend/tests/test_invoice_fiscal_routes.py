from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.crud import invoice as crud_invoice
from app.crud import order as crud_order
from app.main import app
from app.models.invoice import Invoice
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User
from app.services import fiscal_service, invoice_service, mock_printer_service


client = TestClient(app)


def make_user(role: str) -> User:
    return User(
        id=1,
        first_name="Test",
        last_name="User",
        email="test@example.com",
        password_hash="hash",
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def override_current_user(role: str) -> None:
    async def _get_current_user_override():
        return make_user(role)

    app.dependency_overrides[get_current_user] = _get_current_user_override


def make_order() -> Order:
    return Order(
        id=1,
        table_id=1,
        waiter_id=1,
        discount_id=None,
        shift_id=None,
        source="WAITER",
        status="OPEN",
        created_at=datetime.now(timezone.utc),
        closed_at=None,
        total_amount=Decimal("25.00"),
        subtotal_amount=Decimal("25.00"),
        discount_amount=Decimal("0.00"),
        tip_amount=Decimal("0.00"),
    )


def make_invoice() -> Invoice:
    return Invoice(
        id=1,
        order_id=1,
        nip="1234567890",
        company_name="Test Company",
        invoice_number="FV/TEST/1",
        status="CREATED",
        created_at=datetime.now(timezone.utc),
    )


def test_invoice_route_forbidden_for_kitchen_role():
    override_current_user("KITCHEN")

    try:
        response = client.post(
            "/api/v1/orders/1/invoice",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "nip": "1234567890",
                "company_name": "Test Company",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_create_invoice_reaches_service(monkeypatch):
    async def get_order(_db, id: int):
        assert id == 1
        return make_order()

    async def create_invoice(_db, *, order, nip: str, company_name: str):
        assert order.id == 1
        assert nip == "1234567890"
        assert company_name == "Test Company"
        return make_invoice()

    monkeypatch.setattr(crud_order, "get", get_order)
    monkeypatch.setattr(invoice_service, "create_invoice", create_invoice)
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/orders/1/invoice",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "nip": "1234567890",
                "company_name": "Test Company",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["invoice_number"] == "FV/TEST/1"


def test_get_invoice_for_order_reaches_service(monkeypatch):
    async def get_by_order(_db, *, order_id: int):
        assert order_id == 1
        return make_invoice()

    monkeypatch.setattr(invoice_service, "get_by_order", get_by_order)
    override_current_user("MANAGER")

    try:
        response = client.get(
            "/api/v1/orders/1/invoice",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["company_name"] == "Test Company"


def test_generate_invoice_pdf_returns_file(monkeypatch, tmp_path):
    pdf_path = tmp_path / "invoice.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 mock")

    async def get_invoice(_db, id: int):
        assert id == 1
        return make_invoice()

    async def get_order(_db, id: int):
        assert id == 1
        return make_order()

    def generate_invoice_pdf(*, invoice, order):
        assert invoice.id == 1
        assert order.id == 1
        return pdf_path

    monkeypatch.setattr(crud_invoice, "get", get_invoice)
    monkeypatch.setattr(crud_order, "get", get_order)
    monkeypatch.setattr(invoice_service, "generate_invoice_pdf", generate_invoice_pdf)
    override_current_user("MANAGER")

    try:
        response = client.post(
            "/api/v1/invoices/1/pdf",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.4 mock"


def test_send_invoice_to_ksef_mock_reaches_service(monkeypatch):
    async def get_invoice(_db, id: int):
        assert id == 1
        return make_invoice()

    async def send_to_ksef_mock(_db, *, invoice):
        assert invoice.id == 1
        invoice.status = "SENT_TO_KSEF_MOCK"
        return "KSEF-MOCK-1"

    monkeypatch.setattr(crud_invoice, "get", get_invoice)
    monkeypatch.setattr(invoice_service, "send_to_ksef_mock", send_to_ksef_mock)
    override_current_user("MANAGER")

    try:
        response = client.post(
            "/api/v1/invoices/1/send-ksef-mock",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["reference_number"] == "KSEF-MOCK-1"
    assert response.json()["invoice"]["status"] == "SENT_TO_KSEF_MOCK"


def test_mark_invoice_sent_reaches_service(monkeypatch):
    async def get_invoice(_db, id: int):
        assert id == 1
        return make_invoice()

    async def mark_sent(_db, *, invoice):
        assert invoice.id == 1
        invoice.status = "SENT"
        return invoice

    monkeypatch.setattr(crud_invoice, "get", get_invoice)
    monkeypatch.setattr(invoice_service, "mark_sent", mark_sent)
    override_current_user("MANAGER")

    try:
        response = client.post(
            "/api/v1/invoices/1/mark-sent",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "SENT"


def test_fiscal_route_forbidden_for_kitchen_role():
    override_current_user("KITCHEN")

    try:
        response = client.get(
            "/api/v1/orders/1/receipt/text",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_generate_text_receipt_reaches_service(monkeypatch):
    async def get_order(_db, id: int):
        assert id == 1
        return make_order()

    async def generate_text_receipt(_db, *, order):
        assert order.id == 1
        return "TEXT RECEIPT"

    monkeypatch.setattr(crud_order, "get", get_order)
    monkeypatch.setattr(fiscal_service, "generate_text_receipt", generate_text_receipt)
    override_current_user("WAITER")

    try:
        response = client.get(
            "/api/v1/orders/1/receipt/text",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.text == "TEXT RECEIPT"


def test_generate_html_receipt_reaches_service(monkeypatch):
    async def get_order(_db, id: int):
        assert id == 1
        return make_order()

    async def generate_html_receipt(_db, *, order):
        assert order.id == 1
        return "<html><body>RECEIPT</body></html>"

    monkeypatch.setattr(crud_order, "get", get_order)
    monkeypatch.setattr(fiscal_service, "generate_html_receipt", generate_html_receipt)
    override_current_user("WAITER")

    try:
        response = client.get(
            "/api/v1/orders/1/receipt/html",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "RECEIPT" in response.text


def test_generate_receipt_pdf_returns_file(monkeypatch, tmp_path):
    pdf_path = tmp_path / "receipt.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 receipt")

    async def get_order(_db, id: int):
        assert id == 1
        return make_order()

    async def generate_text_receipt(_db, *, order):
        assert order.id == 1
        return "TEXT RECEIPT"

    def print_receipt_to_pdf(*, order_id: int, receipt_content: str):
        assert order_id == 1
        assert receipt_content == "TEXT RECEIPT"
        return pdf_path

    monkeypatch.setattr(crud_order, "get", get_order)
    monkeypatch.setattr(fiscal_service, "generate_text_receipt", generate_text_receipt)
    monkeypatch.setattr(mock_printer_service, "print_receipt_to_pdf", print_receipt_to_pdf)
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/orders/1/receipt/pdf",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.4 receipt"


def test_generate_guest_check_text_reaches_service(monkeypatch):
    async def get_order(_db, id: int):
        assert id == 1
        return make_order()

    async def generate_guest_check_text(_db, *, order):
        assert order.id == 1
        return "GUEST CHECK"

    monkeypatch.setattr(crud_order, "get", get_order)
    monkeypatch.setattr(
        fiscal_service,
        "generate_guest_check_text",
        generate_guest_check_text,
    )
    override_current_user("WAITER")

    try:
        response = client.get(
            "/api/v1/orders/1/guest-check/text",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.text == "GUEST CHECK"


def test_generate_guest_check_pdf_returns_file(monkeypatch, tmp_path):
    pdf_path = tmp_path / "guest-check.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 guest")

    async def get_order(_db, id: int):
        assert id == 1
        return make_order()

    async def generate_guest_check_text(_db, *, order):
        assert order.id == 1
        return "GUEST CHECK"

    def print_guest_check_to_pdf(*, order_id: int, receipt_content: str):
        assert order_id == 1
        assert receipt_content == "GUEST CHECK"
        return pdf_path

    monkeypatch.setattr(crud_order, "get", get_order)
    monkeypatch.setattr(
        fiscal_service,
        "generate_guest_check_text",
        generate_guest_check_text,
    )
    monkeypatch.setattr(
        mock_printer_service,
        "print_guest_check_to_pdf",
        print_guest_check_to_pdf,
    )
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/orders/1/guest-check/pdf",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.4 guest"


def test_vat_summary_uses_gross_prices_and_allocates_discount():
    order = make_order()
    order.discount_amount = Decimal("10.00")

    food = Product(
        id=1,
        category_id=1,
        kitchen_section_id=None,
        name="Food",
        description=None,
        price=Decimal("108.00"),
        vat_rate=Decimal("8.00"),
        preparation_time=None,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    drink = Product(
        id=2,
        category_id=1,
        kitchen_section_id=None,
        name="Drink",
        description=None,
        price=Decimal("123.00"),
        vat_rate=Decimal("23.00"),
        preparation_time=None,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    food_item = OrderItem(
        id=1,
        order_id=1,
        product_id=1,
        quantity=1,
        position=0,
        course_number=1,
        unit_price=Decimal("108.00"),
        total_price=Decimal("108.00"),
        status="NEW",
        notes=None,
    )
    drink_item = OrderItem(
        id=2,
        order_id=1,
        product_id=2,
        quantity=1,
        position=1,
        course_number=1,
        unit_price=Decimal("123.00"),
        total_price=Decimal("123.00"),
        status="NEW",
        notes=None,
    )

    summary = fiscal_service.calculate_vat_summary(
        rows=[(food_item, food), (drink_item, drink)],
        order=order,
    )

    assert summary[Decimal("8.00")]["gross"] == Decimal("103.32")
    assert summary[Decimal("8.00")]["tax"] == Decimal("7.65")
    assert summary[Decimal("23.00")]["gross"] == Decimal("117.68")
    assert summary[Decimal("23.00")]["tax"] == Decimal("22.01")
