from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import platform
from typing import TYPE_CHECKING, Any, Coroutine, Type

from loguru import logger

from modapp.base_converter import BaseConverter
from modapp.routing import APIRouter, RouteMeta

if TYPE_CHECKING:
    from typing import Callable

    from modapp.base_transport import BaseTransport, BaseTransportConfig
    from modapp.dependencies import DependencyOverrides
    from modapp.types import DecoratedCallable


def run_coroutine(coroutine: Callable[..., Coroutine[Any, Any, Any]], *args, **kwargs) -> None:
    import sys

    # uvloop doesn't support Windows yet
    if platform.system() != "Windows":
        import uvloop

        loop_lib = uvloop
    else:
        import winloop  # type: ignore

        loop_lib = winloop

        if sys.version_info >= (3, 11):
            with asyncio.Runner(loop_factory=loop_lib.new_event_loop) as runner:
                runner.run(coroutine(*args, **kwargs))
        else:
            loop_lib.install()
            asyncio.run(coroutine(*args, **kwargs))


@dataclass
class CrossProcessConfig:
    converter_by_transport: dict[Type[BaseTransport], BaseConverter] = field(default_factory=dict)
    dependency_overrides: DependencyOverrides | None = None


class Modapp:
    def __init__(
        self,
        transports: set[BaseTransport],
        config: dict[str, BaseTransportConfig] | None = None,
        dependency_overrides: DependencyOverrides | None = None,
        cross_process_config_factory: Callable[[], CrossProcessConfig] | None = None
    ) -> None:
        self.transports = transports
        self.config: dict[str, BaseTransportConfig] = {}
        if config is not None:
            self.config = config
        self.dependency_overrides = dependency_overrides
        self.router = APIRouter(dependency_overrides=dependency_overrides)
        self.cross_process_config_factory = cross_process_config_factory
        
        for transport in self.transports:
            transport.cross_process_config_factory = cross_process_config_factory

    def run(self) -> None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(self.run_async())

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            self.stop()

    async def run_async(self) -> None:
        await asyncio.gather(
            *[transport.start(self.router.routes) for transport in self.transports]
        )
        logger.info("Server has started")

    def stop(self) -> None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(self.stop_async())

    async def stop_async(self) -> None:
        await asyncio.gather(*[transport.stop() for transport in self.transports])
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
