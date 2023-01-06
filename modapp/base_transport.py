from __future__ import annotations
from abc import ABC
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from .routing import RoutesDict


class BaseTransportConfig(TypedDict):
    ...


class BaseTransport(ABC):
    # REQUIRED
    # TODO: Check automatically whether it is set
    CONFIG_KEY: str

    def __init__(self, config: BaseTransportConfig):
        self.config = config

    async def start(self, routes: RoutesDict) -> None:
        ...

    async def stop(self) -> None:
        ...


__all__ = ["BaseTransportConfig", "BaseTransport"]
