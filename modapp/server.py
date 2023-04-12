from __future__ import annotations
import asyncio
import platform
from typing import TYPE_CHECKING

from loguru import logger

from modapp.routing import APIRouter, RouteMeta

if TYPE_CHECKING:
    from typing import Callable, Dict, Optional, Set

    from modapp.base_transport import BaseTransport, BaseTransportConfig
    from modapp.types import DecoratedCallable
    from modapp.dependencies import DependencyOverrides


# uvloop doesn't support Windows yet
if platform.system() != "Windows":
    # uvloop is optional dependency
    try:
        import uvloop

        # install uvloop event loop to get better performance of event loop
        uvloop.install()
    except ImportError:
        ...


class Modapp:
    def __init__(
        self,
        transports: Set[BaseTransport],
        config: Optional[Dict[str, BaseTransportConfig]] = None,
        dependency_overrides: Optional[DependencyOverrides] = None,
    ) -> None:
        self.transports = transports
        self.config: Dict[str, BaseTransportConfig] = {}
        if config is not None:
            self.config = config
        self.dependency_overrides = dependency_overrides
        self.router = APIRouter(dependency_overrides=dependency_overrides)

    def run(self) -> None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        for transport in self.transports:
            loop.run_until_complete(transport.start(self.router.routes))

        try:
            logger.info("Server has started")
            loop.run_forever()
        except KeyboardInterrupt:
            logger.info("Server stop")

            for transport in self.transports:
                loop.run_until_complete(transport.stop())

    async def run_async(self) -> None:
        for transport in self.transports:
            await transport.start(self.router.routes)

        logger.info("Server has started")

    def stop(self) -> None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        for transport in self.transports:
            loop.run_until_complete(transport.stop())
        
        logger.info("Server stop")

    def endpoint(
        self, route_meta: RouteMeta
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            self.router.add_endpoint(route_meta, func)
            return func

        return decorator

    def include_router(self, router: APIRouter) -> None:
        for route in router.routes.values():
            self.router.add_route(route)

    def update_config(
        self, transport: BaseTransport, config: BaseTransportConfig
    ) -> None:
        self.config[transport.CONFIG_KEY].update(config)
