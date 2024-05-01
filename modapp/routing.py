from __future__ import annotations

import types
from collections import namedtuple
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from enum import Enum, unique
from inspect import isasyncgenfunction, isgeneratorfunction, signature, iscoroutinefunction
from typing import TYPE_CHECKING, Coroutine, NamedTuple, ParamSpec, Callable

from loguru import logger
from typing_extensions import Protocol

from modapp.dependencies import Dependant, DependencyFunc, DependencyOverrides
from modapp.base_model import BaseModel

from .params import Depends, Meta

if TYPE_CHECKING:
    from typing import Any, List, Optional, Type

    from .types import DecoratedCallable


class BaseService(Protocol):
    """This class describes base type of service class."""

    def __mapping__(self) -> dict[str, Any]:
        ...


_Cardinality = namedtuple(
    "_Cardinality",
    "client_streaming, server_streaming",
)


@unique
class Cardinality(_Cardinality, Enum):
    UNARY_UNARY = _Cardinality(False, False)
    UNARY_STREAM = _Cardinality(False, True)
    STREAM_UNARY = _Cardinality(True, False)
    STREAM_STREAM = _Cardinality(True, True)


class RouteMeta(NamedTuple):
    path: str
    cardinality: Cardinality


RequestResponseType = BaseModel | AsyncIterator[BaseModel]
MetaType = dict[str, int | str | bool]
P = ParamSpec("P")
RouteHandlerCallable = (
    Callable[[RequestResponseType | Depends | Meta], RequestResponseType]
    | Coroutine[RequestResponseType, None, None]
)


class Route:
    def __init__(
        self,
        path: str,
        handler: RouteHandlerCallable,
        router: APIRouter,
        request_type: Type[BaseModel],
        reply_type: Type[BaseModel],
        proto_cardinality: Cardinality,
        handler_meta_kwargs: dict[str, Meta] | None = None,
        dependencies: dict[str, Depends] | None = None,
    ) -> None:
        self.path = path
        self.handler = handler
        self.router = router
        self.request_type = request_type
        self.reply_type = reply_type
        self.proto_cardinality = proto_cardinality

        self.handler_meta_kwargs: dict[str, Meta] = {}
        if handler_meta_kwargs:
            self.handler_meta_kwargs = handler_meta_kwargs
        self.dependant: Dependant | None = (
            Dependant.from_depends_list(handler, dependencies) if dependencies else None
        )

    async def get_request_handler(
        self, request: RequestResponseType, meta: MetaType, stack: AsyncExitStack
    ) -> Callable[..., Coroutine[Any, Any, RequestResponseType]]:
        handler_args: dict[str, Any] = {}
        try:
            handler_args.update(
                {
                    meta_key: meta[meta_key]
                    for meta_key in self.handler_meta_kwargs.keys()
                }
            )
        except KeyError as error:
            raise Exception(error)  # TODO: correct exception

        if self.dependant is not None and self.dependant.dependencies is not None:
            # TODO: solve concurrently
            def solve_dependency(
                dependency: DependencyFunc, stack: AsyncExitStack
            ) -> Any:
                if isgeneratorfunction(dependency):
                    cm = contextmanager(dependency)()  # TODO: dependency args
                    return stack.enter_context(cm)
                elif isasyncgenfunction(dependency):
                    cm = asynccontextmanager(dependency)()  # TODO: dependency args
                    return stack.enter_async_context(cm)
                else:
                    raise Exception()

            # TODO: recursive resolving with parameters support
            handler_args.update(
                {
                    str(dep.name): solve_dependency(dep.callable, stack)
                    for dep in self.dependant.dependencies
                }
            )

        async def request_handler():
            if iscoroutinefunction(self.handler):
                return await self.handler(request, **handler_args)
            else:
                return self.handler(request, **handler_args)
        return request_handler


RoutesDict = dict[str, Route]


class APIRouter:
    def __init__(
        self, dependency_overrides: Optional[DependencyOverrides] = None
    ) -> None:
        self._routes: RoutesDict = {}
        self.child_routers: List[APIRouter] = []
        self.dependency_overrides = dependency_overrides

    def endpoint(
        self, route_meta: RouteMeta
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            self.add_endpoint(route_meta, func)
            return func

        return decorator

    def add_endpoint(
        self, route_meta: RouteMeta, handler: RouteHandlerCallable
    ) -> None:
        # TODO: logs only on registering in main router
        if route_meta.path in self.routes:
            logger.warning(f'Route "{route_meta.path}" reregistered')
        else:
            logger.info(f'Route "{route_meta.path}" registered')

        handler_signature = signature(handler)
        meta_kwargs: dict[str, Meta] = {}
        dependencies: dict[str, Depends] = {}
        for parameter_name, parameter in handler_signature.parameters.items():
            if isinstance(parameter.default, Meta):
                meta_kwargs[parameter_name] = parameter.default
            elif isinstance(parameter.default, Depends):
                # if dependency is overwritten, use overwritten one, else default
                if (
                    self.dependency_overrides is not None
                    and parameter.default.dependency in self.dependency_overrides
                ):
                    dependencies[parameter.name] = Depends(
                        self.dependency_overrides[parameter.default.dependency]
                    )
                else:
                    dependencies[parameter.name] = parameter.default

        request_type = handler_signature.parameters["request"].annotation
        return_type = handler_signature.return_annotation
        if (
            isinstance(return_type, types.GenericAlias)
            and return_type.__origin__ == AsyncIterator
            and len(return_type.__args__) > 0
        ):
            return_type = return_type.__args__[0]

        self._routes[route_meta.path] = Route(
            route_meta.path,
            handler,
            self,
            request_type,
            return_type,
            route_meta.cardinality,
            handler_meta_kwargs=meta_kwargs,
            dependencies=dependencies if len(dependencies.keys()) > 0 else None,
        )
        handler.__modapp_route__ = self._routes[route_meta.path]

    def add_route(self, route: Route) -> None:
        self._routes[route.path] = route

    def include_router(self, router: APIRouter) -> None:
        self.child_routers.append(router)

    @property
    def routes(self) -> dict[str, Route]:
        all_routes = self._routes.copy()
        for router in self.child_routers:
            all_routes.update(router.routes)
        return all_routes
