import asyncio
import json
from functools import partial
from typing import Dict, Union

from grpclib.const import Handler
from grpclib.events import listen, RecvRequest
from grpclib.server import Server
from loguru import logger

from ..routing import Route, Cardinality

DEFAULT_CONFIG = {
    "port": 50051
}


async def recv_request(event: RecvRequest):
    logger.trace(f"Income request: {event.method_name}")


async def format_req(request_type, request_stream):
    request = await request_stream.recv_message()
    assert request is not None

    print("req->", request_type)
    # return request_type(**{ field.name: request[field.name] for field in request.DESCRIPTOR.fields })
    # field is tuple with FieldDescriptor as first element and field value as second
    return request_type(
        **{field[0].name: field[1] for field in type(request).ListFields(request)}
    )


def format_res(response_type, response):
    print("res->", response_type, json.loads(response.json(by_alias=True)))
    # TODO: optimize, implement with json dump&load
    # Problem: path to sring recursively
    return response_type(**json.loads(response.json(by_alias=True)))


class HandlerStorage:
    def __init__(self, routes: Dict[str, Route]):
        self.routes = routes

    def __mapping__(self):
        result = {}
        for route_path, route in self.routes.items():

            async def handle(stream, route):
                formatted_request = await format_req(route.request_type, stream)
                if (
                    route.proto_cardinality == Cardinality.UNARY_STREAM
                    or route.proto_cardinality == Cardinality.STREAM_STREAM
                ):
                    # TODO: create context and pass to handler
                    response = await route.handler(formatted_request)
                else:
                    response = route.handler(formatted_request)
                await stream.send_message(format_res(route.proto_reply_type, response))

            handle_partial = partial(handle, route=route)

            new_handler = Handler(
                handle_partial,
                route.proto_cardinality,
                route.proto_request_type,
                route.proto_reply_type,
            )
            result[route_path] = new_handler

        return result


async def start(config: Dict[str, Union[str, int]], routes: Dict[str, Route]):
    # TODO: form handlers and pass to server
    handler_storage = HandlerStorage(routes)
    server = Server([handler_storage])

    listen(server, RecvRequest, recv_request)

    port = int(config.get("port", DEFAULT_CONFIG["port"]))
    # with graceful_exit([server]):  # TODO: replace, because it doesn't work on windows
    await server.start("127.0.0.1", port)
    # await server.wait_closed()

    logger.info(f"Start grpc server: 127.0.0.1:{port}")

    return server


if __name__ == "__main__":

    def get_or_create_eventloop():
        try:
            return asyncio.get_event_loop()
        except RuntimeError as ex:
            if "There is no current event loop in thread" in str(ex):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return asyncio.get_event_loop()

    asyncio.run(start({}))
    loop = get_or_create_eventloop()
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.stop()
