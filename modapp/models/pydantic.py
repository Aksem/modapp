import sys
from typing import Any

if sys.version_info >= (3, 11, 0):
    from typing import Self
else:
    from typing_extensions import Self

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
from pydantic.alias_generators import to_camel, to_snake
from typing_extensions import override

from modapp.base_model import BaseModel
from modapp.errors import InvalidArgumentError


class PydanticModel(PydanticBaseModel, BaseModel):
    # pydantic `model_config` cannot be changed dynamically (e.g. add alias_generator), so
    # currently it is required to add it to base model manually.
    #
    # Snippet for camelCase option:
    # model_config = ConfigDict(alias_generator=AliasGenerator(
    #                validation_alias=to_snake,
    #                serialization_alias=to_camel,
    #            ))
    # __dump_options__ = {'by_alias': True}
    #
    # in future it should be in generated model?
    __dump_options__: dict[str, Any] = {}

    @override
    @classmethod
    def validate_and_construct_from_dict(cls, model_dict: dict[str, Any]) -> Self:
        # if cls.__model_config__.get("camelCase", False):
        #     if cls.model_config.get("alias_generator", None) is None:
        #         cls.model_config["alias_generator"] = AliasGenerator(
        #             validation_alias=to_camel,
        #             serialization_alias=to_camel,
        #         )
        #         cls.__dump_options__['by_alias'] = True

        try:
            return cls(**model_dict)
        except ValidationError as error:
            raise InvalidArgumentError(
                {str(error["loc"][0]): error["msg"] for error in error.errors()}
            )

    @override
    def to_dict(self) -> dict[str, Any]:
        # if self.__model_config__.get("camelCase", False):
        #     if self.model_config.get("alias_generator", None) is None:
        #         self.model_config["alias_generator"] = AliasGenerator(
        #             validation_alias=to_camel,
        #             serialization_alias=to_camel,
        #         )
        #         self.__dump_options__['by_alias'] = True

        # print(self.__dump_options__, self.model_config['alias_generator'])
        return self.model_dump(**self.__dump_options__)


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
    "AliasGenerator"
]
