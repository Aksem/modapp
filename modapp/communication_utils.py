from asyncio import iscoroutine
from typing import Any, Dict

from loguru import logger
from pydantic import ValidationError

from .routing import Route
from .errors import ServerError
from .models import BaseModel


async def run_request_handler(route: Route, handler_arguments: Dict[str, Any]) -> BaseModel:
    try:
        if iscoroutine(route.handler):
            reply = await route.handler(**handler_arguments)
        else:
            reply = route.handler(**handler_arguments)
        return reply
    except ValidationError as error:
        # failed to validate reply
        logger.critical(f"Failed to validate reply: {error}")
        raise ServerError()
