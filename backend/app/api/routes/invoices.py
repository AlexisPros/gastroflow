from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import DbSession, get_or_404, raise_bad_request
from app.crud import invoice as crud_invoice
from app.crud import order as crud_order
from app.schemas import InvoiceRead
from app.services import invoice_service

router = APIRouter(tags=["Invoices"])


class CreateInvoiceRequest(BaseModel):
    nip: str
    company_name: str


class KsefMockResponse(BaseModel):
    reference_number: str
    invoice: InvoiceRead


@router.post("/orders/{order_id}/invoice", response_model=InvoiceRead)
async def create_invoice_for_order(
    order_id: int,
    body: CreateInvoiceRequest,
    db: DbSession,
):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    try:
        return await invoice_service.create_invoice(
            db,
            order=order,
            nip=body.nip,
            company_name=body.company_name,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.get("/orders/{order_id}/invoice", response_model=InvoiceRead)
async def get_invoice_for_order(order_id: int, db: DbSession):
    invoice = await invoice_service.get_by_order(db, order_id=order_id)
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="invoice not found.",
        )

    return invoice


@router.post("/invoices/{invoice_id}/pdf")
async def generate_invoice_pdf(invoice_id: int, db: DbSession):
    invoice = await get_or_404(
        crud_obj=crud_invoice,
        db=db,
        id=invoice_id,
        entity_name="invoice",
    )
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=invoice.order_id,
        entity_name="order",
    )
    pdf_path = invoice_service.generate_invoice_pdf(invoice=invoice, order=order)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
    )


@router.post("/invoices/{invoice_id}/send-ksef-mock", response_model=KsefMockResponse)
async def send_invoice_to_ksef_mock(invoice_id: int, db: DbSession):
    invoice = await get_or_404(
        crud_obj=crud_invoice,
        db=db,
        id=invoice_id,
        entity_name="invoice",
    )
    reference_number = await invoice_service.send_to_ksef_mock(
        db,
        invoice=invoice,
    )
    return KsefMockResponse(
        reference_number=reference_number,
        invoice=invoice,
    )


@router.post("/invoices/{invoice_id}/mark-sent", response_model=InvoiceRead)
async def mark_invoice_sent(invoice_id: int, db: DbSession):
    invoice = await get_or_404(
        crud_obj=crud_invoice,
        db=db,
        id=invoice_id,
        entity_name="invoice",
    )
    return await invoice_service.mark_sent(db, invoice=invoice)
