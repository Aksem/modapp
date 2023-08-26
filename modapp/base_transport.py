from __future__ import annotations

import traceback
from abc import ABC
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, AsyncIterator, Callable, Optional, TypedDict, Union

from loguru import logger

from modapp.base_converter import BaseConverter
from modapp.converter_utils import get_default_converter
from modapp.errors import InvalidArgumentError, NotFoundError, ServerError
from modapp.models import BaseModel
from modapp.routing import Cardinality, Route
from modapp.types import Metadata

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
    async def got_request(
        self,
        route: Route,
        raw_data: bytes,
        meta: Metadata,
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

        logger.debug(f"Request to {route.path}: {request_data}")
        # here or on initialization?
        # updating is needed if response type has submodels
        route.reply_type.update_forward_refs()

        # TODO: validate if there is validator?
        stack = AsyncExitStack()

        try:
            handler = route.get_request_handler(request_data, meta, stack)
            if route.proto_cardinality == Cardinality.UNARY_UNARY:
                reply = handler()
                # modapp validates request handlers, trust it
                assert isinstance(reply, BaseModel)
                proto_reply = self.converter.model_to_raw(reply)
                logger.debug(f"Response on {route.path}: {reply}")
                return proto_reply
            elif route.proto_cardinality == Cardinality.UNARY_STREAM:

                async def handle_request(
                    handler: Callable[..., AsyncIterator[BaseModel]],
                    converter: BaseConverter,
                    route: Route,
                ) -> AsyncIterator[bytes]:
                    response_iterator = handler()
                    logger.debug(f"Response stream on {route.path} ready")
                    assert isinstance(
                        response_iterator, AsyncIterator
                    ), "Reply stream expected to be async iterator"
                    async for reply in response_iterator:
                        proto_reply = converter.model_to_raw(reply)
                        yield proto_reply
                        logger.trace(
                            f"Response stream message on {route.path}: {reply}"
                        )
                    logger.debug(f"Response stream on {route.path} finished")

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
            # logger.debug("Close request stack")
            await stack.aclose()

        raise Exception()


__all__ = ["BaseTransportConfig", "BaseTransport"]
