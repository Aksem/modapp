from __future__ import annotations

import types
from collections import namedtuple
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, contextmanager
from enum import Enum, unique
from inspect import signature, isgeneratorfunction
from typing import TYPE_CHECKING, Union, Dict, NamedTuple

from loguru import logger
from typing_extensions import Protocol

from modapp.dependencies import Dependant, DependencyOverrides
from modapp.models import to_camel, BaseModel

from .params import Meta, Depends

if TYPE_CHECKING:
    from typing import Any, Callable, List, Optional, Type

    from .types import DecoratedCallable


class BaseService(Protocol):
    """This class describes base type of service class."""

    def __mapping__(self) -> Dict[str, Any]:
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


RequestResponseType = Union[BaseModel, AsyncIterator[BaseModel]]
MetaType = Dict[str, Union[int, str, bool]]


class Route:
    # TODO: more concrete type for handler
    def __init__(
        self,
        path: str,
        handler: Callable,
        router: APIRouter,
        request_type: Type[BaseModel],
        reply_type: Type[BaseModel],
        proto_cardinality,
        handler_meta_kwargs: Optional[Dict[str, Meta]] = None,
        dependencies: Optional[Dict[str, Depends]] = None,
    ) -> None:
        self.path = path
        self.handler = handler
        self.router = router
        self.request_type = request_type
        self.reply_type = reply_type
        self.proto_cardinality = proto_cardinality

        self.handler_meta_kwargs: Dict[str, Meta] = {}
        if handler_meta_kwargs:
            self.handler_meta_kwargs = handler_meta_kwargs
        self.dependant: Optional[Dependant] = (
            Dependant.from_depends_list(handler, dependencies) if dependencies else None
        )

    def get_request_handler(
        self, request: RequestResponseType, meta: MetaType, stack: AsyncExitStack
    ) -> Callable[[], RequestResponseType]:
        handler_args = dict(request=request)
        try:
            handler_args.update(
                {
                    meta_key: meta[to_camel(meta_key)]
                    for meta_key in list(
                        name for name in self.handler_meta_kwargs.keys()
                    )
                }
            )
        except KeyError as error:
            raise Exception(error)  # TODO: correct exception

        if self.dependant is not None and self.dependant.dependencies is not None:
            # TODO: solve concurrently
            def solve_dependency(dependency: Callable, stack: AsyncExitStack):
                if isgeneratorfunction(dependency):
                    cm = contextmanager(dependency)()  # TODO: dependency args
                    return stack.enter_context(cm)

            # TODO: recursive resolving with parameters support
            handler_args.update(
                {
                    dep.name: solve_dependency(dep.callable, stack)
                    for dep in self.dependant.dependencies
                }
            )

        return lambda: self.handler(**handler_args)


RoutesDict = Dict[str, Route]


class APIRouter:
    def __init__(
        self, dependency_overrides: Optional[DependencyOverrides] = None
    ) -> None:
        self._routes: Dict[str, Route] = {}
        self.child_routers: List[APIRouter] = []
        self.dependency_overrides = dependency_overrides

    def endpoint(
        self, route_meta: RouteMeta
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            self.add_endpoint(route_meta, func)
            return func

        return decorator

    def add_endpoint(self, route_meta: RouteMeta, handler: Callable) -> None:
        # TODO: logs only on registering in main router
        if route_meta.path in self.routes:
            logger.warning(f'Route "{route_meta.path}" reregistered')
        else:
            logger.info(f'Route "{route_meta.path}" registered')

        handler_signature = signature(handler)
        meta_kwargs: Dict[str, Meta] = {}
        dependencies: Dict[str, Depends] = {}
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

    def add_route(self, route: Route) -> None:
        self._routes[route.path] = route

    def include_router(self, router: APIRouter) -> None:
        self.child_routers.append(router)

    @property
    def routes(self) -> Dict[str, Route]:
        all_routes = self._routes.copy()
        for router in self.child_routers:
            all_routes.update(router.routes)
        return all_routes
