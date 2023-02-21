from __future__ import annotations
from functools import partial
from typing import TYPE_CHECKING, Dict, Optional

from grpclib.const import Handler
from grpclib.encoding.base import CodecBase
from grpclib.events import RecvRequest, listen
from grpclib.server import Server, Stream
from loguru import logger
from typing_extensions import NotRequired

from ..base_converter import BaseConverter
from ..base_transport import BaseTransport, BaseTransportConfig
from ..routing import Cardinality

if TYPE_CHECKING:
    from ..routing import RoutesDict, Route


class GrpcTransportConfig(BaseTransportConfig):
    address: NotRequired[str]
    port: NotRequired[int]


DEFAULT_CONFIG: GrpcTransportConfig = {"address": "127.0.0.1", "port": 50051}


async def recv_request(event: RecvRequest):
    logger.trace(f"Income request: {event.method_name}")


class RawCodec(CodecBase):
    __content_subtype__ = 'proto'

    def encode(self, message, message_type):
        return message

    def decode(self, data: bytes, message_type):
        return data


class HandlerStorage:
    def __init__(self, routes: RoutesDict, converter: BaseConverter, request_callback) -> None:
        self.routes = routes
        self.converter = converter
        self.request_callback = request_callback

    def __mapping__(self):
        result: Dict[str, Handler] = {}
        for route_path, route in self.routes.items():

            async def handle(stream: Stream, route: Route):
                # TODO: avoid large try/except
                try:
                    request = await stream.recv_message()
                    assert request is not None

                    # request_model = self.converter.raw_to_model(request, route)
                    # TODO: pass meta
                    if (
                        route.proto_cardinality == Cardinality.UNARY_STREAM
                        or route.proto_cardinality == Cardinality.STREAM_STREAM
                    ):
                        # TODO: iterate reply
                        response = self.request_callback(route, request, {})
                    else:
                        
                        response = self.request_callback(route, request, {})
                    await stream.send_message(response)
                except Exception as e:
                    print(e)

            handle_partial = partial(handle, route=route)

            new_handler = Handler(
                handle_partial,
                route.proto_cardinality,
                # request and reply are already coded here, no coding is needed anymore
                None,
                None,
            )
            result[route_path] = new_handler

        return result


class GrpcTransport(BaseTransport):
    CONFIG_KEY = "grpc"

    def __init__(
        self, config: GrpcTransportConfig, converter: Optional[BaseConverter] = None
    ) -> None:
        super().__init__(config, converter)
        self.server: Optional[Server] = None

    async def start(self, routes: RoutesDict) -> None:
        handler_storage = HandlerStorage(routes, self.converter, self.got_request)
        self.server = Server([handler_storage], codec=RawCodec())

        listen(self.server, RecvRequest, recv_request)

        try:
            address: str = self.config.get("address", DEFAULT_CONFIG["address"])
            port: int = self.config.get("port", DEFAULT_CONFIG["port"])
        except KeyError as e:
            raise ValueError(
                f"{e.args[0]} is missed in default configuration of grpc transport"
            )

        # with graceful_exit([server]):  # TODO: replace, because it doesn't work on windows
        await self.server.start(address, port)
        # await server.wait_closed()

        logger.info(f"Start grpc server: {address}:{port}")

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            self.server = None
        else:
            logger.warning("Cannot stop not started server")


__all__ = ["GrpcTransport", "GrpcTransportConfig"]
