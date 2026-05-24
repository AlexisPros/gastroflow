from app.crud.base import CRUDBase
from app.models.reservation import Reservation
from app.schemas.reservation import ReservationCreate, ReservationUpdate


reservation = CRUDBase[Reservation, ReservationCreate, ReservationUpdate](Reservation)
