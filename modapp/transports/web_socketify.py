from __future__ import annotations
import secrets
from functools import partial
from typing import TYPE_CHECKING

from loguru import logger
from typing_extensions import NotRequired, override
from socketify import App, CompressOptions

from modapp.base_converter import BaseConverter
from modapp.base_transport import BaseTransport, BaseTransportConfig

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


class WebSocketifyTransportConfig(BaseTransportConfig):
    port: NotRequired[int]


DEFAULT_CONFIG: WebSocketifyTransportConfig = {
    "port": 3000,
    "max_message_size_kb": 4096,
}


class WebSocketifyTransport(BaseTransport):
    CONFIG_KEY = "web_socketify"

    def __init__(
        self,
        config: WebSocketifyTransportConfig,
        converter: BaseConverter | None = None,
    ) -> None:
        super().__init__(config, converter)
        self.app: App | None = None

    @override
    async def start(self, routes: RoutesDict) -> None:
        if self.app is not None:
            raise Exception(
                "Server is running already, stop it first to restart"
            )  # TODO: better exception

        self.app = App()
        for route_path, route in routes.items():

            def route_handler(route, request, response) -> None:
                response.end("{}")

            self.app.post(
                route_path.replace(".", "/"), handler=partial(route_handler, route)
            )

        self.app.post(
            "/auth", lambda req, res: res.end({"id": secrets.token_urlsafe(20)})
        )
        # TODO: configure websockets
        # self.app.ws(
        #     "/stream",
        #     {
        #         "compression": CompressOptions.SHARED_COMPRESSOR,
        #         "max_payload_length": self.config["max_message_size_kb"],
        #         "idle_timeout": 12,
        #         "open": ws_open,
        #         "message": ws_message,
        #         "close": ws_close,
        #     },
        # )

        port = self.config.get("port", DEFAULT_CONFIG["port"])
        assert isinstance(port, int), "Int expected to be an int"
        self.app.listen(
            port,
            lambda config: logger.info(
                f"Start web socketify server: localhost:{config.port}"
            ),
        )
        self.app.run()

    @override
    async def stop(self) -> None:
        if self.app is not None:
            self.app.close()
            self.app = None
        else:
            logger.warning("Cannot stop not started server")


__all__ = ["WebSocketifyTransport", "WebSocketifyTransportConfig"]
