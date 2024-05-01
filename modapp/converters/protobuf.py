from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Type, cast

import google.protobuf.descriptor as protobuf_descriptor
from google._upb._message import MessageMapContainer, ScalarMapContainer  # type: ignore
from google.protobuf import message as protobuf_message
from google.protobuf.timestamp_pb2 import Timestamp
from google.rpc import status_pb2  # type: ignore
from google.rpc.error_details_pb2 import BadRequest  # type: ignore
from loguru import logger
from typing_extensions import override

from modapp.base_converter import BaseConverter
from modapp.base_validator import BaseValidator
from modapp.errors import InvalidArgumentError, NotFoundError, ServerError, Status
from modapp.base_model import BaseModel, ModelType

if TYPE_CHECKING:
    from modapp.errors import BaseModappError


PRIMITIVE_TYPE_PROTO_TO_PY_MAP = {
    protobuf_descriptor.FieldDescriptor.TYPE_DOUBLE: float,
    protobuf_descriptor.FieldDescriptor.TYPE_FLOAT: float,
    protobuf_descriptor.FieldDescriptor.TYPE_INT64: int,
    protobuf_descriptor.FieldDescriptor.TYPE_UINT64: int,
    protobuf_descriptor.FieldDescriptor.TYPE_INT32: int,
    protobuf_descriptor.FieldDescriptor.TYPE_FIXED64: int,
    protobuf_descriptor.FieldDescriptor.TYPE_FIXED32: int,
    protobuf_descriptor.FieldDescriptor.TYPE_BOOL: bool,
    protobuf_descriptor.FieldDescriptor.TYPE_STRING: str,
    # TYPE_GROUP          = 10
    # TYPE_MESSAGE        = 11
    protobuf_descriptor.FieldDescriptor.TYPE_BYTES: bytes,
    protobuf_descriptor.FieldDescriptor.TYPE_UINT32: int,
    # TODO
    # protobuf_descriptor.FieldDescriptor.TYPE_ENUM:
    protobuf_descriptor.FieldDescriptor.TYPE_SFIXED32: int,
    protobuf_descriptor.FieldDescriptor.TYPE_SFIXED64: int,
    protobuf_descriptor.FieldDescriptor.TYPE_SINT32: int,
    protobuf_descriptor.FieldDescriptor.TYPE_SINT64: int,
}


def model_field_type_matches_proto_field(
    dict_field_value: Any,
    model_field_value: Any,
    proto_field: protobuf_descriptor.FieldDescriptor,
) -> bool:
    if proto_field.type == protobuf_descriptor.FieldDescriptor.TYPE_MESSAGE:
        return cast(
            bool,
            proto_field.message_type.full_name == model_field_value.__modapp_path__,
        )
    # TODO: what if few proto type map to the same python type? like oneof { int32, int64 }
    return isinstance(
        dict_field_value, PRIMITIVE_TYPE_PROTO_TO_PY_MAP[proto_field.type]
    )


class ProtobufConverter(BaseConverter):
    def __init__(
        self,
        protos: dict[str, Type[protobuf_message.Message]],
        validator: BaseValidator,
    ) -> None:
        super().__init__()
        self.protos = protos
        self.validator = validator
        # self.resolved_protos: dict[str, Type[protobuf_message.Message]] = {}

    @override
    def raw_to_model(self, raw: bytes, model_cls: Type[ModelType]) -> ModelType:
        try:
            proto_cls = self.protos[model_cls.__modapp_path__]
        except KeyError:
            raise ServerError(f"Proto for {model_cls} not found")
            # else:
            #     self.resolved_protos[model_cls.__modapp_path__] = proto_request_type

        proto_instance = proto_cls.FromString(raw)
        model_dict = self.__proto_obj_to_dict(proto_instance)
        return self.validator.validate_and_construct_from_dict(
            model_dict=model_dict, model_cls=model_cls
        )

    @override
    def model_to_raw(self, model: BaseModel) -> bytes:
        model_dict = self.validator.model_to_dict(model=model)
        proto_obj = self.__dict_to_proto_obj(
            model_dict=model_dict,
            model_obj=model,
        )
        return proto_obj.SerializeToString()

    @override
    def error_to_raw(self, error: BaseModappError) -> bytes:
        if isinstance(error, InvalidArgumentError):
            return self.__invalid_argument_to_raw(error)
        elif isinstance(error, NotFoundError):
            return self.__not_found_to_raw(error)
        elif isinstance(error, ServerError):
            return self.__server_error_to_raw(error)
        raise NotImplementedError()

    def __invalid_argument_to_raw(self, error: InvalidArgumentError) -> bytes:
        status_proto = status_pb2.Status(
            code=Status.INVALID_ARGUMENT.value,
            message="Invalid data in request.",
        )
        detail = BadRequest(
            field_violations=[
                BadRequest.FieldViolation(
                    field=field_name,
                    description=field_error,
                )
                for (field_name, field_error) in error.errors_by_fields.items()
            ]
        )
        detail_container = status_proto.details.add()
        detail_container.Pack(detail)
        return cast(bytes, status_proto.SerializeToString())

    def __not_found_to_raw(self, error: NotFoundError) -> bytes:
        status_proto = status_pb2.Status(
            code=Status.NOT_FOUND.value, message="Not found."
        )
        return cast(bytes, status_proto.SerializeToString())

    def __server_error_to_raw(self, error: ServerError) -> bytes:
        if len(error.args) > 0:
            message = error.args[0]
        else:
            message = "Internal error"
        status_proto = status_pb2.Status(code=Status.INTERNAL.value, message=message)
        return cast(bytes, status_proto.SerializeToString())

    def resolve_proto(self, model_path: str) -> Type[protobuf_message.Message] | None:
        try:
            return self.protos[model_path]
        except KeyError:
            logger.error(f"Proto for model {model_path} not found")
            return None

    def __proto_obj_to_dict(
        self, proto_obj: protobuf_message.Message
    ) -> dict[str, Any]:
        model_dict: dict[str, Any] = {}

        for field in proto_obj.DESCRIPTOR.fields:
            # skip fields with default values
            if not (not field.has_presence or proto_obj.HasField(field.name)):
                continue

            if field.containing_oneof is not None:
                # field in oneof: set value to oneof field
                # it can be message as well, convert it if so
                if field.type == field.TYPE_MESSAGE:
                    model_dict[field.containing_oneof.name] = self.__proto_obj_to_dict(
                        proto_obj.__getattribute__(field.name)
                    )
                else:
                    model_dict[field.containing_oneof.name] = (
                        proto_obj.__getattribute__(field.name)
                    )
            elif (
                field.label == field.LABEL_REPEATED and field.type == field.TYPE_MESSAGE
            ):
                if isinstance(
                    proto_obj.__getattribute__(field.name), ScalarMapContainer
                ):
                    # maps are also repeated messages
                    proto_map = proto_obj.__getattribute__(field.name)
                    model_dict[field.name] = dict(proto_map.items())
                elif isinstance(
                    proto_obj.__getattribute__(field.name), MessageMapContainer
                ):
                    proto_map = proto_obj.__getattribute__(field.name)
                    model_dict[field.name] = {
                        key: self.__proto_obj_to_dict(value)
                        for key, value in proto_map.items()
                    }
                else:
                    # repeated with messages: convert messages
                    model_dict[field.name] = [
                        self.__proto_obj_to_dict(item)
                        for item in proto_obj.__getattribute__(field.name)
                    ]
            elif field.type == field.TYPE_MESSAGE:
                if field.message_type.full_name == "google.protobuf.Timestamp":
                    timestamp_obj = proto_obj.__getattribute__(field.name)
                    model_dict[field.name] = datetime.fromtimestamp(
                        timestamp_obj.seconds + (timestamp_obj.nanos / 1_000_000_000),
                        tz=timezone.utc,
                    )
                else:
                    # nested message: convert
                    model_dict[field.name] = self.__proto_obj_to_dict(
                        proto_obj.__getattribute__(field.name)
                    )
            else:
                model_dict[field.name] = proto_obj.__getattribute__(field.name)
        return model_dict

    def __dict_to_proto_obj(
        self,
        model_dict: dict[str, Any],
        model_obj: BaseModel,
    ) -> protobuf_message.Message:
        try:
            proto_cls = self.protos[model_obj.__modapp_path__]
        except KeyError:
            raise ServerError(f"Proto for {model_obj.__modapp_path__} not found")

        # serialize 'oneof' fields
        for oneof_name, oneof_descriptor in proto_cls.DESCRIPTOR.oneofs_by_name.items():
            if oneof_name in model_dict:
                try:
                    proto_field_name = next(
                        field.name
                        for field in oneof_descriptor.fields
                        if model_field_type_matches_proto_field(
                            dict_field_value=model_dict[oneof_name],
                            model_field_value=model_obj.__getattribute__(oneof_name),
                            proto_field=field,
                        )
                    )
                except StopIteration:
                    raise Exception(
                        f"Field not found in oneof {oneof_name} in message"
                        f" {proto_cls.DESCRIPTOR.full_name} for value"
                        f" {model_dict[oneof_name]}"
                    )
                model_dict[proto_field_name] = model_dict[oneof_name]
                del model_dict[oneof_name]

        # python enum to integer
        for field in proto_cls.DESCRIPTOR.fields:
            if field.name not in model_dict:
                continue

            if field.type == field.TYPE_ENUM:
                model_dict[field.name] = (
                    model_dict[field.name].value
                    if isinstance(model_dict[field.name], Enum)
                    else model_dict[field.name]
                )
            elif field.type == field.TYPE_MESSAGE:
                if field.message_type.full_name == "google.protobuf.Timestamp":
                    datetime_value = model_dict[field.name]
                    model_dict[field.name] = Timestamp(
                        seconds=int(
                            datetime_value.replace(tzinfo=timezone.utc).timestamp()
                        ),
                        nanos=datetime_value.microsecond * 1000,
                    )
                elif field.label == field.LABEL_REPEATED:
                    # maps with messages as values in proto descriptor are repeated messages with
                    # automatically generated name <FieldNamePascal>Entry. This name cannot be used
                    # for own messages, so it is unambiguous identifier of a map. At the same time
                    # it means user cannot create own repeated list of messages with such pattern
                    # in the name and (key, value) fields inside.
                    if (
                        field.message_type.name
                        == f"{field.camelcase_name[0].upper()}{field.camelcase_name[1:]}Entry"
                    ):
                        map_proto_type = field.message_type
                        if (
                            "key" in map_proto_type.fields_by_name
                            and "value" in map_proto_type.fields_by_name
                        ):
                            value_message_type = map_proto_type.fields_by_name["value"]
                            if value_message_type.message_type is not None:
                                model_dict[field.name] = {
                                    key: self.__dict_to_proto_obj(
                                        model_dict=value,
                                        model_obj=model_obj.__getattribute__(
                                            field.name
                                        )[key],
                                    )
                                    for (key, value) in model_dict[field.name].items()
                                }
                    else:
                        # repeated with nested message
                        # value_proto_type_identifier = field.message_type.full_name
                        model_dict[field.name] = [
                            self.__dict_to_proto_obj(
                                model_dict=item_dict,
                                model_obj=model_obj.__getattribute__(field.name)[idx],
                                # modapp_path=value_proto_type_identifier,
                            )
                            for (idx, item_dict) in enumerate(model_dict[field.name])
                        ]
                else:
                    # nested message
                    field_name_in_obj = (
                        field.containing_oneof.name
                        if field.containing_oneof is not None
                        else field.name
                    )
                    model_dict[field.name] = self.__dict_to_proto_obj(
                        model_dict=model_dict[field.name],
                        model_obj=model_obj.__getattribute__(field_name_in_obj),
                    )

        return proto_cls(**model_dict)


__all__ = ["ProtobufConverter"]
