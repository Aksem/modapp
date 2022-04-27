import asyncio
import platform
from enum import Enum
from typing import Any, Callable, Dict, Set

from loguru import logger

from modapp.routing import APIRouter

from .communications.grpc import (
    start as grpc_start,
    DEFAULT_CONFIG as GRPC_DEFAULT_CONFIG,
)
from .communications.socketio import (
    start as socketio_start,
    DEFAULT_CONFIG as SOCKETIO_DEFAULT_CONFIG,
)
from .types import DecoratedCallable

# uvloop doesn't support Windows yet
if platform.system() != 'Windows':
    import uvloop
    uvloop.install()


class Communication(Enum):
    LOCAL = "local"
    GRPC = "grpc"
    SOCKETIO = "socketio"


class Modapp:
    def __init__(self, communications: Set[Communication]):
        self.communications = communications
        self.config = {}
        self.router = APIRouter()
        if Communication.GRPC in communications:
            self.config[Communication.GRPC] = GRPC_DEFAULT_CONFIG.copy()
        if Communication.SOCKETIO in communications:
            self.config[Communication.SOCKETIO] = SOCKETIO_DEFAULT_CONFIG.copy()

    def run(self):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        grpc_server = None
        if Communication.GRPC in self.communications:
            grpc_server = loop.run_until_complete(
                grpc_start(self.config[Communication.GRPC], self.router.routes)
            )

        socketio_server = None
        if Communication.SOCKETIO in self.communications:
            socketio_server = loop.run_until_complete(
                socketio_start(self.config[Communication.SOCKETIO], self.router.routes)
            )
        try:
            logger.info("Server has started")
            loop.run_forever()
        except KeyboardInterrupt:
            logger.info("Server stop")
            if Communication.GRPC in self.communications and grpc_server is not None:
                grpc_server.close()

            if (
                Communication.SOCKETIO in self.communications
                and socketio_server is not None
            ):
                loop.run_until_complete(socketio_server.cleanup())

    def endpoint(
        self, route_path: str
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            self.router.add_endpoint(route_path, func)
            return func

        return decorator

    def include_router(self, router: APIRouter) -> None:
        for route in router.routes.values():
            self.router.add_route(route)

    def update_config(self, communication: Communication, config: Dict[str, Any]):
        self.config[communication].update(config)
