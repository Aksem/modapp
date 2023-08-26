from random import seed
from typing import AsyncIterator, Dict, Union

import socketio  # type: ignore
from aiohttp import web
from loguru import logger
from typing_extensions import NotRequired, override

from modapp.base_converter import BaseConverter
from modapp.base_transport import BaseTransport, BaseTransportConfig
from modapp.errors import InvalidArgumentError, NotFoundError, ServerError
from modapp.routing import Cardinality, RoutesDict

seed(1)


class SocketioTransportConfig(BaseTransportConfig):
    address: NotRequired[str]
    port: NotRequired[int]


DEFAULT_CONFIG: SocketioTransportConfig = {"address": "127.0.0.1", "port": 9091}


class SocketioTransport(BaseTransport):
    CONFIG_KEY = "socketio"

    def __init__(
        self, config: SocketioTransportConfig, converter: BaseConverter | None = None
    ) -> None:
        super().__init__(config, converter)
        self.runner: web.AppRunner | None = None

    @override
    async def start(self, routes: RoutesDict) -> None:
        sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")
        app = web.Application()
        sio.attach(app)

        @sio.event  # type: ignore
        async def connect(sid: int, environ, auth) -> None:
            logger.info("connected: " + str(sid))

        @sio.event  # type: ignore
        def disconnect(sid: int) -> None:
            logger.info("disconnected: " + str(sid))

        @sio.event  # type: ignore
        async def grpc_request_v2(
            sid, method_name: str, meta: Dict[str, Union[str, int, bool]], data: bytes
        ):
            logger.trace(f"request_v2 {method_name} {str(meta)}")

            try:
                route = routes[method_name]
            except KeyError:
                logger.error(f"Endpoint '{method_name}' not found")
                error = NotFoundError(f"Endpoint '{method_name}' not found")
                return (self.converter.error_to_raw(error), None)

            # TODO: get and validate meta data

            try:
                reply = await self.got_request(route, data, meta)
            except (
                NotFoundError,
                InvalidArgumentError,
                ServerError,
            ) as error:  # TODO: base error?
                return (self.converter.error_to_raw(error), None)

            if (
                route.proto_cardinality == Cardinality.UNARY_UNARY
                or route.proto_cardinality == Cardinality.STREAM_UNARY
            ):
                return (None, reply)
            else:
                assert isinstance(reply, AsyncIterator)
                async for reply_item in reply:
                    await sio.emit(
                        f"{method_name}_{meta['request_id']}_reply", reply_item
                    )

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        address = self.config.get("address", DEFAULT_CONFIG.get("address"))
        assert isinstance(address, str), "Address expected to be a string"
        port = self.config.get("port", DEFAULT_CONFIG.get("port"))
        assert isinstance(port, int), "Port expected to be an int"
        site = web.TCPSite(self.runner, address, port)
        await site.start()
        logger.info(f"Start socketio server: {address}:{port}")

    @override
    async def stop(self) -> None:
        if self.runner is not None:
            await self.runner.cleanup()
            self.runner = None
        else:
            logger.warning("Cannot stop not started server")


__all__ = ["SocketioTransport", "SocketioTransportConfig"]
