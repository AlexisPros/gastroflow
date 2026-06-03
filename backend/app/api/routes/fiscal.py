from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

from app.api.deps import DbSession, RequireFiscalRole, get_or_404
from app.crud import order as crud_order
from app.services import fiscal_service, mock_printer_service

router = APIRouter(
    tags=["Fiscal mock"],
    dependencies=[RequireFiscalRole],
)


@router.get(
    "/orders/{order_id}/receipt/text",
    response_class=PlainTextResponse,
)
async def generate_text_receipt(order_id: int, db: DbSession):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    return await fiscal_service.generate_text_receipt(db, order=order)


@router.get(
    "/orders/{order_id}/receipt/html",
    response_class=HTMLResponse,
)
async def generate_html_receipt(order_id: int, db: DbSession):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    return await fiscal_service.generate_html_receipt(db, order=order)


@router.post("/orders/{order_id}/receipt/pdf")
async def generate_receipt_pdf(order_id: int, db: DbSession):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    receipt_content = await fiscal_service.generate_text_receipt(db, order=order)
    pdf_path = mock_printer_service.print_receipt_to_pdf(
        order_id=order.id,
        receipt_content=receipt_content,
    )
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
    )


@router.get(
    "/orders/{order_id}/guest-check/text",
    response_class=PlainTextResponse,
)
async def generate_guest_check_text(order_id: int, db: DbSession):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    return await fiscal_service.generate_guest_check_text(db, order=order)


@router.post("/orders/{order_id}/guest-check/pdf")
async def generate_guest_check_pdf(order_id: int, db: DbSession):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    receipt_content = await fiscal_service.generate_guest_check_text(db, order=order)
    pdf_path = mock_printer_service.print_guest_check_to_pdf(
        order_id=order.id,
        receipt_content=receipt_content,
    )
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
    )
