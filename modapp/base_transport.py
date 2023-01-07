from __future__ import annotations
from abc import ABC
from typing import TYPE_CHECKING, Optional, TypedDict

from modapp.base_converter import BaseConverter
from modapp.converter_utils import get_default_converter

if TYPE_CHECKING:
    from .routing import RoutesDict


class BaseTransportConfig(TypedDict):
    ...


class BaseTransport(ABC):
    # REQUIRED
    # TODO: Check automatically whether it is set
    CONFIG_KEY: str

    def __init__(self, config: BaseTransportConfig, converter: Optional[BaseConverter] = None):
        self.config = config
        self.converter = converter if converter is not None else get_default_converter()

    async def start(self, routes: RoutesDict) -> None:
        ...

    async def stop(self) -> None:
        ...


__all__ = ["BaseTransportConfig", "BaseTransport"]
