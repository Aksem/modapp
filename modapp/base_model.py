
from dataclasses import dataclass
from typing import TypeVar, ClassVar


@dataclass
class BaseModel:
    __modapp_path__: ClassVar[str]

    model_config: ClassVar[dict[str, str]] = {}


ModelType = TypeVar("ModelType", bound=BaseModel)


__all__ = [
    'BaseModel',
    'ModelType'
]
