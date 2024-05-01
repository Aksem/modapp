from __future__ import annotations

import asyncio
import concurrent.futures.process as process
from functools import partial
import importlib
import os
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, cast

from grpclib.const import Handler
from grpclib.const import Status as GrpcStatus
from grpclib.encoding.base import CodecBase
from grpclib.exceptions import GRPCError
from grpclib.server import Server, Stream
from loguru import logger
from typing_extensions import override

import modapp.async_queue as async_queue
from modapp.base_converter import BaseConverter
from modapp.base_transport import BaseTransport, got_request
from modapp.errors import (
    BaseModappError,
    InvalidArgumentError,
    NotFoundError,
    ServerError,
)
from modapp.routing import Cardinality
from modapp.server import CrossProcessConfig
from .grpc_config import GrpcTransportConfig, DEFAULT_CONFIG

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


async def mp_request_handler_async(
    route: Route,
    request: bytes,
    converter: BaseConverter,
    response_queue: async_queue.AsyncQueue,
):
    # TODO: meta
    response = await got_request(
        route=route, raw_data=request, meta={}, converter=converter
    )
    if (
        route.proto_cardinality == Cardinality.UNARY_STREAM
        or route.proto_cardinality == Cardinality.STREAM_STREAM
    ):
        async for message in cast(AsyncIterator[bytes], response):
            response_queue.put(message)
    else:
        response_queue.put(response)


async def request_handler_async(
    route: Route, request: bytes, converter: BaseConverter, stream: Stream
):
    # TODO: meta
    response = await got_request(
        route=route, raw_data=request, meta={}, converter=converter
    )
    if (
        route.proto_cardinality == Cardinality.UNARY_STREAM
        or route.proto_cardinality == Cardinality.STREAM_STREAM
    ):
        async for message in cast(AsyncIterator[bytes], response):
            await stream.send_message(message)
    else:
        await stream.send_message(response)


def import_module_member(module: str, member_name: str) -> Any:
    module_obj = importlib.import_module(module)
    return getattr(module_obj, member_name)


def mp_execute_handler(
    route_module: str,
    route_func_name: str,
    request: bytes,
    cross_process_config_factory_module: str,
    cross_process_config_factory_name: str,
    response_queue: async_queue.AsyncQueue,
):
    logger.trace(f"Running {route_module}.{route_func_name} in process {os.getpid()}")
    route_func = import_module_member(route_module, route_func_name)
    route = route_func.__modapp_route__

    cross_process_config_factory = import_module_member(
        cross_process_config_factory_module, cross_process_config_factory_name
    )
    cross_process_config = cross_process_config_factory()
    assert isinstance(cross_process_config, CrossProcessConfig)
    converter = cross_process_config.converter_by_transport[GrpcTransport]

    asyncio.run(mp_request_handler_async(route, request, converter, response_queue))


async def get_from_queue_and_send(queue: async_queue.AsyncQueue, stream: Stream):
    queue_end = async_queue.QueueEnd()
    while True:
        try:
            el = await queue.get_async()
            if el == queue_end:
                break
            await stream.send_message(el)
            queue.task_done()
        except Exception as e:
            logger.exception(e)
            raise GRPCError(GrpcStatus.INTERNAL)


async def handler_callback(
    stream: Stream[Any, Any],
    route: Route,
    converter: BaseConverter,
    executor: process.ProcessPoolExecutor | None,
    cross_process_config_factory: Callable[[], CrossProcessConfig] | None,
):
    logger.trace("Got request")
    try:
        # TODO: support of reading stream, not only one message
        request = await stream.recv_message()
        assert request is not None
    except Exception as e:
        logger.exception(e)
        raise GRPCError(GrpcStatus.INTERNAL)

    if executor is not None:
        response_queue = async_queue.create_async_process_queue()
        loop = asyncio.get_running_loop()
        get_and_send_task = asyncio.create_task(
            get_from_queue_and_send(response_queue, stream)
        )
        try:
            logger.trace(
                f"Executor processes: {executor._processes.keys()}, count = {len(executor._processes)}"
            )
            await loop.run_in_executor(
                executor,
                mp_execute_handler,
                route.handler.__module__,
                route.handler.__name__,
                request,
                cross_process_config_factory.__module__ if cross_process_config_factory is not None else None,
                cross_process_config_factory.__name__ if cross_process_config_factory is not None else None,
                response_queue,
            )
            response_queue.put(async_queue.QueueEnd())
        except BaseModappError as modapp_error:
            logger.trace(f"Grpc request handling error: {modapp_error}")
            raise modapp_error_to_grpc(modapp_error, converter)
        except Exception as e:
            logger.exception(e)
            raise GRPCError(GrpcStatus.INTERNAL)

        await get_and_send_task
    else:
        # no multiprocessing, execute in main process
        try:
            await request_handler_async(route, request, converter, stream)
        except BaseModappError as modapp_error:
            logger.trace(f"Grpc request handling error: {modapp_error}")
            raise modapp_error_to_grpc(modapp_error, converter)
        except Exception as e:
            logger.exception(e)
            raise GRPCError(GrpcStatus.INTERNAL)


class HandlerStorage:
    def __init__(
        self,
        routes: RoutesDict,
        converter: BaseConverter,
        executor: process.ProcessPoolExecutor | None,
        cross_process_config_factory: Callable[[], CrossProcessConfig] | None = None,
    ) -> None:
        self.routes = routes
        self.converter = converter
        self.executor = executor
        self.cross_process_config_factory = cross_process_config_factory

    def __mapping__(self) -> dict[str, Handler]:
        result: dict[str, Handler] = {}
        for route_path, route in self.routes.items():
            partial_handler_callback = partial(
                handler_callback,
                route=route,
                converter=self.converter,
                executor=self.executor,
                cross_process_config_factory=self.cross_process_config_factory,
            )
            new_handler = Handler(
                partial_handler_callback,
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
        self.executor: process.ProcessPoolExecutor | None = None
        self.server: Server | None = None

    @override
    async def start(self, routes: RoutesDict, max_workers: int | None = None) -> None:
        if max_workers is None or max_workers > 1:
            self.executor = process.ProcessPoolExecutor(max_workers=max_workers)
        else:
            self.executor = None
        handler_storage = HandlerStorage(
            routes, self.converter, self.executor, self.cross_process_config_factory
        )
        self.server = Server([handler_storage], codec=RawCodec())

        # listen(self.server, RecvRequest, recv_request)

        try:
            address = self.config.get("address", DEFAULT_CONFIG["address"])
            assert isinstance(address, str), "Address expected to be a string"
            port = self.config.get("port", DEFAULT_CONFIG["port"])
            assert isinstance(port, int), "Port expected to be an int"
        except KeyError as e:
            raise ValueError(
                f"{e.args[0]} is missed in default configuration of grpc transport"
            )

        # with graceful_exit([server]):  # TODO: replace, because it doesn't work on windows
        await self.server.start(address, port)
        # await server.wait_closed()

        logger.info(f"Start grpc server: {address}:{port}")

    @override
    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            self.server = None
        else:
            logger.warning("Cannot stop not started server")

        if self.executor is not None:
            self.executor.shutdown()
            self.executor = None


__all__ = ["GrpcTransport", "GrpcTransportConfig"]
