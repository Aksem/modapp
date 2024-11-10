from __future__ import annotations

import asyncio
from functools import partial
import json
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator
import uuid

from aiohttp import web, WSMsgType
from loguru import logger
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

from modapp.errors import (
    InvalidArgumentError,
    NotFoundError,
    ServerError,
)
from modapp.routing import Cardinality, Route

from .web_aiohttp_config import DEFAULT_CONFIG, WebAiohttpTransportConfig
from .utils.free_port import get_free_port

if TYPE_CHECKING:
    from modapp.routing import RoutesDict


def _get_cors_headers(cors_allow: str | None) -> dict[str, str]:
    headers = {
        "Access-Control-Allow-Headers": "Connection-Id, Content-Type, Stream-Id"
    }
    if cors_allow is not None:
        headers["Access-Control-Allow-Origin"] = cors_allow
    return headers


def _exception_to_response(
    error: Exception, converter: BaseConverter, cors_allow: str | None
) -> Exception:
    if isinstance(error, NotFoundError):
        return web.HTTPNotFound(
            headers=_get_cors_headers(cors_allow),
            body=converter.error_to_raw(error),
            content_type=_get_content_type(converter),
        )
    elif isinstance(error, InvalidArgumentError):
        return web.HTTPUnprocessableEntity(
            headers=_get_cors_headers(cors_allow),
            body=converter.error_to_raw(error),
            content_type=_get_content_type(converter),
        )
    elif isinstance(error, ServerError):
        # does the same as return statement below, but shows explicitly mapping of ServerError to
        # http error
        return web.HTTPInternalServerError(
            headers=_get_cors_headers(cors_allow),
            body=converter.error_to_raw(error),
            content_type=_get_content_type(converter),
        )

    return web.HTTPInternalServerError(headers=_get_cors_headers(cors_allow))


def _get_content_type(converter: BaseConverter) -> str:
    if JsonConverter is not None and isinstance(converter, JsonConverter):
        content_type = "application/json"
    elif ProtobufConverter is not None and isinstance(converter, ProtobufConverter):
        content_type = "application/octet-stream"
    else:
        content_type = ""
    return content_type


class WebAiohttpTransport(BaseTransport):
    CONFIG_KEY = "web_aiohttp"

    def __init__(
        self,
        config: WebAiohttpTransportConfig,
        converter: BaseConverter | None = None,
    ) -> None:
        super().__init__(config, converter)
        self.port: int = 0
        self.app: web.Application | None = None
        self._static_dirs: dict[str, Path] = {}
        self._runner: web.AppRunner | None = None
        self._msg_queue_by_conn_id: dict[str, asyncio.Queue] = {}
        self._stream_ids: list[str] = []
        self._sending_to_ws_tasks: list[asyncio.Task] = []

    def host_static_dir(self, dir_path: Path, route: str) -> None:
        self._static_dirs[route] = dir_path

    @override
    async def start(self, routes: RoutesDict) -> None:
        if self.app is not None:
            raise Exception(
                "Server is running already, stop it first to restart"
            )  # TODO: better exception

        self.app = web.Application()
        cors_allow: str | None = self.config.get(
            "cors_allow", DEFAULT_CONFIG["cors_allow"]
        )
        app_routes: list[web.RouteDef] = []
        for route_path, route in routes.items():
            http_route_path = route_path.replace(".", "/").lower()
            app_routes.append(
                web.post(
                    http_route_path, partial(self.route_handler, route, transport=self)
                )
            )
            app_routes.append(
                web.options(
                    http_route_path,
                    partial(self.options_handler, cors_allow=cors_allow),
                )
            )
            logger.trace(f"Registered http route {http_route_path}")

        self.app.add_routes(app_routes)

        port = self.config.get("port", DEFAULT_CONFIG["port"])
        if port is None or port == 0:
            port = get_free_port()
        assert isinstance(port, int), "Int expected to be an int"

        for static_dir_route, static_dir_path in self._static_dirs.items():
            logger.info(f"Host static dir: 127.0.0.1:{port}{static_dir_route}")
            self.app.add_routes(
                [
                    # we need 'get' to be able resolve index.html, but we need to keep in mind,
                    # that 'get' with concrete path handles only this path, and static files are
                    # subpathes. Use 'static' to add all subpathes
                    web.get(
                        static_dir_route,
                        partial(
                            self.static_dir_index_handler,
                            static_dir_path=static_dir_path,
                        ),
                    ),
                    web.static(static_dir_route, static_dir_path),
                ]
            )

        self.app.add_routes([web.get("/ws", self.websocket_handler)])
        self.app.add_routes([web.route("*", "", self.unknown_path_handler)])

        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", port)
        await site.start()
        self.port = port
        logger.info(f"Start server: 127.0.0.1:{port}")
        logger.trace(f"Start web aiohttp server: 127.0.0.1:{port}")

    async def route_handler(
        self, route: Route, request: web.Request, transport: WebAiohttpTransport
    ) -> web.Response:
        data = await request.content.read()
        cors_allow = transport.config.get("cors_allow", DEFAULT_CONFIG["cors_allow"])

        if route.proto_cardinality == Cardinality.UNARY_UNARY:
            try:
                result = await transport.got_request(
                    route=route, raw_data=data, meta={}
                )
            except Exception as error:
                raise _exception_to_response(error, transport.converter, cors_allow)

            return web.Response(
                body=result,
                status=201,
                headers=_get_cors_headers(cors_allow),
                content_type=_get_content_type(transport.converter),
            )
        elif route.proto_cardinality == Cardinality.UNARY_STREAM:
            conn_id = request.headers.get("Connection-Id")
            if not isinstance(conn_id, str):
                logger.error("'Connection-Id' header is missing or has invalid value")
                return web.Response(
                    status=400,
                    headers=_get_cors_headers(cors_allow),
                    reason="'Connection-Id' header is missing or has invalid value",
                )

            if conn_id not in self._msg_queue_by_conn_id:
                logger.error("Websocket connection with such 'Connection-Id' not found")
                return web.Response(
                    status=400,
                    headers=_get_cors_headers(cors_allow),
                    reason="Websocket connection with such 'Connection-Id' not found",
                )

            stream_id = str(uuid.uuid4())
            while stream_id in self._stream_ids:
                stream_id = str(uuid.uuid4())

            response_stream = await self.got_request(
                route=route, raw_data=data, meta={}
            )
            assert isinstance(response_stream, AsyncIterator)
            sending_task = asyncio.create_task(
                self._send_messages_to_ws(response_stream, conn_id, stream_id)
            )
            self._sending_to_ws_tasks.append(sending_task)

            return web.Response(
                status=201,
                headers={**_get_cors_headers(cors_allow), "Stream-Id": stream_id},
                content_type=_get_content_type(transport.converter),
            )

        # TODO: how to stop on both ends?
        raise NotImplementedError()
        # TODO: other cardinalities

    async def _send_messages_to_ws(
        self, iterator: AsyncIterator[bytes], connection_id: str, stream_id: str
    ):
        conn_queue = self._msg_queue_by_conn_id[connection_id]
        async for msg in iterator:
            await conn_queue.put(json.dumps({ "streamId": stream_id, "message": msg.decode() }))
        await conn_queue.put(json.dumps({ "streamId": stream_id, "end": True }))

    async def options_handler(
        self, request: web.Request, cors_allow: str | None
    ) -> web.Response:
        return web.Response(
            status=200,
            headers={"Allow": "OPTIONS, POST", **_get_cors_headers(cors_allow)},
        )

    async def static_dir_index_handler(
        self, request: web.Request, static_dir_path: Path
    ) -> web.FileResponse:
        # +1 for initial slash
        url_in_dir = request.url.path[len(static_dir_path.name) + 1 :]
        if url_in_dir in ["", "/"]:
            index_html_path = static_dir_path / "index.html"
            if index_html_path.exists():
                return web.FileResponse(index_html_path)

        return web.FileResponse(static_dir_path / url_in_dir)

    async def unknown_path_handler(self, request: web.Request) -> web.Response:
        logger.error(f"Unknown path: {request.url}")
        return web.Response(status=404, reason="Not found")

    async def websocket_handler(self, request: web.Request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        conn_id = str(uuid.uuid4())
        while conn_id in self._msg_queue_by_conn_id:
            conn_id = str(uuid.uuid4())

        conn_queue = asyncio.Queue()
        self._msg_queue_by_conn_id[conn_id] = conn_queue
        conn_id_msg = {"connectionId": conn_id}
        await ws.send_str(data=json.dumps(conn_id_msg))

        sending_task = asyncio.create_task(self._send_ws_messages(conn_queue, ws))
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                if msg.data == 'close':
                    await ws.close()
            elif msg.type == WSMsgType.ERROR:
                print('ws connection closed with exception %s' %
                    ws.exception())

        sending_task.cancel()
        for task in self._sending_to_ws_tasks:
            task.cancel()
        self._sending_to_ws_tasks = []
        logger.info(f"Websocket connection '{conn_id}' closed")
        return ws

    async def _send_ws_messages(self, connection_queue: asyncio.Queue, ws):
        while True:
            msg = await connection_queue.get()
            # TODO: allow to end connection
            # TODO: support of all converters, not only json
            await ws.send_str(msg)

    @override
    def stop(self) -> None:
        if self._runner is not None:
            loop = asyncio.get_running_loop()
            loop.create_task(self._runner.cleanup())
            self.app = None
            self._runner = None
        else:
            logger.warning("Cannot stop not started server")

        for task in self._sending_to_ws_tasks:
            task.cancel()
        self._sending_to_ws_tasks = []


__all__ = ["WebAiohttpTransport", "WebAiohttpTransportConfig"]
