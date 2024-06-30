from typing import Any, Type
from dataclasses import asdict

from typing_extensions import override

from modapp.base_validator import BaseValidator
from modapp.errors import InvalidArgumentError
from modapp.base_model import BaseModel, ModelType


class DataclassValidator(BaseValidator):

    @override
    def validate_and_construct_from_dict(
        self, model_dict: dict[str, Any], model_cls: Type[ModelType]
    ) -> ModelType:
        try:
            return model_cls(**model_dict)
        except Exception as error:  # TODO
            raise InvalidArgumentError(
                {}
                # errors_by_fields=# {str(error["loc"][0]): error["msg"] for error in error.errors()}
            )

    @override
    def model_to_dict(self, model: BaseModel) -> dict[str, Any]:
        return asdict(model)
