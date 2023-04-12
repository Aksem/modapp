from typing import AsyncIterator, Optional, Dict, Any, Type, TypeVar

from modapp.base_converter import BaseConverter
from modapp.client import BaseChannel
from modapp.models import BaseModel
from modapp.transports.inmemory import InMemoryTransport


T = TypeVar('T', bound=BaseModel)

class InMemoryChannel(BaseChannel):
    def __init__(self, converter: BaseConverter, transport: InMemoryTransport) -> None:
        super().__init__(converter)
        self.transport = transport

    async def send_unary_unary(
        self,
        route_path: str,
        request_data: BaseModel,
        reply_cls: Type[BaseModel],
        meta: Optional[Dict[str, Any]] = None,
    ) -> BaseModel:
        raw_data = self.converter.model_to_raw(request_data)
        raw_reply = await self.transport.handle_request(route_path, raw_data)
        return self.converter.raw_to_model(raw_reply, reply_cls)

    async def send_unary_stream(
        self,
        route_path: str,
        request_data: BaseModel,
        reply_cls: Type[T],
        meta: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[T]:
        raw_data = self.converter.model_to_raw(request_data)
        async for raw_message in await self.transport.handle_request(route_path, raw_data):
            yield self.converter.raw_to_model(raw_message, reply_cls)

    async def send_stream_unary(self):
        raise NotImplementedError()

    async def send_stream_stream(self):
        raise NotImplementedError()
