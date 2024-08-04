from dataclasses import asdict
from typing import Any, Self

from typing_extensions import override
try:
    import humps
except ImportError:
    humps = None

from modapp.base_model import BaseModel
from modapp.errors import InvalidArgumentError


class DataclassModel(BaseModel):
    @override
    @classmethod
    def validate_and_construct_from_dict(cls, model_dict: dict[str, Any]) -> Self:
        data_as_dict = model_dict
        if cls.__model_config__.get("camelCase", False):
            if humps is None:
                raise Exception("Extra 'case_change' is required to use 'camelCase' model option")
            data_as_dict = humps.decamelize(data_as_dict)
        try:
            return cls(**data_as_dict)
        except Exception as error:  # TODO
            raise InvalidArgumentError(
                {}
                # errors_by_fields=# {str(error["loc"][0]): error["msg"] for error in error.errors()}
            )

    @override
    def to_dict(self) -> dict[str, Any]:
        data_as_dict = asdict(self)
        if self.__model_config__.get("camelCase", False):
            if humps is None:
                raise Exception("Extra 'case_change' is required to use 'camelCase' model option")
            data_as_dict = humps.camelize(data_as_dict)
        return data_as_dict
