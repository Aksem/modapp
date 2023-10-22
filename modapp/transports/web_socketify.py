"""
Dev Notes:
- if at least one header is added to response, status code will be successful 200, not 4xx/5xx.
  See: https://github.com/cirospaciari/socketify.py/issues/144
"""
from __future__ import annotations
from pathlib import Path
import base64
import secrets
from functools import partial
from typing import TYPE_CHECKING, AsyncIterator

from loguru import logger
from typing_extensions import override
from socketify import (
    App,
    CompressOptions,
    Request,
    Response,
    WebSocket,
    OpCode,
)

from modapp.base_converter import BaseConverter
from modapp.base_transport import BaseTransport
from modapp.routing import Route, Cardinality
from modapp.errors import (
    InvalidArgumentError,
    NotFoundError,
    ServerError,
)
from .web_socketify_config import WebSocketifyTransportConfig, DEFAULT_CONFIG

if TYPE_CHECKING:
    from modapp.routing import RoutesDict


def socketify_app_run_async(app: App) -> None:
    if app._factory is not None:
        app._factory.populate()
    if app._ws_factory is not None:
        app._ws_factory.populate()

    # from app.loop.run
    app.loop.started = True
    app.loop.loop.call_soon(app.loop._keep_alive)


# TODO: return when issue socketify#144 is resolved
# def _prepare_response(response: Response, request: Request, data=None) -> None:
#     response.write_header("Access-Control-Allow-Origin", "http://localhost:5173")
#     response.write_header("Access-Control-Allow-Headers", "Connection-Id, Request-Id")
#     return data
#     # return response


# TODO: return when issue socketify#144 is resolved
# def modapp_error_to_http(
#     modapp_error: BaseModappError, converter: BaseConverter, response: Response
# ) -> None:
#     if isinstance(modapp_error, NotFoundError):
#         response.write_status(404).end("Not found")
#         return
#     elif isinstance(modapp_error, InvalidArgumentError):
#         response.write_status(422)
#         response.end(converter.error_to_raw(modapp_error))
#         return
#     elif isinstance(modapp_error, ServerError):
#         # does the same as return statement below, but shows explicitly mapping of ServerError to
#         # http error
#         response.write_status(500).end("Server error")
#         return
#     response.write_status(500).end("Internal error")


class WebSocketifyTransport(BaseTransport):
    CONFIG_KEY = "web_socketify"

    def __init__(
        self,
        config: WebSocketifyTransportConfig,
        converter: BaseConverter | None = None,
    ) -> None:
        super().__init__(config, converter)
        self.app: App | None = None
        self._static_dirs: dict[str, Path] = {}
        self._websockets_by_conn_id: dict[str, WebSocket] = {}

    def host_static_dir(self, dir_path: Path, route: str) -> None:
        self._static_dirs[route] = dir_path

    def _handle_websocket_message(
        self, ws: WebSocket, message: bytes | str, opcode: OpCode
    ) -> None:
        # recognize 'connect' message and save ws by conn_id
        print(ws, message, opcode)

    async def _send_stream_responses_in_ws(
        self, stream: AsyncIterator[bytes], ws: WebSocket, request_id: str
    ) -> None:
        async for message in stream:
            # TODO: build message with metadata like request_id
            ws.send(message)

    @override
    async def start(self, routes: RoutesDict) -> None:
        if self.app is not None:
            raise Exception(
                "Server is running already, stop it first to restart"
            )  # TODO: better exception

        self.app = App()

        @self.app.on_error
        def on_error(error, response: Response, request: Request) -> None:
            if isinstance(error, NotFoundError):
                response.write_status(404).end("Not found")
                return
            elif isinstance(error, InvalidArgumentError):
                response.write_status(422)
                response.end(self.converter.error_to_raw(error))
                return
            elif isinstance(error, ServerError):
                # does the same as return statement below, but shows explicitly mapping of ServerError to
                # http error
                response.write_status(500).end("Server error")
                return
            response.write_status(500).end("Internal error")
            logger.exception(error)

        for route_path, route in routes.items():

            async def route_handler(
                route: Route, response: Response, request: Request
            ) -> None:
                data = await response.get_data()
                # tmp repeated
                response.write_header(
                    "Access-Control-Allow-Origin", "http://localhost:5173"
                )
                response.write_header(
                    "Access-Control-Allow-Headers", "Connection-Id, Request-Id"
                )
                # tmp repeated end

                if route.proto_cardinality == Cardinality.UNARY_UNARY:
                    # try:
                    result = await self.got_request(
                        route=route, raw_data=data.getvalue(), meta={}
                    )
                    # response.write_header(
                    #     "Content-Type", "application/octet-stream"
                    # )
                    # temporary send base64 until we know how to create correct Uint8Array from binary data in js
                    response.end(base64.b64encode(result))
                    return
                    # except BaseModappError as modapp_error:
                    #     logger.trace(f"Http request handling error: {modapp_error}")
                    #     # modapp_error_to_http(
                    #     #     modapp_error, self.converter, _prepare_response(response)
                    #     # )

                    #     # if isinstance(modapp_error, NotFoundError):
                    #     #     response.write_status(404).end("Not found")
                    #     #     return
                    #     # elif isinstance(modapp_error, InvalidArgumentError):
                    #     #     response.write_status(422)
                    #     #     response.end(self.converter.error_to_raw(modapp_error))
                    #     #     return
                    #     # elif isinstance(modapp_error, ServerError):
                    #     #     # does the same as return statement below, but shows explicitly mapping of ServerError to
                    #     #     # http error
                    #     #     response.write_status(500).end("Server error")
                    #     #     return
                    #     # response.write_status(500).end("Internal error")

                    #     return
                    # except Exception as e:
                    #     logger.exception(e)
                    #     response.write_status(500).end("Internal error")
                    #     return
                elif route.proto_cardinality == Cardinality.UNARY_STREAM:
                    conn_id = request.get_header("connection-id")
                    if not isinstance(conn_id, str):
                        logger.error(
                            "'Connection-Id' header is missing or has invalid value"
                        )
                        response.write_status(400).end(
                            "'Connection-Id' header is missing or has invalid value"
                        )
                        return

                    try:
                        ws = self._websockets_by_conn_id[conn_id]
                    except KeyError:
                        logger.error(
                            f'Websocket connection with id "{conn_id}" not found'
                        )
                        response.write_status(404).end(
                            f'Websocket connection with id "{conn_id}" not found'
                        )
                        return

                    request_id = request.get_header("request-id")
                    if not isinstance(request_id, str):
                        logger.error(
                            "'Request-Id' header is missing or has invalid value"
                        )
                        response.write_status(400).end(
                            "'Request-Id' header is missing or has invalid value"
                        )
                        return

                    response_stream = await self.got_request(
                        route=route, raw_data=data.getvalue(), meta={}
                    )
                    # TODO: schedule execution
                    self._send_stream_responses_in_ws(
                        stream=response_stream, ws=ws, request_id=request_id
                    )
                    response.write_status(204).end_without_body()
                    # TODO: how to stop on both ends?
                raise NotImplementedError()
                # TODO: other cardinalities

            http_route_path = route_path.replace(".", "/").lower()
            self.app.post(http_route_path, handler=partial(route_handler, route))

            def options_handler(response: Response, request: Request) -> None:
                # tmp repeated
                response.write_header(
                    "Access-Control-Allow-Origin", "http://localhost:5173"
                )
                response.write_header(
                    "Access-Control-Allow-Headers", "Connection-Id, Request-Id"
                )
                # tmp repeated end
                # here should be end_without_body, but for unknown reason it is very slow
                response.write_header("Allow", "OPTIONS, POST").write_status(200).end(
                    ""
                )

            self.app.options(http_route_path, options_handler)
            logger.trace(f"Registered http route {http_route_path}")

        def connect_handler(response: Response, request: Request) -> None:
            # tmp repeated
            response.write_header(
                "Access-Control-Allow-Origin", "http://localhost:5173"
            )
            response.write_header(
                "Access-Control-Allow-Headers", "Connection-Id, Request-Id"
            )
            # tmp repeated end
            response.end({"id": secrets.token_urlsafe(20)})

        self.app.post("/connect", connect_handler)
        # TODO: configure websockets
        self.app.ws(
            "/stream",
            {
                "compression": CompressOptions.SHARED_COMPRESSOR,
                "max_payload_length": self.config.get(
                    "max_message_size_kb", DEFAULT_CONFIG["max_message_size_kb"]
                ),
                "idle_timeout": 12,
                # "open": ws_open,
                "message": self._handle_websocket_message,
                # "close": ws_close,
            },
        )

        def unknown_path_handler(response: Response, request: Request) -> None:
            # tmp repeated
            # response.write_header(
            #     "Access-Control-Allow-Origin", "http://localhost:5173"
            # )
            # response.write_header(
            #     "Access-Control-Allow-Headers", "Connection-Id, Request-Id"
            # )
            # tmp repeated end
            logger.error(f"Unknown path: {request.get_url()}")
            response.write_status(404)
            response.end("Not found")

        self.app.any("/*", unknown_path_handler)

        for static_dir_route, static_dir_path in self._static_dirs.items():
            self.app.static(static_dir_route, static_dir_path)

        port = self.config.get("port", DEFAULT_CONFIG["port"])
        assert isinstance(port, int), "Int expected to be an int"
        self.app.listen(
            port,
            lambda config: logger.info(
                f"Start web socketify server: localhost:{config.port}"
            ),
        )
        socketify_app_run_async(self.app)

    @override
    async def stop(self) -> None:
        if self.app is not None:
            # from app.loop.run:
            # clean up uvloop
            self.app.loop.uv_loop.stop()

            self.app.close()
            self.app = None
        else:
            logger.warning("Cannot stop not started server")


__all__ = ["WebSocketifyTransport", "WebSocketifyTransportConfig"]
