import inspect
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
            data_as_dict = _decamelize_model_dict(model_dict, cls)
        try:
            return cls(**data_as_dict)
        except Exception as error:  # TODO
            # TODO: field name should follow camelCase option
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
        elif isinstance(value, list):
            # TODO: support all iterables: set etc.
            list_result: list[Any] = []
            for idx, dict_item in enumerate(value):
                if isinstance(model_attr_value[idx], DataclassModel):
                    list_result.append(_camelize_model_dict(dict_item, model_attr_value[idx]))
                else:
                    list_result.append(dict_item)
            camelized_value = list_result
        elif isinstance(value, dict):
            # TODO: check whether user dicts are supported
            dict_result: dict[Any, Any] = {}
            for dict_key, dict_value in value.items():
                if isinstance(value, DataclassModel):
                    dict_result[dict_key] = _camelize_model_dict(dict_value, model_attr_value[key])
                else:
                    dict_result[dict_key] = dict_value
            camelized_value = dict_result
        else:
            camelized_value = value
        camelized_data_dict[humps.camelize(key)] = camelized_value
    return camelized_data_dict


def _decamelize_model_dict(
    data_dict: dict[str, Any], model_cls: Type[DataclassModel]
) -> dict[str, Any]:
    # NOTE: that data_dict is not validated yet, it can include wrong keys or some keys can be missing
    assert humps is not None
    decamelized_data_dict: dict[str, Any] = {}
    for key, value in data_dict.items():
        decamelized_key = humps.decamelize(key)
        # decamelize all keys and values that are also model instances
        try:
            model_attr_type = model_cls.__annotations__[decamelized_key]
        except KeyError:
            logger.trace(f"Skip key {decamelized_key} in data, because its type was not found in model")
            continue

        if inspect.isclass(model_attr_type) and issubclass(model_attr_type, DataclassModel):
            decamelized_value = _decamelize_model_dict(value, model_attr_type)
        else:
            decamelized_value = value
        decamelized_data_dict[decamelized_key] = decamelized_value
    return decamelized_data_dict
