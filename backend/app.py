"""Compatibility entry point.

Prefer running ``uvicorn backend.main:app``. This module is kept so older
commands using ``backend.app:app`` still work.
"""

from backend.services.translation_api_service import app
