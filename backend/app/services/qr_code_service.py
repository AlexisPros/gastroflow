from secrets import token_urlsafe
import re

from app.core.config import settings


class QRCodeService:
    def generate_table_token(self, *, table_number: str) -> str:
        normalized_table_number = re.sub(
            r"[^a-z0-9]+",
            "-",
            table_number.lower(),
        ).strip("-")
        suffix = token_urlsafe(6)

        if not normalized_table_number:
            return suffix

        return f"{normalized_table_number}-{suffix}"

    def build_table_url(self, *, qr_token: str) -> str:
        return f"{settings.PUBLIC_MENU_BASE_URL.rstrip('/')}/{qr_token}"


qr_code_service = QRCodeService()
