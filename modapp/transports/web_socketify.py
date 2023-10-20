from __future__ import annotations
from pathlib import Path
import secrets
from functools import partial
from typing import TYPE_CHECKING

from loguru import logger
from typing_extensions import override
from socketify import App, CompressOptions, Request, Response

from modapp.base_converter import BaseConverter
from modapp.base_transport import BaseTransport
from modapp.routing import Route
from .web_socketify_config import WebSocketifyTransportConfig, DEFAULT_CONFIG

# from modapp.errors import (
#     BaseModappError,
#     InvalidArgumentError,
#     NotFoundError,
#     ServerError,
# )
# from modapp.routing import Cardinality
# from modapp.types import Metadata

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

    def host_static_dir(self, dir_path: Path, route: str) -> None:
        self._static_dirs[route] = dir_path

    @override
    async def start(self, routes: RoutesDict) -> None:
        if self.app is not None:
            raise Exception(
                "Server is running already, stop it first to restart"
            )  # TODO: better exception

        self.app = App()
        for route_path, route in routes.items():

            async def route_handler(route: Route, response: Response, request: Request) -> None:
                data = await response.get_data()
                # TODO: if unary-stream, store it
                result = await self.got_request(route=route, raw_data=data.getvalue(), meta={})
                response.end(result)

            http_route_path = route_path.replace(".", "/")
            self.app.post(http_route_path, handler=partial(route_handler, route))
            logger.trace(f"Registered http route {http_route_path}")

        self.app.post(
            "/auth", lambda req, res: res.end({"id": secrets.token_urlsafe(20)})
        )
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
                # "message": ws_message,
                # "close": ws_close,
            },
        )

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
