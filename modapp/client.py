from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Generic, Optional, Type, TypeVar

if sys.version_info >= (3, 11, 0):
    from typing import Self
else:
    from typing_extensions import Self

from modapp.base_converter import BaseConverter
from modapp.base_model import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseChannel(ABC):
    def __init__(self, converter: BaseConverter) -> None:
        self.converter = converter

    async def __aenter__(self) -> Self:
        return self

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb) -> None:
        pass

    @abstractmethod
    async def send_unary_unary(
        self,
        route_path: str,
        request: BaseModel,
        reply_cls: Type[T],
        meta: Optional[Dict[str, Any]] = None,
        timeout: float | None = 5.0,
    ) -> T:
        raise NotImplementedError()

    @abstractmethod
    async def send_unary_stream(
        self,
        route_path: str,
        request: BaseModel,
        reply_cls: Type[T],
        meta: Optional[Dict[str, Any]] = None,
    ) -> Stream[T]:
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


ReceiveType = TypeVar("ReceiveType", bound=BaseModel)

class Stream(AsyncIterator[ReceiveType]):
    def __init__(self, result_iterator: AsyncIterator[ReceiveType], on_end: Callable[[], Awaitable]) -> None:
        super().__init__()
        self.result_iterator = result_iterator
        self.on_end = on_end

    async def end(self) -> None:
        await self.on_end()

    def __aiter__(self) -> AsyncIterator[ReceiveType]:
        return self

    async def __anext__(self) -> ReceiveType:
        return await anext(self.result_iterator)


SendType = TypeVar('SendType', bound=BaseModel)


class BiStream(AsyncIterator[T], Generic[T, SendType]):
    def __init__(self, result_iterator: AsyncIterator[T], on_end: Callable[[], Awaitable]) -> None:
        super().__init__()
        self.result_iterator = result_iterator
        self.on_end = on_end

    async def end(self) -> None:
        await self.on_end()

    async def send_message(self, message: SendType) -> None:
        ...

    def __aiter__(self) -> AsyncIterator[T]:
        return self

    async def __anext__(self) -> T:
        return await anext(self.result_iterator)


__all__ = ["Client", "BaseChannel"]
