from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type, AsyncIterator, TypeVar

from modapp.models import BaseModel
from modapp.base_converter import BaseConverter


T = TypeVar("T", bound=BaseModel)


class BaseChannel(ABC):
    def __init__(self, converter: BaseConverter) -> None:
        self.converter = converter

    def __aenter__(self):
        return self

    def __aexit__(self):
        ...

    @abstractmethod
    async def send_unary_unary(
        self,
        route_path: str,
        request: BaseModel,
        reply_cls: Type[BaseModel],
        meta: Optional[Dict[str, Any]] = None,
    ) -> BaseModel:
        raise NotImplementedError()

    @abstractmethod
    async def send_unary_stream(
        self,
        route_path: str,
        request: BaseModel,
        reply_cls: Type[T],
        meta: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[T]:
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
