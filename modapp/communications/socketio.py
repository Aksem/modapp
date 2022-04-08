import asyncio
import json
from typing import Any, Dict

import socketio
from aiohttp import web
from loguru import logger

from ..errors import NotFoundError, InvalidArgumentError
from ..routing import Route


DEFAULT_CONFIG = {
    'port': 9091
}

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
        method_type = meta["methodType"]
    except KeyError:
        logger.error("Invalid meta in request")
        raise Exception("Invalid meta in request")

    try:
        route = server_routes[method_name]
    except KeyError:
        logger.error(f"Endpoint '{meta['methodName']}' not found")
        return ("Endpoint not found", None)

    try:
        # TODO: move to worker manager or similar?
        if method_type == 'UnaryUnary':
            proto_request = route.proto_request_type.FromString(data)
            request_data = route.request_type(**{ field[0].name: field[1] for field in type(proto_request).ListFields(proto_request) })

            if asyncio.iscoroutine(route.handler):
                reply = await route.handler(request_data)
            else:
                reply = route.handler(request_data)

            proto_reply = route.proto_reply_type(**json.loads(reply.json(by_alias=True))).SerializeToString()
            # await sio.emit(f"{method_name}_reply", proto_reply)
            return (None, proto_reply)
    except NotFoundError:
        logger.error('Not found error')
    except InvalidArgumentError:
        logger.error('Invalid argument error')
    except BaseException as err:
        logger.error('Server error')
        print(err)


async def start(config: Dict[str, Any], routes: Dict[str, Route]):
    app = web.Application()
    sio.attach(app)
    global server_routes
    server_routes = routes

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", config['port'])
    await site.start()
    logger.info("Start socketio server on port " + str(config['port']))
    return runner
