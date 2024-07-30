from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Type

from .base_model import BaseModel, ModelType

if TYPE_CHECKING:
    from .errors import BaseModappError


class BaseConverter(ABC):
    @abstractmethod
    def raw_to_model(self, raw: bytes, model_cls: Type[ModelType]) -> ModelType:
        raise NotImplementedError()

    @abstractmethod
    def model_to_raw(self, model: BaseModel) -> bytes:
        raise NotImplementedError()

    @abstractmethod
    def error_to_raw(self, error: BaseModappError) -> bytes:
        """Convert error object to raw data.

        Args:
            error (BaseModappError): error to convert

        Raises:
            NotImplementedError: converter doesn't support this error type

        Returns:
            bytes: raw data with error information
        """
        raise NotImplementedError()
