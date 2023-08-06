from abc import ABC
from typing import Any, Type

from modapp.models import BaseModel, ModelType


class BaseValidator(ABC):
    def validate_and_construct_from_dict(
        self, model_dict: dict[str, Any], model_cls: Type[ModelType]
    ) -> ModelType:
        raise NotImplementedError()

    def model_to_dict(self, model: BaseModel) -> dict[str, Any]:
        raise NotImplementedError()
