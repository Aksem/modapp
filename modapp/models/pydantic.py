from typing import Any, Self

from pydantic import ValidationError, BaseModel as PydanticBaseModel
from typing_extensions import override

from modapp.errors import InvalidArgumentError
from modapp.base_model import BaseModel


class PydanticModel(BaseModel, PydanticBaseModel):
    dump_options: dict[str, Any] = {}

    @override
    @classmethod
    def validate_and_construct_from_dict(
        cls, model_dict: dict[str, Any]
    ) -> Self:
        try:
            return cls(**model_dict)
        except ValidationError as error:
            raise InvalidArgumentError(
                {str(error["loc"][0]): error["msg"] for error in error.errors()}
            )

    @override
    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(**self.dump_options)
