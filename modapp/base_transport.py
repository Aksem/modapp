from __future__ import annotations

import asyncio
import traceback
from abc import ABC
from typing import (
    TYPE_CHECKING,
    Callable,
    Optional,
    TypedDict,
    Union,
    AsyncIterator,
)
from contextlib import AsyncExitStack

from loguru import logger

from modapp.base_converter import BaseConverter
from modapp.errors import InvalidArgumentError, NotFoundError, ServerError
from modapp.converter_utils import get_default_converter
from modapp.models import BaseModel
from modapp.routing import Route, Cardinality

if TYPE_CHECKING:
    from .routing import RoutesDict


class BaseTransportConfig(TypedDict):
    ...


class BaseTransport(ABC):
    # REQUIRED
    # TODO: Check automatically whether it is set
    CONFIG_KEY: str

    def __init__(
        self, config: BaseTransportConfig, converter: Optional[BaseConverter] = None
    ):
        self.config = config
        self.converter = converter if converter is not None else get_default_converter()

    async def start(self, routes: RoutesDict) -> None:
        raise NotImplementedError()

    async def stop(self) -> None:
        raise NotImplementedError()

    # TODO: AsyncIterator in raw_data type
    def got_request(
        self,
        route: Route,
        raw_data: bytes,
        meta: Dict[str, Union[str, int, bool]],
    ) -> Union[bytes, AsyncIterator[bytes]]:
        # request body
        try:
            request_data = self.converter.raw_to_model(raw_data, route.request_type)
        except InvalidArgumentError as error:
            logger.error(
                f"Failed to convert request data to model: '{str(raw_data)}' for route"
                f" '{route.path}'"
            )
            raise error

        # here or on initialization?
        # updating is needed if response type has submodels
        route.reply_type.update_forward_refs()

        # TODO: validate if there is validator?
        stack = AsyncExitStack()

        try:
            handler = route.get_request_handler(request_data, meta, stack)
            reply = handler()
            if route.proto_cardinality == Cardinality.UNARY_UNARY:
                # modapp validates request handlers, trust it
                assert isinstance(reply, BaseModel)
                proto_reply = self.converter.model_to_raw(reply)
                return proto_reply
            elif route.proto_cardinality == Cardinality.UNARY_STREAM:
                handler = route.get_request_handler(request_data, meta, stack)

                async def handle_request(
                    handler: Callable,
                    converter: BaseConverter,
                    route: Route,
                ) -> AsyncIterator[bytes]:
                    async for reply in handler():
                        proto_reply = converter.model_to_raw(reply)
                        yield proto_reply
                        logger.trace("Response stream message:")
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                return handle_request(handler, self.converter, route)
        except (NotFoundError, InvalidArgumentError, ServerError) as error:
            traceback.print_exc()
            raise error
        except BaseException as error:  # this should be in handler runner?
            logger.critical(f"Unhandled server error {error}")
            traceback.print_exc()
            server_error = ServerError("Internal server error")
            raise server_error
        finally:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            asyncio.run_coroutine_threadsafe(stack.aclose(), loop)


__all__ = ["BaseTransportConfig", "BaseTransport"]
