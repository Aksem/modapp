from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Type

if TYPE_CHECKING:
    from .routing import Route
    from .models import BaseModel
    from .errors import BaseModappError


class BaseConverter(ABC):
    @abstractmethod
    def raw_to_model(self, raw: bytes, model_cls: Type[BaseModel]) -> BaseModel:
        raise NotImplementedError()

    @abstractmethod
    def model_to_raw(self, model: BaseModel) -> bytes:
        raise NotImplementedError()

    @abstractmethod
    def error_to_raw(self, error: BaseModappError, route: Optional[Route]) -> bytes:
        """Convert error object to raw data.

        Route is optional, because it's not always available, e.g. NotFoundError if requested
        endpoint was not found.

        Args:
            error (BaseModappError): error to convert
            route (Optional[Route]): route on which error occurred

        Raises:
            NotImplementedError: converter doesn't support this error type

        Returns:
            bytes: raw data with error information
        """
        raise NotImplementedError()
