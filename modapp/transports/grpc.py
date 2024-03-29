from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Dict, Optional

from grpclib.const import Handler, Status as GrpcStatus
from grpclib.encoding.base import CodecBase
# from grpclib.events import RecvRequest, listen
from grpclib.exceptions import GRPCError
from grpclib.server import Server, Stream
from loguru import logger
from typing_extensions import NotRequired

from ..base_converter import BaseConverter
from ..base_transport import BaseTransport, BaseTransportConfig
from ..errors import BaseModappError, ServerError, InvalidArgumentError, NotFoundError
from ..routing import Cardinality

if TYPE_CHECKING:
    from ..routing import Route, RoutesDict


class GrpcTransportConfig(BaseTransportConfig):
    address: NotRequired[str]
    port: NotRequired[int]


DEFAULT_CONFIG: GrpcTransportConfig = {"address": "127.0.0.1", "port": 50051}


# async def recv_request(event: RecvRequest):
#     logger.trace(f"Income request: {event.method_name}")


class RawCodec(CodecBase):
    __content_subtype__ = "proto"

    def encode(self, message, message_type):
        return message

    def decode(self, data: bytes, message_type):
        return data


def modapp_error_to_grpc(
    modapp_error: BaseModappError, converter: BaseConverter
) -> GRPCError:
    if isinstance(modapp_error, NotFoundError):
        return GRPCError(status=GrpcStatus.NOT_FOUND)
    elif isinstance(modapp_error, InvalidArgumentError):
        return GRPCError(
            status=GrpcStatus.INVALID_ARGUMENT,
            details=converter.error_to_raw(modapp_error),
        )
    elif isinstance(modapp_error, ServerError):
        # does the same as return statement below, but shows explicitly mapping of ServerError to
        # GRPCError
        return GRPCError(status=GrpcStatus.INTERNAL)
    return GRPCError(status=GrpcStatus.INTERNAL)


class HandlerStorage:
    def __init__(
        self, routes: RoutesDict, converter: BaseConverter, request_callback
    ) -> None:
        self.routes = routes
        self.converter = converter
        self.request_callback = request_callback

    def __mapping__(self):
        result: Dict[str, Handler] = {}
        for route_path, route in self.routes.items():

            async def handle(stream: Stream, route: Route):
                try:
                    request = await stream.recv_message()
                    assert request is not None

                    # TODO: pass meta
                    response = await self.request_callback(route, request, {})
                    if (
                        route.proto_cardinality == Cardinality.UNARY_STREAM
                        or route.proto_cardinality == Cardinality.STREAM_STREAM
                    ):
                        async for message in response:
                            await stream.send_message(message)
                    else:
                        await stream.send_message(response)
                except BaseModappError as modapp_error:
                    raise modapp_error_to_grpc(modapp_error, self.converter)
                except Exception as e:
                    logger.exception(e)

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

        # listen(self.server, RecvRequest, recv_request)

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
