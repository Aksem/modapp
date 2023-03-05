from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from modapp.models import BaseModel
from modapp.base_converter import BaseConverter


class BaseChannel(ABC):
    def __init__(self, converter: BaseConverter) -> None:
        self.converter = converter

    @abstractmethod
    async def send_unary_unary(
        self, route_path: str, request: BaseModel, meta: Optional[Dict[str, Any]] = None
    ):
        raise NotImplementedError()

    @abstractmethod
    async def send_unary_stream(self):
        raise NotImplementedError()

    @abstractmethod
    async def send_stream_unary(self):
        raise NotImplementedError()

    @abstractmethod
    async def send_stream_stream(self):
        raise NotImplementedError()


class Client:
    def __init__(self, channel: BaseChannel) -> None:
        self.channel = channel


__all__ = ["Client", "BaseChannel"]
