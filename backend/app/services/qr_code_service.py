from functools import lru_cache
from importlib import import_module
from io import BytesIO
import re
from secrets import token_urlsafe

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

    @lru_cache(maxsize=512)
    def generate_png(self, *, url: str, size: int = 420) -> bytes:
        qrcode = import_module("qrcode")
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        qr.box_size = max(1, size // (qr.modules_count + (qr.border * 2)))
        image = qr.make_image(fill_color="#132f53", back_color="white")
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()


qr_code_service = QRCodeService()
