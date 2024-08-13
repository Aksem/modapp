from dataclasses import asdict
from typing import Any, Self, Type

from loguru import logger
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
                raise Exception(
                    "Extra 'case_change' is required to use 'camelCase' model option"
                )
            # TODO: we cannot decamelize / camelize the whole object, because data inside of model fields can also includes dicts, that should stay unchanged
            data_as_dict = _decamelize_model_dict(model_dict, cls)
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
                raise Exception(
                    "Extra 'case_change' is required to use 'camelCase' model option"
                )
            data_as_dict = _camelize_model_dict(data_as_dict, self)
        return data_as_dict


# TODO: handle containers like list, dict etc correctly

def _camelize_model_dict(
    data_dict: dict[str, Any], model_instance: DataclassModel
) -> dict[str, Any]:
    assert humps is not None
    camelized_data_dict: dict[str, Any] = {}
    for key, value in data_dict.items():
        # camelize all keys and values that are also model instances
        model_attr_value = getattr(model_instance, key)
        if isinstance(model_attr_value, DataclassModel):
            camelized_value = _camelize_model_dict(value, model_attr_value)
        else:
            camelized_value = value
        camelized_data_dict[humps.camelize(key)] = camelized_value
    return camelized_data_dict


def _decamelize_model_dict(
    data_dict: dict[str, Any], model_cls: Type[DataclassModel]
) -> dict[str, Any]:
    # NOTE: that data_dict is not validated yet, it can include wrong keys or some keys can be missing
    decamelized_data_dict: dict[str, Any] = {}
    for key, value in data_dict.items():
        # decamelize all keys and values that are also model instances
        try:
            model_attr_type = model_cls.__annotations__[key]
        except KeyError:
            logger.trace(f"Skip key {key} in data, because its type was not found in model")
            continue

        if issubclass(model_attr_type, DataclassModel):
            decamelized_value = _decamelize_model_dict(value, model_attr_type)
        else:
            decamelized_value = value
        decamelized_data_dict[humps.decamelize(key)] = decamelized_value
    return decamelized_data_dict
