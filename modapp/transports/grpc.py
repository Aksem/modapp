from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Coroutine, cast

from grpclib.const import Handler
from grpclib.const import Status as GrpcStatus
from grpclib.encoding.base import CodecBase
from grpclib.exceptions import GRPCError
from grpclib.server import Server, Stream
from loguru import logger
from typing_extensions import override

from modapp.base_converter import BaseConverter
from modapp.base_transport import BaseTransport
from modapp.errors import (
    BaseModappError,
    InvalidArgumentError,
    NotFoundError,
    ServerError,
)
from modapp.routing import Cardinality
from modapp.types import Metadata

from .grpc_config import DEFAULT_CONFIG, GrpcTransportConfig

if TYPE_CHECKING:
    from modapp.routing import Route, RoutesDict


class RawCodec(CodecBase):
    __content_subtype__ = "proto"

    @override
    def encode(self, message: Any, message_type: Any) -> bytes:
        return cast(bytes, message)

    @override
    def decode(self, data: bytes, message_type: Any) -> Any:
        return data


def modapp_error_to_grpc(
    modapp_error: BaseModappError, converter: BaseConverter, error_details: bool
) -> GRPCError:
    if isinstance(modapp_error, NotFoundError):
        if len(modapp_error.args) > 0 and isinstance(modapp_error.args[0], str):
            message = modapp_error.args[0]
        else:
            message = None
        return GRPCError(status=GrpcStatus.NOT_FOUND, message=message)
    elif isinstance(modapp_error, InvalidArgumentError):
        if error_details:
            details=converter.error_to_raw(modapp_error)
            message = None
        else:
            message = ''
            for field_name, field_value in modapp_error.errors_by_fields.items():
                if field_name == 'non_field_errors' or field_name == 'nonFieldErrors':
                    message += field_value + '\n'
                else:
                    message += f'{field_name}: {field_value}\n'
            message = message.rstrip('\n')
            details = None
        return GRPCError(
            status=GrpcStatus.INVALID_ARGUMENT,
            message=message,
            details=details
        )
    elif isinstance(modapp_error, ServerError):
        # does the same as return statement below, but shows explicitly mapping of ServerError to
        # GRPCError
        return GRPCError(status=GrpcStatus.INTERNAL)
    return GRPCError(status=GrpcStatus.INTERNAL)


class HandlerStorage:
    def __init__(
        self,
        routes: RoutesDict,
        converter: BaseConverter,
        request_callback: Callable[
            [Route, bytes, Metadata], Coroutine[Any, Any, bytes | AsyncIterator[bytes]]
        ],
        error_details: bool,
    ) -> None:
        self.routes = routes
        self.converter = converter
        self.request_callback = request_callback
        self.error_details = error_details

    def __mapping__(self) -> dict[str, Handler]:
        result: dict[str, Handler] = {}
        for route_path, route in self.routes.items():

            async def handle(stream: Stream[Any, Any], route: Route) -> None:
                try:
                    request = await stream.recv_message()
                    assert request is not None

                    # TODO: pass meta
                    response = await self.request_callback(route, request, {})
                    if (
                        route.proto_cardinality == Cardinality.UNARY_STREAM
                        or route.proto_cardinality == Cardinality.STREAM_STREAM
                    ):
                        async for message in cast(AsyncIterator[bytes], response):
                            await stream.send_message(message)
                    else:
                        await stream.send_message(response)
                except BaseModappError as modapp_error:
                    logger.trace(f"Grpc request handling error: {modapp_error}")
                    raise modapp_error_to_grpc(
                        modapp_error, self.converter, self.error_details
                    )
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
        self, config: GrpcTransportConfig, converter: BaseConverter | None = None
    ) -> None:
        super().__init__(config, converter)
        self.server: Server | None = None

    @override
    async def start(self, routes: RoutesDict) -> None:
        error_details = self.config.get(
            "error_details", DEFAULT_CONFIG["error_details"]
        )
        handler_storage = HandlerStorage(
            routes, self.converter, self.got_request, error_details
        )
        self.server = Server([handler_storage], codec=RawCodec())

        # listen(self.server, RecvRequest, recv_request)

        try:
            address = self.config.get("address", DEFAULT_CONFIG["address"])
            assert isinstance(address, str), "Address expected to be a string"
            port = self.config.get("port", DEFAULT_CONFIG["port"])
            assert isinstance(port, int), "Int expected to be an int"
        except KeyError as e:
            raise ValueError(
                f"{e.args[0]} is missed in default configuration of grpc transport"
            )

        # with graceful_exit([server]):  # TODO: replace, because it doesn't work on windows
        await self.server.start(address, port)
        # await server.wait_closed()

        logger.info(f"Start grpc server: {address}:{port}")

    @override
    def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            self.server = None
        else:
            logger.warning("Cannot stop not started server")


__all__ = ["GrpcTransport", "GrpcTransportConfig"]
