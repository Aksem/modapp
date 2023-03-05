import concurrent.futures
from typing import Optional

from loguru import logger

from modapp.base_converter import BaseConverter
from modapp.errors import ServerError
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

    async def handle_request(self, route_path: str, request_data: bytes):
        if self.routes is None:
            raise Exception("Server need to be started first")  # TODO
        try:
            route = self.routes[route_path]
        except KeyError:
            raise ServerError()  # TODO
        with concurrent.futures.ThreadPoolExecutor() as executor:
            meta = {}  # TODO
            future = executor.submit(
                self.got_request, route, request_data, meta, convert_to_raw=False
            )
            try:
                data = future.result()
            except Exception as exc:
                logger.error(f"Error on handling request {exc}")
            else:
                return data


__all__ = ["InMemoryTransport", "InMemoryTransportConfig"]
