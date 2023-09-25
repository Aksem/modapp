from asyncio import iscoroutine
from typing import Any, Dict

from loguru import logger
from pydantic import ValidationError

from .errors import ServerError
from .models import BaseModel
from .routing import Route


async def run_request_handler(
    route: Route, handler_arguments: Dict[str, Any]
) -> BaseModel:
    try:
        if iscoroutine(route.handler):
            # assert isinstance(route.handler, Coroutine)
            reply = await route.handler(
                handler_arguments["request"], **handler_arguments
            )
        else:
            # assert isinstance(route.handler, Callable[..., Any])
            reply = route.handler(handler_arguments["request"], **handler_arguments)
        return reply
    except ValidationError as error:
        # failed to validate reply
        logger.critical(f"Failed to validate reply: {error}")
        raise ServerError()
