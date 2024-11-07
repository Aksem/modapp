import asyncio
import json
from typing import Any, Type, TypeVar

import aiohttp
from loguru import logger
from typing_extensions import override

from modapp.base_converter import BaseConverter
from modapp.base_model import BaseModel
from modapp.client import BaseChannel, Stream

T = TypeVar("T", bound=BaseModel)
StreamClosedMessage = object()


class AioHttpChannel(BaseChannel):
    """
    NOTE: aiohttp conflicts with web_socketify, requests cannot be sent in web_socketify transport
    """

    def __init__(self, converter: BaseConverter, server_address: str) -> None:
        super().__init__(converter)
        self.server_address = server_address
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ws_connection_id: str | None = None
        self._msg_queue_by_stream_id: dict[str, asyncio.Queue] = {}
        self._ws_message_processing_task: asyncio.Task | None = None

    @override
    async def send_unary_unary(
        self,
        route_path: str,
        request: BaseModel,
        reply_cls: Type[T],
        meta: dict[str, Any] | None = None,
        timeout: float | None = 5,
    ) -> T:
        raw_data = self.converter.model_to_raw(request)

        async with aiohttp.ClientSession() as session:
            # TODO: check route path
            async with session.post(
                self.server_address + route_path.replace(".", "/").lower(),
                data=raw_data,
                timeout=aiohttp.ClientTimeout(total=timeout),
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
        request: BaseModel,
        reply_cls: Type[T],
        meta: dict[str, Any] | None = None,
    ) -> Stream[T]:
        if self._ws is None:
            await self._connect_to_ws()
            assert self._ws is not None
        assert self._ws_connection_id is not None

        # Send HTTP request to start stream
        raw_data = self.converter.model_to_raw(request)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.server_address + route_path.replace(".", "/").lower(),
                data=raw_data,
                timeout=aiohttp.ClientTimeout(),
                headers={"Connection-Id": self._ws_connection_id},
            ) as response:
                stream_id = response.headers.get("Stream-Id")

        if stream_id is None:
            raise Exception()  # TODO

        stream_queue = asyncio.Queue()
        self._msg_queue_by_stream_id[stream_id] = stream_queue
        
        async def generator():
            while True:
                raw_message = await stream_queue.get()
                if raw_message == StreamClosedMessage:
                    del self._msg_queue_by_stream_id[stream_id]
                    break
                message = self.converter.raw_to_model(raw_message, reply_cls)
                yield message
        
        async def on_end():
            assert self._ws is not None
            await self._ws.send_str(json.dumps({ 'streamId': stream_id, 'end': True }))
            del self._msg_queue_by_stream_id[stream_id]
            if len(self._msg_queue_by_stream_id) == 0:
                await self._close_ws()

        return Stream(generator(), on_end=on_end)

    @override
    async def send_stream_unary(self) -> None:
        raise NotImplementedError()

    @override
    async def send_stream_stream(self) -> None:
        raise NotImplementedError()

    @override
    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._close_ws(exc_type, exc, tb)

    async def _connect_to_ws(self):
        if self._session is not None and self._ws is not None:
            logger.debug("Already connected to websocket")
            return

        # TODO: handle timeout
        self._session = await aiohttp.ClientSession().__aenter__()
        self._ws = await self._session.ws_connect(
            f"{self.server_address}/ws"
        ).__aenter__()

        # TODO: catch timeout
        first_message = await asyncio.wait_for(anext(self._ws), timeout=10)
        if first_message.type == aiohttp.WSMsgType.ERROR:
            # error happened, raise exception
            raise Exception()  # TODO
        elif first_message.type == aiohttp.WSMsgType.TEXT:
            first_message_json = json.loads(first_message.data)
            try:
                # TODO: validate type
                self._ws_connection_id = first_message_json["connectionId"]
            except KeyError:
                raise Exception()  # TODO
        else:
            raise Exception()  # TODO

        self._ws_message_processing_task = asyncio.create_task(
            self.process_ws_messages()
        )

    async def _close_ws(self, exc_type = None, exc = None, tb = None):
        if self._session is not None:
            await self._session.__aexit__(exc_type, exc, tb)
            self._session = None
        if self._ws is not None:
            await self._ws.__aexit__(exc_type, exc, tb)
            self._ws = None

    async def process_ws_messages(self):
        assert self._ws is not None
        async for msg in self._ws:
            msg_json = json.loads(msg.data)
            try:
                stream_id = msg_json["streamId"]
            except KeyError:
                logger.error("No streamId in ws message, skip it")
                continue

            try:
                stream_queue = self._msg_queue_by_stream_id[stream_id]
            except KeyError:
                logger.error(f"No queue found for streamId {stream_id}, skip it")
                continue

            try:
                stream_msg = msg_json["message"]
            except KeyError:
                stream_end_msg = msg_json.get("end", None)
                if stream_end_msg is not None:
                    if stream_end_msg is True:
                        await stream_queue.put(StreamClosedMessage)
                    else:
                        logger.error(
                            f"Field 'end' has unsupported value '{stream_end_msg}', only 'true' is supported"
                        )
                    continue
                else:
                    logger.error(
                        "Neither 'message' field nor 'end' field in ws message, skip it"
                    )
                    continue

            if msg.type == aiohttp.WSMsgType.TEXT:
                await stream_queue.put(stream_msg)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                await stream_queue.put(StreamClosedMessage)
                break
