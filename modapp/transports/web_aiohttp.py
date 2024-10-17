from __future__ import annotations

# import secrets
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import web
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

if TYPE_CHECKING:
    from modapp.routing import RoutesDict


def _get_cors_headers(cors_allow: str | None) -> dict[str, str]:
    headers = {
        "Access-Control-Allow-Headers": "Connection-Id, Request-Id, Content-Type"
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


async def route_handler(
    route: Route, request: web.Request, transport: WebAiohttpTransport
) -> web.Response:
    data = await request.content.read()
    cors_allow = transport.config.get("cors_allow", DEFAULT_CONFIG["cors_allow"])

    if route.proto_cardinality == Cardinality.UNARY_UNARY:
        try:
            result = await transport.got_request(route=route, raw_data=data, meta={})
        except Exception as error:
            raise _exception_to_response(error, transport.converter, cors_allow)

        return web.Response(
            body=result,
            status=201,
            headers=_get_cors_headers(cors_allow),
            content_type=_get_content_type(transport.converter),
        )
    # elif route.proto_cardinality == Cardinality.UNARY_STREAM:
    #     conn_id = request.get_header("connection-id")
    #     if not isinstance(conn_id, str):
    #         logger.error(
    #             "'Connection-Id' header is missing or has invalid value"
    #         )
    #         response.write_status(400).end(
    #             "'Connection-Id' header is missing or has invalid value"
    #         )
    #         return

    #     try:
    #         ws = self._websockets_by_conn_id[conn_id]
    #     except KeyError:
    #         logger.error(
    #             f'Websocket connection with id "{conn_id}" not found'
    #         )
    #         response.write_status(404).end(
    #             f'Websocket connection with id "{conn_id}" not found'
    #         )
    #         return

    #     request_id = request.get_header("request-id")
    #     if not isinstance(request_id, str):
    #         logger.error(
    #             "'Request-Id' header is missing or has invalid value"
    #         )
    #         response.write_status(400).end(
    #             "'Request-Id' header is missing or has invalid value"
    #         )
    #         return

    #     response_stream = await self.got_request(
    #         route=route, raw_data=data.getvalue(), meta={}
    #     )
    #     # TODO: schedule execution
    #     await self._send_stream_responses_in_ws(
    #         stream=response_stream, ws=ws, request_id=request_id
    #     )
    #     _add_cors_headers_to_response(
    #         response.write_status(204),
    #         self.config.get("cors_allow", DEFAULT_CONFIG["cors_allow"]),
    #     ).end_without_body()
    # TODO: how to stop on both ends?
    raise NotImplementedError()
    # TODO: other cardinalities


async def options_handler(request: web.Request, cors_allow: str | None) -> web.Response:
    return web.Response(
        status=200, headers={"Allow": "OPTIONS, POST", **_get_cors_headers(cors_allow)}
    )


async def static_dir_index_handler(
    request: web.Request, static_dir_path: Path
) -> web.FileResponse:
    # +1 for initial slash
    url_in_dir = request.url.path[len(static_dir_path.name) + 1 :]
    if url_in_dir in ["", "/"]:
        index_html_path = static_dir_path / "index.html"
        if index_html_path.exists():
            return web.FileResponse(index_html_path)

    return web.FileResponse(static_dir_path / url_in_dir)


async def unknown_path_handler(request: web.Request) -> web.Response:
    logger.error(f"Unknown path: {request.url}")
    return web.Response(status=404, reason="Not found")


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
                web.post(http_route_path, partial(route_handler, route, transport=self))
            )
            app_routes.append(
                web.options(
                    http_route_path, partial(options_handler, cors_allow=cors_allow)
                )
            )
            logger.trace(f"Registered http route {http_route_path}")

        self.app.add_routes(app_routes)

        port = self.config.get("port", DEFAULT_CONFIG["port"])
        if port is None:
            port = 0
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
                            static_dir_index_handler, static_dir_path=static_dir_path
                        ),
                    ),
                    web.static(static_dir_route, static_dir_path),
                ]
            )

        self.app.add_routes([web.route("*", "", unknown_path_handler)])

        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", port)
        await site.start()
        self.port = port
        logger.info(f"Start web aiohttp server: localhost:{port}")

    @override
    def stop(self) -> None:
        if self._runner is not None:
            # TODO
            # await self._runner.cleanup()
            self.app = None
            self._runner = None
        else:
            logger.warning("Cannot stop not started server")


__all__ = ["WebAiohttpTransport", "WebAiohttpTransportConfig"]
