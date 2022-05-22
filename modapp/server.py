import asyncio
import platform
from enum import Enum
from typing import Any, Callable, Dict, Set

from loguru import logger

from modapp.routing import APIRouter

from .transports.grpc import (
    start as grpc_start,
    DEFAULT_CONFIG as GRPC_DEFAULT_CONFIG,
)
from .transports.socketio import (
    start as socketio_start,
    DEFAULT_CONFIG as SOCKETIO_DEFAULT_CONFIG,
)
from .types import DecoratedCallable

# uvloop doesn't support Windows yet
if platform.system() != 'Windows':
    import uvloop
    uvloop.install()


class Transport(Enum):
    LOCAL = "local"
    GRPC = "grpc"
    SOCKETIO = "socketio"


class Modapp:
    def __init__(self, communications: Set[Transport]):
        self.communications = communications
        self.config = {}
        self.router = APIRouter()
        if Transport.GRPC in communications:
            self.config[Transport.GRPC] = GRPC_DEFAULT_CONFIG.copy()
        if Transport.SOCKETIO in communications:
            self.config[Transport.SOCKETIO] = SOCKETIO_DEFAULT_CONFIG.copy()

    def run(self):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        grpc_server = None
        if Transport.GRPC in self.communications:
            grpc_server = loop.run_until_complete(
                grpc_start(self.config[Transport.GRPC], self.router.routes)
            )

        socketio_server = None
        if Transport.SOCKETIO in self.communications:
            socketio_server = loop.run_until_complete(
                socketio_start(self.config[Transport.SOCKETIO], self.router.routes)
            )
        try:
            logger.info("Server has started")
            loop.run_forever()
        except KeyboardInterrupt:
            logger.info("Server stop")
            if Transport.GRPC in self.communications and grpc_server is not None:
                grpc_server.close()

            if (
                Transport.SOCKETIO in self.communications
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

    def update_config(self, communication: Transport, config: Dict[str, Any]):
        self.config[communication].update(config)
