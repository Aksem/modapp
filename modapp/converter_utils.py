from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base_converter import BaseConverter


def get_default_converter() -> BaseConverter:
    ...
