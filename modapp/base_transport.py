from __future__ import annotations

import asyncio
import traceback
from abc import ABC
from typing import TYPE_CHECKING, Optional, TypedDict, Dict, Union, Any, AsyncIterator
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
    def got_request(self, route: Route, raw_data: bytes, meta: Dict[str, Union[str, int, bool]]) -> Union[BaseModel, AsyncIterator[BaseModel]]:
        # request body
        try:
            request_data = self.converter.raw_to_model(raw_data, route)
        except InvalidArgumentError as error:
            logger.error(
                f"Failed to convert request data to model: '{str(raw_data)}' for route"
                f" '{route.path}'"
            )
            raise error

        # TODO: validate if there is validator?
        stack = AsyncExitStack()

        try:
            handler = route.get_request_handler(request_data, meta, stack)
            reply = handler()
            if route.proto_cardinality == Cardinality.UNARY_UNARY:
                # modapp validates request handlers, trust it
                assert isinstance(reply, BaseModel)
                proto_reply = self.converter.model_to_raw(reply, route)
                return proto_reply
            elif route.proto_cardinality == Cardinality.UNARY_STREAM:
                request_id = randint(0, 10000000)

                async def handle_request(
                    request_id: int,
                    handler_arguments: Dict[str, Any],
                    converter: BaseConverter,
                    route: Route,
                ):
                    try:
                        async for reply in route.handler(
                            **handler_arguments
                        ):  # TODO: handle validation error
                            proto_reply = converter.model_to_raw(reply, route)
                            yield proto_reply
                            logger.trace(
                                "Response stream message:"
                                f" {method_name}_{request_id}_reply"
                            )
                    except Exception as error:
                        logger.error(error)
                        traceback.print_exc()
                        # send error?
                        raise ServerError(error)  # TODO: error only in debug?

                loop = asyncio.get_event_loop()
                asyncio.run_coroutine_threadsafe(
                    handle_request(
                        request_id, handler_arguments, self.converter, route
                    ),
                    loop,
                )
                return request_id
        except (NotFoundError, InvalidArgumentError, ServerError) as error:
            traceback.print_exc()
            raise error
        except BaseException as error:  # this should be in handler runner?
            logger.critical(f"Unhandled server error {error}")
            traceback.print_exc()
            server_error = ServerError("Internal server error")
            raise server_error
        finally:
            loop = asyncio.get_event_loop()
            asyncio.run_coroutine_threadsafe(stack.aclose(), loop)


__all__ = ["BaseTransportConfig", "BaseTransport"]
