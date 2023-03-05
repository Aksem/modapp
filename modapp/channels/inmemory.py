from typing import Optional, Dict, Any

from modapp.base_converter import BaseConverter
from modapp.client import BaseChannel
from modapp.models import BaseModel
from modapp.transports.inmemory import InMemoryTransport


class InMemoryChannel(BaseChannel):
    def __init__(self, converter: BaseConverter, transport: InMemoryTransport) -> None:
        super().__init__(converter)
        self.transport = transport

    async def send_unary_unary(
        self, route_path: str, request_data: BaseModel, meta: Optional[Dict[str, Any]] = None
    ) -> BaseModel:
        raw_data = self.converter.model_to_raw(request_data)
        return await self.transport.handle_request(route_path, raw_data)

    async def send_unary_stream(self):
        raise NotImplementedError()

    async def send_stream_unary(self):
        raise NotImplementedError()

    async def send_stream_stream(self):
        raise NotImplementedError()
