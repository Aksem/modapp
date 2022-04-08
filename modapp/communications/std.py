import asyncio
import json
from inspect import signature
from functools import partial
from typing import Dict
from pathlib import Path

from grpclib.const import Handler, Cardinality
from grpclib.events import listen, RecvRequest
from grpclib.server import Server
from loguru import logger

from ..routing import Route

DEFAULT_CONFIG = {}


async def recv_request(event: RecvRequest):
    logger.trace(f"Income request: {event.method_name}")


async def format_req(request_type, request_stream):
    request = await request_stream.recv_message()
    assert request is not None

    print('req->', request_type)
    # return request_type(**{ field.name: request[field.name] for field in request.DESCRIPTOR.fields })
    # field is tuple with FieldDescriptor as first element and field value as second
    return request_type(**{ field[0].name: field[1] for field in type(request).ListFields(request) })


def format_res(response_type, response):
    print('res->', response_type, json.loads(response.json(by_alias=True)))
    # TODO: optimize, implement with json dump&load
    # Problem: path to sring recursively
    return response_type(**json.loads(response.json(by_alias=True)))


class HandlerStorage:
    def __init__(self, routes: Dict[str, Route]):
        self.routes = routes

    def __mapping__(self):
        result = {}
        for route_path, route in self.routes.items():
            if route.router.service_cls is None:
                logger.warning(f'Route "{route_path}" has no service')
                continue
            # TODO: find better solution instead of workaround
            route.router.service_cls.__abstractmethods__ = frozenset()
            service = route.router.service_cls()
            generated_mapping = service.__mapping__()
            try:
                generated_handler = generated_mapping[route_path]
            except KeyError:
                logger.error(f'Generated handler for route "{route_path}" not found')
                continue

            handler_signature = signature(route.handler)
            request_parameter_name = list(handler_signature.parameters.keys())[0]
            request_type = handler_signature.parameters[request_parameter_name].annotation

            # TODO: find better solution instead of workaround
            route.router.service_cls.__abstractmethods__ = frozenset()
            service = route.router.service_cls()
            generated_mapping = service.__mapping__()
            try:
                generated_handler = generated_mapping[route_path]
            except KeyError:
                logger.error(f'Generated handler for route "{route_path}" not found')
                return

            cardinality = generated_handler.cardinality

            async def handle(stream, route, request_type, generated_handler, cardinality):
                formatted_request = await format_req(request_type, stream)
                if cardinality == Cardinality.UNARY_STREAM or cardinality == Cardinality.STREAM_STREAM:
                    # TODO: create context and pass to handler
                    response = await route.handler(formatted_request)
                else:
                    response = route.handler(formatted_request)
                await stream.send_message(format_res(generated_handler.reply_type, response))
            
            handle_partial = partial(handle, route=route, request_type=request_type, generated_handler=generated_handler, cardinality=cardinality)

            new_handler = Handler(
                handle_partial,
                generated_handler.cardinality,
                generated_handler.request_type,
                generated_handler.reply_type
            )
            result[route_path] = new_handler

        return result


async def start(config: Dict[str, str], routes: Dict[str, Route]):
    # TODO: form handlers and pass to server
    handler_storage = HandlerStorage(routes)
    server = Server([handler_storage])

    listen(server, RecvRequest, recv_request)

    # with graceful_exit([server]):  # TODO: replace, because it doesn't work on windows
    await server.start("127.0.0.1", 50051)
    # await server.wait_closed()

    logger.info("Start grpc server")

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
