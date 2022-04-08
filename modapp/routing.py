from __future__ import annotations
from typing import Callable, Optional, Dict, Any
from inspect import signature

from loguru import logger

from .types import DecoratedCallable


class BaseService:
    """This class describes base type of service class."""
    def __mapping__(self) -> Dict[str, Any]:
        ...


class Route:
    # TODO: more concrete type for handler
    def __init__(self, path: str, handler: Callable, router: APIRouter, request_type, reply_type, proto_request_type, proto_reply_type, proto_cardinality):
        self.path = path
        self.handler = handler
        self.router = router
        self.request_type = request_type
        self.reply_type = reply_type
        self.proto_request_type = proto_request_type
        self.proto_reply_type = proto_reply_type
        self.proto_cardinality = proto_cardinality


class APIRouter:
    def __init__(self, service_cls: Optional[type[BaseService]] = None):
        self.routes: Dict[str, Route] = {}
        self.service_cls = service_cls

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
            logger.warning(f'Route "{route_path}" has no service and cannot be registered')
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
        request_parameter_name = list(handler_signature.parameters.keys())[0]
        request_type = handler_signature.parameters[request_parameter_name].annotation

        # TODO: find better solution instead of workaround
        self.service_cls.__abstractmethods__ = frozenset()
        service = self.service_cls()
        generated_mapping = service.__mapping__()
        try:
            generated_handler = generated_mapping[route_path]
        except KeyError:
            logger.error(f'Generated handler for route "{route_path}" not found')
            return

        self.routes[route_path] = Route(route_path, handler, self, request_type, None, generated_handler.request_type, generated_handler.reply_type, generated_handler.cardinality)
    
    def add_route(self, route: Route):
        self.routes[route.path] = route
