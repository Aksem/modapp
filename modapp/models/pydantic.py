from typing import Any, Self

from pydantic import ValidationError, BaseModel as PydanticBaseModel
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
]
