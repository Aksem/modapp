
from dataclasses import dataclass
from typing import TypeVar


@dataclass
class BaseModel:
    __modapp_path__: str = ""

    model_config = {}


ModelType = TypeVar("ModelType", bound=BaseModel)


__all__ = [
    'BaseModel',
    'ModelType'
]
