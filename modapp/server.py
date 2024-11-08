from __future__ import annotations

import asyncio
import platform
from typing import TYPE_CHECKING, Any, Coroutine, Sequence

from loguru import logger

from modapp.routing import APIRouter, Cardinality, RouteMeta
from modapp.endpoints import keep_running as keep_running_endpoint_handler, health_check

if TYPE_CHECKING:
    from typing import Callable

    from modapp.base_transport import BaseTransport, BaseTransportConfig
    from modapp.dependencies import DependencyOverrides
    from modapp.types import DecoratedCallable


def run_in_better_loop(coroutine: Callable[..., Coroutine[Any, Any, Any]]) -> None:
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
                runner.run(coroutine())
        else:
            loop_lib.install()
            asyncio.run(coroutine())


class Modapp:
    def __init__(
        self,
        transports: Sequence[BaseTransport],
        config: dict[str, BaseTransportConfig] | None = None,
        dependency_overrides: DependencyOverrides | None = None,
        keep_running_endpoint: bool = False,
        healthcheck_endpoint: bool = False,
    ) -> None:
        self.transports = transports
        self.config: dict[str, BaseTransportConfig] = {}
        if config is not None:
            self.config = config
        self.dependency_overrides = dependency_overrides
        self.router = APIRouter(dependency_overrides=dependency_overrides)
        if keep_running_endpoint:
            self.router.add_endpoint(
                route_meta=RouteMeta(
                    path="/modapp.ModappService/KeepRunningUntilDisconnect",
                    cardinality=Cardinality.UNARY_STREAM,
                ),
                handler=keep_running_endpoint_handler,
            )
        if healthcheck_endpoint:
            self.router.add_endpoint(
                route_meta=RouteMeta(
                    path="/modapp.ModappService/GetHealthStatus",
                    cardinality=Cardinality.UNARY_UNARY,
                ),
                handler=health_check,
            )

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
        # run API is async, but stop is sync, because using asyncio in except and finally blocks
        # on app end (e.g. after getting SIGINT) is quite tricky.
        for transport in self.transports:
            transport.stop()
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
