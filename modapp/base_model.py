from __future__ import annotations

import sys
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar, TypeVar

if sys.version_info >= (3, 11, 0):
    from typing import Self
else:
    from typing_extensions import Self


@dataclass
class BaseModel:
    __modapp_path__: ClassVar[str]

    __model_config__: ClassVar[dict[str, str | bool | int | float]] = {"camelCase": False}

    def __init__(self, *args: tuple[Any], **kwargs: dict[str, Any]) -> None: ...

    @classmethod
    @abstractmethod
    def validate_and_construct_from_dict(cls, model_dict: dict[str, Any]) -> Self:
        raise NotImplementedError()

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError()


ModelType = TypeVar("ModelType", bound=BaseModel)


__all__ = ["BaseModel", "ModelType"]
