from __future__ import annotations
from functools import cached_property
import typing
from collections.abc import AsyncIterator
from typing import Callable, List, Optional, Dict, Any
from inspect import signature
from typing_extensions import Protocol
# re-export
from grpclib.const import Cardinality

from loguru import logger

from .params import Meta
from .types import DecoratedCallable


class BaseService(Protocol):
    """This class describes base type of service class."""

    def __mapping__(self) -> Dict[str, Any]:
        ...


class Route:
    # TODO: more concrete type for handler
    def __init__(
        self,
        path: str,
        handler: Callable,
        router: APIRouter,
        request_type,
        reply_type,
        proto_request_type,
        proto_reply_type,
        proto_cardinality,
        handler_meta_kwargs: Optional[Dict[str, Meta]] = None
    ):
        self.path = path
        self.handler = handler
        self.router = router
        self.request_type = request_type
        self.reply_type = reply_type
        self.proto_request_type = proto_request_type
        self.proto_reply_type = proto_reply_type
        self.proto_cardinality = proto_cardinality
        
        self.handler_meta_kwargs: Dict[str, Meta] = {}
        if handler_meta_kwargs:
            self.handler_meta_kwargs = handler_meta_kwargs
    
    @cached_property
    def handler_meta_keys(self) -> List[str]:
        return [name for name in self.handler_meta_kwargs.keys()]


class APIRouter:
    def __init__(self, service_cls: Optional[type[BaseService]] = None):
        self._routes: Dict[str, Route] = {}
        self.service_cls = service_cls
        self.child_routers: List[APIRouter] = []

    def endpoint(self, route_path) -> Callable[[DecoratedCallable], DecoratedCallable]:
        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            self.add_endpoint(route_path, func)
            return func

        return decorator

    def add_endpoint(self, route_path: str, handler: Callable) -> None:
        # TODO: logs only on registering in main router
        if route_path in self.routes:
            logger.warning(f'Route "{route_path}" reregistered')
        else:
            logger.info(f'Route "{route_path}" registered')

        if self.service_cls is None:
            logger.warning(
                f'Route "{route_path}" has no service and cannot be registered'
            )
            return

        # TODO: find better solution instead of workaround
        self.service_cls.__abstractmethods__ = frozenset()
        service = self.service_cls()
        generated_mapping = service.__mapping__()
        try:
            generated_handler = generated_mapping[route_path]
        except KeyError:
            logger.error(f'Generated handler for route "{route_path}" not found')
            return

        handler_signature = signature(handler)
        meta_kwargs: Dict[str, Meta] = {}
        for (parameter_name, parameter) in handler_signature.parameters.items():
            if isinstance(parameter.default, Meta):
                meta_kwargs[parameter_name] = parameter.default

        request_type = handler_signature.parameters['request'].annotation
        return_type = handler_signature.return_annotation
        if isinstance(return_type, typing._GenericAlias) and return_type.__origin__ == AsyncIterator and len(return_type.__args__) > 0:
            return_type = return_type.__args__[0]

        # TODO: find better solution instead of workaround
        self.service_cls.__abstractmethods__ = frozenset()
        service = self.service_cls()
        generated_mapping = service.__mapping__()
        try:
            generated_handler = generated_mapping[route_path]
        except KeyError:
            logger.error(f'Generated handler for route "{route_path}" not found')
            return

        self._routes[route_path] = Route(
            route_path,
            handler,
            self,
            request_type,
            return_type,
            generated_handler.request_type,
            generated_handler.reply_type,
            generated_handler.cardinality,
            handler_meta_kwargs=meta_kwargs
        )

    def add_route(self, route: Route):
        self._routes[route.path] = route

    def include_router(self, router: APIRouter) -> None:
        self.child_routers.append(router)

    @property
    def routes(self) -> Dict[str, Route]:
        all_routes = self._routes.copy()
        for router in self.child_routers:
            all_routes.update(router.routes)
        return all_routes
