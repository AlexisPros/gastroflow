from app.crud.base import CRUDBase
from app.models.invoice import Invoice
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate


invoice = CRUDBase[Invoice, InvoiceCreate, InvoiceUpdate](Invoice)
