import asyncio
import traceback
from typing import Any, Dict
from random import randint, seed

import socketio
from aiohttp import web
from google.rpc import status_pb2
from google.rpc.error_details_pb2 import BadRequest
from loguru import logger

from ..errors import NotFoundError, InvalidArgumentError, Status, ServerError
from ..routing import Route, Cardinality
from ..communication_utils import (
    deserialize_request,
    serialize_reply,
    run_request_handler,
)
from ..models import to_camel

seed(1)


DEFAULT_CONFIG = {"port": 9091}

sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")
server_routes = {}


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
        route = server_routes[method_name]
    except KeyError:
        logger.error(f"Endpoint '{meta['methodName']}' not found")
        return ("Endpoint not found", None)

    try:
        request_data = deserialize_request(route, data)
    except InvalidArgumentError as error:
        status_proto = status_pb2.Status(
            code=Status.INVALID_ARGUMENT.value, message="Invalid data in request."
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

    handler_arguments = {'request': request_data}
    handler_arguments.update({meta_key: meta[to_camel(meta_key)] for meta_key in route.handler_meta_keys})
    try:
        if route.proto_cardinality == Cardinality.UNARY_UNARY:
            reply = await run_request_handler(route, handler_arguments)
            proto_reply = serialize_reply(route, reply)
            # await sio.emit(f"{method_name}_reply", proto_reply)
            return (None, proto_reply)
        elif route.proto_cardinality == Cardinality.UNARY_STREAM:
            request_id = randint(0, 10000000)

            async def handle_request(
                request_id: int,
                handler_arguments: Dict[str, Any],
                route: Route
            ):
                try:
                    async for reply in route.handler(
                        **handler_arguments
                    ):  # TODO: handle validation error
                        proto_reply = serialize_reply(route, reply)
                        await sio.emit(f"{method_name}_{request_id}_reply", proto_reply)
                        logger.trace(
                            f"Response stream message: {method_name}_{request_id}_reply"
                        )
                except Exception as error:
                    logger.error(error)
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
            code=Status.INVALID_ARGUMENT.value, message="Invalid data in request."
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


async def start(config: Dict[str, Any], routes: Dict[str, Route]):
    app = web.Application()
    sio.attach(app)
    global server_routes
    server_routes = routes

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", config["port"])
    await site.start()
    logger.info("Start socketio server: 127.0.0.1:" + str(config["port"]))
    return runner
