from typing import AsyncIterator, Optional

from typing_extensions import override

from modapp.base_converter import BaseConverter
from modapp.base_transport import BaseTransport
from modapp.errors import ServerError
from modapp.routing import RoutesDict

from .inmemory_config import InMemoryTransportConfig


class InMemoryTransport(BaseTransport):
    CONFIG_KEY = "inmemory"

    def __init__(
        self, config: InMemoryTransportConfig, converter: Optional[BaseConverter] = None
    ):
        super().__init__(config, converter)
        self.routes: Optional[RoutesDict] = None

    @override
    async def start(self, routes: RoutesDict) -> None:
        self.routes = routes

    @override
    def stop(self) -> None:
        self.routes = None

    async def handle_request(
        self, route_path: str, request_data: bytes
    ) -> bytes | AsyncIterator[bytes]:
        if self.routes is None:
            raise Exception("Server need to be started first")  # TODO
        try:
            route = self.routes[route_path]
        except KeyError:
            raise ServerError()  # TODO
        # with concurrent.futures.ThreadPoolExecutor() as executor:
        meta: dict[str, str | int | bool] = {}  # TODO
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
