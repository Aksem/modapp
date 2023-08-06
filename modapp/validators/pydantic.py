from typing import Any, Type

from pydantic import ValidationError

from modapp.base_validator import BaseValidator
from modapp.errors import InvalidArgumentError
from modapp.models import BaseModel, ModelType


class PydanticValidator(BaseValidator):
    def validate_and_construct_from_dict(
        self, model_dict: dict[str, Any], model_cls: Type[ModelType]
    ) -> ModelType:
        try:
            return model_cls(**model_dict)
        except ValidationError as error:
            raise InvalidArgumentError(
                {str(error["loc"][0]): error["msg"] for error in error.errors()}
            )

    def model_to_dict(self, model: BaseModel) -> dict[str, Any]:
        return model.model_dump()  # by_alias=True
