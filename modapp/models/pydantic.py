import inspect
import sys
from typing import Any, Type

if sys.version_info >= (3, 11, 0):
    from typing import Self
else:
    from typing_extensions import Self

from loguru import logger
from pydantic import BaseModel as PydanticBaseModel, AliasGenerator, ConfigDict
from pydantic import ValidationError, field_validator
from pydantic.networks import (
    AmqpDsn,
    AnyHttpUrl,
    AnyUrl,
    CockroachDsn,
    EmailStr,
    FileUrl,
    HttpUrl,
    IPvAnyAddress,
    IPvAnyInterface,
    IPvAnyNetwork,
    KafkaDsn,
    MongoDsn,
    NameEmail,
    PostgresDsn,
    RedisDsn,
)
from pydantic.types import (
    UUID1,
    UUID3,
    UUID4,
    UUID5,
    ByteSize,
    DirectoryPath,
    FilePath,
    FutureDate,
    Json,
    NegativeFloat,
    NegativeInt,
    NonNegativeFloat,
    NonNegativeInt,
    NonPositiveFloat,
    NonPositiveInt,
    PastDate,
    PositiveFloat,
    PositiveInt,
    SecretBytes,
    SecretStr,
    StrictBool,
    StrictBytes,
    StrictFloat,
    StrictInt,
    StrictStr,
    conbytes,
    condecimal,
    confloat,
    confrozenset,
    conint,
    conlist,
    conset,
    constr,
)
from pydantic.alias_generators import to_camel, to_snake, to_pascal
from typing_extensions import override

try:
    import humps
except ImportError:
    humps = None

from modapp.base_model import BaseModel
from modapp.errors import InvalidArgumentError


class PydanticModel(PydanticBaseModel, BaseModel):
    # 1. Pydantic `model_config` cannot be changed dynamically (e.g. add alias_generator), so
    # currently it is required to add it to base model manually.
    #
    # Snippet for camelCase option:
    # model_config = ConfigDict(alias_generator=AliasGenerator(
    #                validation_alias=to_camel,
    #                serialization_alias=to_camel,
    #            ))
    # __dump_options__ = {'by_alias': True}
    #
    # in future it should be in generated model?
    # 1.1 Note, that both alias generators are to_camel, because pydantic converts key in model, not
    #     in the input data.
    # 1.2 Previous note means also that if alias_generator is set, only aliased data are supported
    #     as input data.
    __dump_options__: dict[str, Any] = {}

    @override
    @classmethod
    def validate_and_construct_from_dict(cls, model_dict: dict[str, Any]) -> Self:
        # we cannot use alias generator from pydantic, see #1 above.
        data_as_dict = model_dict
        if cls.__model_config__.get("camelCase", False):
            if humps is None:
                raise Exception(
                    "Extra 'case_change' is required to use 'camelCase' model option"
                )
            data_as_dict = _decamelize_model_dict(model_dict, cls)

        try:
            return cls(**model_dict)
        except ValidationError as error:
            raise InvalidArgumentError(
                # TODO: field name should follow camelCase option
                {str(error["loc"][0]): error["msg"] for error in error.errors()}
            )

    @override
    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(**self.__dump_options__)


def _decamelize_model_dict(
    data_dict: dict[str, Any], model_cls: Type[PydanticModel]
) -> dict[str, Any]:
    # NOTE: that data_dict is not validated yet, it can include wrong keys or some keys can be missing
    assert humps is not None
    decamelized_data_dict: dict[str, Any] = {}
    for key, value in data_dict.items():
        # decamelize all keys and values that are also model instances
        decamelized_key = humps.decamelize(key)
        try:
            model_attr_type = model_cls.model_fields[decamelized_key].annotation
        except KeyError:
            logger.trace(
                f"Skip key {key} in data, because its type was not found in model"
            )
            continue

        if (
            model_attr_type is not None
            and inspect.isclass(model_attr_type)
            and issubclass(model_attr_type, PydanticModel)
        ):
            decamelized_value = _decamelize_model_dict(value, model_attr_type)
        else:
            decamelized_value = value
        decamelized_data_dict[decamelized_key] = decamelized_value
    return decamelized_data_dict


__all__ = [
    "BaseModel",
    "field_validator",
    "ValidationError",
    # pydantic types
    "StrictStr",
    "conbytes",
    "conlist",
    "conset",
    "confrozenset",
    "constr",
    "conint",
    "PositiveInt",
    "NegativeInt",
    "NonNegativeInt",
    "NonPositiveInt",
    "confloat",
    "PositiveFloat",
    "NegativeFloat",
    "NonNegativeFloat",
    "NonPositiveFloat",
    "condecimal",
    "UUID1",
    "UUID3",
    "UUID4",
    "UUID5",
    "FilePath",
    "DirectoryPath",
    "Json",
    "SecretStr",
    "SecretBytes",
    "StrictBool",
    "StrictBytes",
    "StrictInt",
    "StrictFloat",
    "ByteSize",
    "PastDate",
    "FutureDate",
    # networks
    "AnyUrl",
    "AnyHttpUrl",
    "FileUrl",
    "HttpUrl",
    "EmailStr",
    "NameEmail",
    "IPvAnyAddress",
    "IPvAnyInterface",
    "IPvAnyNetwork",
    "PostgresDsn",
    "CockroachDsn",
    "AmqpDsn",
    "RedisDsn",
    "MongoDsn",
    "KafkaDsn",
    "ConfigDict",
    "to_camel",
    "to_snake",
    "to_pascal",
    "AliasGenerator",
]
