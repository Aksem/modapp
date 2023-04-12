from random import seed
from typing import Dict, Optional, Union, AsyncIterator


import socketio
from aiohttp import web
from loguru import logger
from typing_extensions import NotRequired

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
        self, config: SocketioTransportConfig, converter: Optional[BaseConverter] = None
    ) -> None:
        super().__init__(config, converter)
        self.runner: Optional[web.AppRunner] = None

    async def start(self, routes: RoutesDict) -> None:
        sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")
        app = web.Application()
        sio.attach(app)

        @sio.event
        async def connect(sid, environ, auth):
            logger.info("connected: " + str(sid))

        @sio.event
        def disconnect(sid):
            logger.info("disconnected: " + str(sid))

        @sio.event
        async def grpc_request_v2(
            sid, method_name: str, meta: Dict[str, Union[str, int, bool]], data: bytes
        ):
            logger.trace("request_v2 " + str(meta))

            try:
                route = routes[method_name]
            except KeyError:
                logger.error(f"Endpoint '{method_name}' not found")
                error = NotFoundError(f"Endpoint '{method_name}' not found")
                return (self.converter.error_to_raw(error, None), None)

            # TODO: get and validate meta data

            try:
                reply = self.got_request(route, data, meta)
            except (
                NotFoundError,
                InvalidArgumentError,
                ServerError,
            ) as error:  # TODO: base error?
                return (self.converter.error_to_raw(error, route), None)

            if (
                route.proto_cardinality == Cardinality.UNARY_UNARY
                or route.proto_cardinality == Cardinality.STREAM_UNARY
            ):
                print(reply)
                return (None, reply)
            else:
                assert isinstance(reply, AsyncIterator)
                async for reply_item in reply:
                    await sio.emit(f"{method_name}_{request_id}_reply", reply_item)

        runner = web.AppRunner(app)
        await runner.setup()
        address: str = self.config.get("address", DEFAULT_CONFIG.get("address"))
        port: int = self.config.get("port", DEFAULT_CONFIG.get("port"))
        site = web.TCPSite(runner, address, port)
        await site.start()
        logger.info(f"Start socketio server: {address}:{port}")

    async def stop(self) -> None:
        if self.runner is not None:
            await self.runner.cleanup()
            self.runner = None
        else:
            logger.warning("Cannot stop not started server")


__all__ = ["SocketioTransport", "SocketioTransportConfig"]
