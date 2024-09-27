from typing import Any, AsyncIterator, Dict, Optional, Type, TypeVar

import aiohttp
from typing_extensions import override

from modapp.base_converter import BaseConverter
from modapp.base_model import BaseModel
from modapp.client import BaseChannel

T = TypeVar("T", bound=BaseModel)


class AioHttpChannel(BaseChannel):
    """
    NOTE: aiohttp conflicts with web_socketify, requests cannot be sent in web_socketify transport
    """
    def __init__(self, converter: BaseConverter, server_address: str) -> None:
        super().__init__(converter)
        self.server_address = server_address

    @override
    async def send_unary_unary(
        self,
        route_path: str,
        request_data: BaseModel,
        reply_cls: Type[T],
        meta: Optional[Dict[str, Any]] = None,
        timeout: float | None = 5,
    ) -> T:
        raw_data = self.converter.model_to_raw(request_data)

        # TODO: save client session
        async with aiohttp.ClientSession() as session:
            # TODO: check route path
            async with session.post(
                self.server_address + route_path.replace(".", "/").lower(),
                data=raw_data,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                raw_reply = await response.read()

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
        raise NotImplementedError()
        # raw_data = self.converter.model_to_raw(request_data)

        # TODO

        # assert isinstance(
        #     reply_iterator, AsyncIterator
        # ), "Reply on unary-stream request should be async iterator of bytes"
        # async for raw_message in reply_iterator:
        #     yield self.converter.raw_to_model(raw_message, reply_cls)

    @override
    async def send_stream_unary(self) -> None:
        raise NotImplementedError()

    @override
    async def send_stream_stream(self) -> None:
        raise NotImplementedError()

    @override
    def __aexit__(self) -> None:
        pass
