import asyncio
import platform
from typing import Callable, Dict, Optional, Set

from loguru import logger

from modapp.base_transport import BaseTransportConfig, BaseTransport
from modapp.routing import APIRouter

from .types import DecoratedCallable

# uvloop doesn't support Windows yet
if platform.system() != "Windows":
    import uvloop

    # install uvloop event loop to get better performance of event loop
    uvloop.install()


class Modapp:
    def __init__(
        self,
        transports: Set[BaseTransport],
        config: Optional[Dict[str, BaseTransportConfig]] = None,
    ) -> None:
        self.transports = transports
        self.config: Dict[str, BaseTransportConfig] = {}
        if config is not None:
            self.config = config
        self.router = APIRouter()

    def run(self) -> None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        for transport in self.transports:
            loop.run_until_complete(
                transport.start(
                    self.router.routes
                )
            )

        try:
            logger.info("Server has started")
            loop.run_forever()
        except KeyboardInterrupt:
            logger.info("Server stop")

            for transport in self.transports:
                loop.run_until_complete(transport.stop())

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

    def update_config(self, transport: BaseTransport, config: BaseTransportConfig) -> None:
        self.config[transport.CONFIG_KEY].update(config)
