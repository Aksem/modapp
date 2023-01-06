import asyncio
import traceback
from random import randint, seed
from typing import Any, Dict, Optional

import socketio
from aiohttp import web
from google.rpc import status_pb2
from google.rpc.error_details_pb2 import BadRequest
from loguru import logger
from typing_extensions import NotRequired

from ..base_transport import BaseTransportConfig, BaseTransport
from ..communication_utils import (
    deserialize_request,
    run_request_handler,
    serialize_reply,
)
from ..errors import InvalidArgumentError, NotFoundError, ServerError, Status
from ..models import to_camel
from ..routing import Cardinality, Route, RoutesDict

seed(1)


class SocketioTransportConfig(BaseTransportConfig):
    address: NotRequired[str]
    port: NotRequired[int]


DEFAULT_CONFIG: SocketioTransportConfig = {"address": "127.0.0.1", "port": 9091}


class SocketioTransport(BaseTransport):
    CONFIG_KEY = "socketio"

    def __init__(self, config: SocketioTransportConfig) -> None:
        super().__init__(config)
        self.runner: Optional[web.AppRunner] = None

    async def start(self, routes: RoutesDict) -> None:
        sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")
        # server_routes = {}

        app = web.Application()
        sio.attach(app)
        # TODO: avoid
        # global server_routes
        # server_routes = routes

        @sio.event
        async def connect(sid, environ, auth):
            logger.info("connected: " + str(sid))

        @sio.event
        def disconnect(sid):
            logger.info("disconnected: " + str(sid))

        @sio.event
        async def grpc_request_v2(sid, meta, data):
            logger.trace("request_v2 " + str(meta))

            try:
                method_name = meta["methodName"]
                # connection_id = sid
            except KeyError:
                logger.error("Invalid meta in request")
                raise Exception("Invalid meta in request")
            # connection_id = meta.get("connectionId", None)

            try:
                route = routes[method_name]
            except KeyError:
                logger.error(f"Endpoint '{meta['methodName']}' not found")
                return ("Endpoint not found", None)

            try:
                request_data = deserialize_request(route, data)
            except InvalidArgumentError as error:
                status_proto = status_pb2.Status(
                    code=Status.INVALID_ARGUMENT.value,
                    message="Invalid data in request.",
                )
                detail = BadRequest(
                    field_violations=[
                        BadRequest.FieldViolation(
                            field=to_camel(field_name),
                            description=field_error,
                        )
                        for (field_name, field_error) in error.errors_by_fields.items()
                    ]
                )
                detail_container = status_proto.details.add()
                detail_container.Pack(detail)
                return (status_proto.SerializeToString(), None)

            handler_arguments = {"request": request_data}
            handler_arguments.update(
                {
                    meta_key: meta[to_camel(meta_key)]
                    for meta_key in route.handler_meta_keys
                }
            )
            try:
                if route.proto_cardinality == Cardinality.UNARY_UNARY:
                    reply = await run_request_handler(route, handler_arguments)
                    proto_reply = serialize_reply(route, reply)
                    # await sio.emit(f"{method_name}_reply", proto_reply)
                    return (None, proto_reply)
                elif route.proto_cardinality == Cardinality.UNARY_STREAM:
                    request_id = randint(0, 10000000)

                    async def handle_request(
                        request_id: int, handler_arguments: Dict[str, Any], route: Route
                    ):
                        try:
                            async for reply in route.handler(
                                **handler_arguments
                            ):  # TODO: handle validation error
                                proto_reply = serialize_reply(route, reply)
                                await sio.emit(
                                    f"{method_name}_{request_id}_reply", proto_reply
                                )
                                logger.trace(
                                    "Response stream message:"
                                    f" {method_name}_{request_id}_reply"
                                )
                        except Exception as error:
                            logger.error(error)
                            traceback.print_exc()
                            # send error?
                            raise ServerError(error)  # TODO: error only in debug?

                    loop = asyncio.get_event_loop()
                    asyncio.run_coroutine_threadsafe(
                        handle_request(request_id, handler_arguments, route), loop
                    )
                    return (None, request_id)
            except NotFoundError as error:
                # logger.error(error)
                traceback.print_exc()
                status_proto = status_pb2.Status(
                    code=Status.NOT_FOUND.value, message="Not found."
                )
                return (status_proto.SerializeToString(), None)
            except InvalidArgumentError as error:
                status_proto = status_pb2.Status(
                    code=Status.INVALID_ARGUMENT.value,
                    message="Invalid data in request.",
                )
                detail = BadRequest(
                    field_violations=[
                        BadRequest.FieldViolation(
                            field=to_camel(field_name),
                            description=field_error,
                        )
                        for (field_name, field_error) in error.errors_by_fields.items()
                    ]
                )
                detail_container = status_proto.details.add()
                detail_container.Pack(detail)
                return (status_proto.SerializeToString(), None)
            except ServerError as error:
                traceback.print_exc()
                if len(error.args) > 0:
                    message = error.args[0]
                else:
                    message = "Internal error"
                status_proto = status_pb2.Status(
                    code=Status.INTERNAL.value, message=message
                )
                return (status_proto.SerializeToString(), None)
            except BaseException as error:
                logger.error(f"Unhandled server error {error}")
                traceback.print_exc()
                status_proto = status_pb2.Status(
                    code=Status.INTERNAL.value, message="Internal server error."
                )
                return (status_proto.SerializeToString(), None)

        runner = web.AppRunner(app)
        await runner.setup()
        address = self.config.get("address", DEFAULT_CONFIG.get("address"))
        port = self.config.get("port", DEFAULT_CONFIG.get("port"))
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
