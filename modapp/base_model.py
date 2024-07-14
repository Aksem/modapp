from __future__ import annotations
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Self, TypeVar, ClassVar


@dataclass
class BaseModel:
    __modapp_path__: ClassVar[str]

    __model_config__: ClassVar[dict[str, str]] = {}

    def __init__(self, *args, **kwargs) -> None:
        ...

    @classmethod
    @abstractmethod
    def validate_and_construct_from_dict(
        cls, model_dict: dict[str, Any]
    ) -> Self:
        raise NotImplementedError()

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError()


ModelType = TypeVar("ModelType", bound=BaseModel)


__all__ = [
    'BaseModel',
    'ModelType'
]
