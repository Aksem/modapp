import sys
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, Optional, Type, TypeVar

if sys.version_info >= (3, 11, 0):
    from typing import Self
else:
    from typing_extensions import Self

from modapp.base_converter import BaseConverter
from modapp.models import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseChannel(ABC):
    def __init__(self, converter: BaseConverter) -> None:
        self.converter = converter

    def __aenter__(self) -> Self:
        return self

    @abstractmethod
    def __aexit__(self) -> None:
        pass

    @abstractmethod
    async def send_unary_unary(
        self,
        route_path: str,
        request: BaseModel,
        reply_cls: Type[T],
        meta: Optional[Dict[str, Any]] = None,
    ) -> T:
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
    async def send_stream_unary(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def send_stream_stream(self) -> None:
        raise NotImplementedError()


class Client:
    def __init__(self, channel: BaseChannel) -> None:
        self.channel = channel


__all__ = ["Client", "BaseChannel"]
