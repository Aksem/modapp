"""
Dev Notes:
- if at least one header is added to response, status code will be successful 200, not 4xx/5xx.
  See: https://github.com/cirospaciari/socketify.py/issues/144
"""

from __future__ import annotations

import secrets
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator

from loguru import logger
from socketify import (
    App,
    CompressOptions,
    OpCode,
    Request,
    Response,
    WebSocket,
    sendfile,
)
from typing_extensions import override

from modapp.base_converter import BaseConverter
from modapp.base_transport import BaseTransport

try:
    from modapp.converters.json import JsonConverter
except ImportError:
    JsonConverter = None
try:
    from modapp.converters.protobuf import ProtobufConverter
except ImportError:
    ProtobufConverter = None

from modapp.errors import InvalidArgumentError, NotFoundError, ServerError
from modapp.routing import Cardinality, Route

from .web_socketify_config import DEFAULT_CONFIG, WebSocketifyTransportConfig

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


def _add_cors_headers_to_response(
    response: Response, cors_allow: str | None
) -> Response:
    if cors_allow is not None:
        response.write_header("Access-Control-Allow-Origin", cors_allow)
        response.write_header(
            "Access-Control-Allow-Headers", "Connection-Id, Request-Id, Content-Type"
        )
    return response


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
                response.write_status(404).end(self.converter.error_to_raw(error))
                return
            elif isinstance(error, InvalidArgumentError):
                response.write_status(422)
                response.end(self.converter.error_to_raw(error))
                return
            elif isinstance(error, ServerError):
                # does the same as return statement below, but shows explicitly mapping of ServerError to
                # http error
                _error = ServerError()
                response.write_status(500).end(self.converter.error_to_raw(_error))
                return
            _error = ServerError()
            response.write_status(500).end(self.converter.error_to_raw(_error))
            logger.exception(error)

        for route_path, route in routes.items():

            async def route_handler(
                route: Route, response: Response, request: Request
            ) -> None:
                data = await response.get_data()
                # NOTE: if we explicitly set status, it should be done before headers:
                # https://github.com/cirospaciari/socketify.py/issues/144

                if route.proto_cardinality == Cardinality.UNARY_UNARY:
                    result = await self.got_request(
                        route=route, raw_data=data.getvalue(), meta={}
                    )
                    if JsonConverter is not None and isinstance(
                        self.converter, JsonConverter
                    ):
                        content_type = "application/json"
                    elif ProtobufConverter is not None and isinstance(
                        self.converter, ProtobufConverter
                    ):
                        content_type = "application/octet-stream"
                    else:
                        content_type = ""

                    response.write_header("Content-Type", content_type)
                    _add_cors_headers_to_response(
                        response,
                        self.config.get("cors_allow", DEFAULT_CONFIG["cors_allow"]),
                    ).end(result)
                    return
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
                    await self._send_stream_responses_in_ws(
                        stream=response_stream, ws=ws, request_id=request_id
                    )
                    _add_cors_headers_to_response(
                        response.write_status(204),
                        self.config.get("cors_allow", DEFAULT_CONFIG["cors_allow"]),
                    ).end_without_body()
                    # TODO: how to stop on both ends?
                raise NotImplementedError()
                # TODO: other cardinalities

            http_route_path = route_path.replace(".", "/").lower()
            self.app.post(http_route_path, handler=partial(route_handler, route))

            def options_handler(response: Response, request: Request) -> None:
                # here should be end_without_body, but for unknown reason it is very slow
                _add_cors_headers_to_response(
                    response.write_status(200).write_header("Allow", "OPTIONS, POST"),
                    self.config.get("cors_allow", DEFAULT_CONFIG["cors_allow"]),
                ).end("")

            self.app.options(http_route_path, options_handler)
            logger.trace(f"Registered http route {http_route_path}")

        def connect_handler(response: Response, request: Request) -> None:
            _add_cors_headers_to_response(
                response, self.config.get("cors_allow", DEFAULT_CONFIG["cors_allow"])
            ).end({"id": secrets.token_urlsafe(20)})

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
            logger.error(f"Unknown path: {request.get_url()}")
            response.write_status(404)
            response.end("Not found")

        port = self.config.get("port", DEFAULT_CONFIG["port"])

        async def static_dir_index_handler(
            response: Response, request: Request, static_dir_path: Path
        ) -> None:
            # +1 for initial slash
            url_in_dir = request.get_url()[len(static_dir_path.name) + 1 :]
            if url_in_dir in ["", "/"]:
                index_html_path = static_dir_path / "index.html"
                if index_html_path.exists():
                    await sendfile(response, request, index_html_path)
                    return
            response.write_status(404)
            response.end("Not found")

        for static_dir_route, static_dir_path in self._static_dirs.items():
            logger.info(f"Host static dir: localhost:{port}{static_dir_route}")
            self.app.static(static_dir_route, static_dir_path)

            async def _static_dir_index_handler(
                response: Response, request: Request
            ) -> None:
                await static_dir_index_handler(response, request, static_dir_path)

            self.app.get(static_dir_route, _static_dir_index_handler)

        self.app.any("/*", unknown_path_handler)
        assert isinstance(port, int), "Int expected to be an int"
        self.app.listen(
            port,
            lambda config: logger.info(
                f"Start web socketify server: localhost:{config.port}"
            ),
        )
        socketify_app_run_async(self.app)

    @override
    def stop(self) -> None:
        if self.app is not None:
            # from app.loop.run:
            # clean up uvloop
            self.app.loop.uv_loop.stop()

            self.app.close()
            self.app = None
        else:
            logger.warning("Cannot stop not started server")


__all__ = ["WebSocketifyTransport", "WebSocketifyTransportConfig"]
