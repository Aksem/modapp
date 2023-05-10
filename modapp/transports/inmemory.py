import inspect
import concurrent.futures
from typing import AsyncIterator, Optional

from loguru import logger

from modapp.base_converter import BaseConverter
from modapp.errors import ServerError, BaseModappError
from modapp.base_transport import BaseTransport, BaseTransportConfig
from modapp.routing import RoutesDict


class InMemoryTransportConfig(BaseTransportConfig):
    ...


DEFAULT_CONFIG: InMemoryTransportConfig = {}


class InMemoryTransport(BaseTransport):
    CONFIG_KEY = "inmemory"

    def __init__(
        self, config: BaseTransportConfig, converter: Optional[BaseConverter] = None
    ):
        super().__init__(config, converter)
        self.routes: Optional[RoutesDict] = None

    async def start(self, routes: RoutesDict) -> None:
        self.routes = routes

    async def stop(self) -> None:
        self.routes = None

    async def handle_request(self, route_path: str, request_data: bytes) -> bytes | AsyncIterator[bytes]:
        if self.routes is None:
            raise Exception("Server need to be started first")  # TODO
        try:
            route = self.routes[route_path]
        except KeyError:
            raise ServerError()  # TODO
        # with concurrent.futures.ThreadPoolExecutor() as executor:
        meta = {}  # TODO
        data = await self.got_request(route=route, raw_data=request_data, meta=meta)
        return data
        # future = executor.submit(
        #     self.got_request, route, request_data, meta
        # )
        # try:
        #     data = future.result()
        #     assert isinstance(data, bytes) or inspect.isasyncgen(data)
        # except Exception as exc:
        #     if isinstance(exc, BaseModappError):
        #         raise exc
        #     logger.error(f"Error on handling request {exc}")
        #     raise ServerError()  # TODO
        # else:
        #     return data


__all__ = ["InMemoryTransport", "InMemoryTransportConfig"]
