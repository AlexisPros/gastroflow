from app.crud.base import CRUDBase
from app.models.payment import Payment
from app.schemas.payment import PaymentCreate, PaymentUpdate


payment = CRUDBase[Payment, PaymentCreate, PaymentUpdate](Payment)
