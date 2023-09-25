from typing import Any, AsyncIterator, Dict, Optional, Type, TypeVar

from typing_extensions import override

from modapp.base_converter import BaseConverter
from modapp.client import BaseChannel
from modapp.models import BaseModel
from modapp.transports.inmemory import InMemoryTransport

T = TypeVar("T", bound=BaseModel)


class InMemoryChannel(BaseChannel):
    def __init__(self, converter: BaseConverter, transport: InMemoryTransport) -> None:
        super().__init__(converter)
        self.transport = transport

    @override
    async def send_unary_unary(
        self,
        route_path: str,
        request_data: BaseModel,
        reply_cls: Type[BaseModel],
        meta: Optional[Dict[str, Any]] = None,
    ) -> BaseModel:
        raw_data = self.converter.model_to_raw(request_data)
        raw_reply = await self.transport.handle_request(route_path, raw_data)
        assert isinstance(
            raw_reply, bytes
        ), "Reply on unary-unary request should be bytes"
        return self.converter.raw_to_model(raw_reply, reply_cls)

    @override
    async def send_unary_stream(
        self,
        route_path: str,
        request_data: BaseModel,
        reply_cls: Type[T],
        meta: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[T]:
        raw_data = self.converter.model_to_raw(request_data)
        reply_iterator = await self.transport.handle_request(route_path, raw_data)
        assert isinstance(
            reply_iterator, AsyncIterator
        ), "Reply on unary-stream request should be async iterator of bytes"
        async for raw_message in reply_iterator:
            yield self.converter.raw_to_model(raw_message, reply_cls)

    @override
    async def send_stream_unary(self) -> None:
        raise NotImplementedError()

    @override
    async def send_stream_stream(self) -> None:
        raise NotImplementedError()

    @override
    def __aexit__(self) -> None:
        pass
