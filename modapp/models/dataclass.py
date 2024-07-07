from typing import Any, Self
from dataclasses import asdict

from typing_extensions import override

from modapp.errors import InvalidArgumentError
from modapp.base_model import BaseModel


class DataclassModel(BaseModel):
    @override
    @classmethod
    def validate_and_construct_from_dict(cls, model_dict: dict[str, Any]) -> Self:
        try:
            return cls(**model_dict)
        except Exception as error:  # TODO
            raise InvalidArgumentError(
                {}
                # errors_by_fields=# {str(error["loc"][0]): error["msg"] for error in error.errors()}
            )

    @override
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
