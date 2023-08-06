from __future__ import annotations

# from datetime import timezone
from typing import TYPE_CHECKING, Any, Type

import google.protobuf.descriptor as protobuf_descriptor
from loguru import logger
from google.protobuf import message as protobuf_message
# from google.protobuf.timestamp_pb2 import Timestamp
from google.rpc import status_pb2
from google.rpc.error_details_pb2 import BadRequest

from modapp.models import BaseModel, to_camel  # , to_snake
from modapp.base_converter import BaseConverter, ModelType
from modapp.base_validator import BaseValidator
from modapp.errors import InvalidArgumentError, Status, NotFoundError, ServerError

if TYPE_CHECKING:
    from modapp.errors import BaseModappError


def model_field_type_matches_proto_field(
    model: BaseModel, field: str, proto_field: protobuf_descriptor.FieldDescriptor
) -> bool:
    field_value = model.__dict__[field]
    # primitive types
    # TODO: other types
    return (
        # string
        (
            proto_field.type == protobuf_descriptor.FieldDescriptor.TYPE_STRING
            and isinstance(field_value, str)
        )
        # messages
        or (
            proto_field.type == protobuf_descriptor.FieldDescriptor.TYPE_MESSAGE
            and proto_field.message_type.full_name == field_value.__modapp_path__
        )
    )

    """
    TYPE_DOUBLE         = 1
  TYPE_FLOAT          = 2
  TYPE_INT64          = 3
  TYPE_UINT64         = 4
  TYPE_INT32          = 5
  TYPE_FIXED64        = 6
  TYPE_FIXED32        = 7
  TYPE_BOOL           = 8
  TYPE_STRING         = 9
  TYPE_GROUP          = 10
  TYPE_MESSAGE        = 11
  TYPE_BYTES          = 12
  TYPE_UINT32         = 13
  TYPE_ENUM           = 14
  TYPE_SFIXED32       = 15
  TYPE_SFIXED64       = 16
  TYPE_SINT32         = 17
  TYPE_SINT64         = 18
    """


def get_schema_properties(model_schema: dict[str, Any]) -> dict[str, Any]:
    if "properties" in model_schema:
        return model_schema["properties"]
    elif "allOf" in model_schema:
        model_name = model_schema["allOf"][0].get("$ref", "").split("/")[-1]

        if (
            "$defs" in model_schema
            and model_name in model_schema["$defs"]
            and "properties" in model_schema["$defs"][model_name]
        ):
            # 'submodels'(models of fields) have $ref in schema and definitions
            return model_schema["$defs"][model_name]["properties"]
        else:
            raise Exception(f"No schema found for {model_name}")
    raise Exception("No schema found")


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

    def model_to_raw(self, model: BaseModel) -> bytes:
        # if reply is None:
        #     logger.error(f"Route handler '{route.path}' doesn't return value")
        #     raise ServerError("Internal error")
        model_dict = self.validator.model_to_dict(model=model)
        try:
            proto_cls = self.protos[model.__modapp_path__]
        except KeyError:
            raise ServerError(f"Proto for {model.__modapp_path__} not found")

        return proto_cls(**model_dict).SerializeToString()
        # def fix_json(model, json) -> None:
        #     # model is field with reference, it can be also for example Enum
        #     if not isinstance(model, BaseModel):
        #         return

        #     # model.__class__.update_forward_refs()
        #     # TODO: do we need the whole schema or field iterator would be enough?
        #     model_schema = model.__class__.model_json_schema()
        #     schema_properties = get_schema_properties(model_schema)

        #     # TODO: unify with code below
        #     try:
        #         proto_reply_type = self.resolved_protos[model.__modapp_path__]
        #     except KeyError:
        #         proto_reply_type = self.resolve_proto(model.__modapp_path__)
        #         if proto_reply_type is None:
        #             raise ServerError(f"Proto for {model.__class__.__name__} not found")
        #         else:
        #             self.resolved_protos[model.__modapp_path__] = proto_reply_type

        #     one_of_fields = proto_reply_type.DESCRIPTOR.oneofs_by_name.keys()

        #     for field in model.__dict__:
        #         field_camel_case = to_camel(field)
        #         # convert datetime to google.protobuf.Timestamp instance
        #         # in pydantic model schema datetime has type 'string' and format 'date-time'
        #         if (
        #             schema_properties[field_camel_case].get("format", None)
        #             == "date-time"
        #         ):
        #             json[field_camel_case] = Timestamp(
        #                 seconds=int(
        #                     model.__dict__[field]
        #                     .replace(tzinfo=timezone.utc)
        #                     .timestamp()
        #                 )
        #                 # TODO: nanos?
        #             )
        #         elif field_camel_case in one_of_fields:
        #             # one_of field: match subfield by type and replace `field_camel_case` by
        #             # subfield name in json
        #             try:
        #                 subfield = next(
        #                     proto_field
        #                     for proto_field in proto_reply_type.DESCRIPTOR.oneofs_by_name[
        #                         field_camel_case
        #                     ].fields
        #                     if model_field_type_matches_proto_field(
        #                         model, field, proto_field
        #                     )
        #                 )
        #             except StopIteration:
        #                 raise ServerError(
        #                     f"Cannot match field '{field_camel_case}' in proto"
        #                 )
        #             if (
        #                 subfield.type
        #                 == protobuf_descriptor.FieldDescriptor.TYPE_MESSAGE
        #             ):
        #                 # first fix submessage, then process parent message
        #                 fix_json(model.__dict__[field], json[field_camel_case])
        #             json[subfield.name] = json[field_camel_case]
        #             del json[field_camel_case]
        #         elif "$ref" in schema_properties[field_camel_case]:
        #             # model reference, fix recursively
        #             fix_json(model.__dict__[field], json[field_camel_case])
        #         elif (
        #             schema_properties[field_camel_case].get("type", None) == "array"
        #             and "$ref" in schema_properties[field_camel_case]["items"]
        #         ):
        #             # array of model references
        #             for idx, item in enumerate(model.__dict__[field]):
        #                 fix_json(item, json[field_camel_case][idx])

        # fix_json(model, model_dict)

        # try:
        #     proto_reply_type = self.resolved_protos[model.__modapp_path__]
        # except KeyError:
        #     proto_reply_type = self.resolve_proto(model.__modapp_path__)
        #     if proto_reply_type is None:
        #         raise ServerError(f"Proto for {model} not found")
        #     else:
        #         self.resolved_protos[model.__modapp_path__] = proto_reply_type

        # return proto_reply_type(**model_dict).SerializeToString()

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
                    field=to_camel(field_name),
                    description=field_error,
                )
                for (field_name, field_error) in error.errors_by_fields.items()
            ]
        )
        detail_container = status_proto.details.add()
        detail_container.Pack(detail)
        return status_proto.SerializeToString()

    def __not_found_to_raw(self, error: NotFoundError) -> bytes:
        status_proto = status_pb2.Status(
            code=Status.NOT_FOUND.value, message="Not found."
        )
        return status_proto.SerializeToString()

    def __server_error_to_raw(self, error: ServerError) -> bytes:
        if len(error.args) > 0:
            message = error.args[0]
        else:
            message = "Internal error"
        status_proto = status_pb2.Status(code=Status.INTERNAL.value, message=message)
        return status_proto.SerializeToString()

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
                    model_dict[
                        field.containing_oneof.name
                    ] = proto_obj.__getattribute__(field.name)
            if field.label == field.LABEL_REPEATED and field.type == field.TYPE_MESSAGE:
                # repeated with messages: convert messages
                model_dict[field.name] = [
                    self.__proto_obj_to_dict(item)
                    for item in proto_obj.__getattribute__(field.name)
                ]
            elif field.type == field.TYPE_MESSAGE:
                # nested message: convert
                model_dict[field.name] = self.__proto_obj_to_dict(
                    proto_obj.__getattribute__(field.name)
                )
            # TODO: enum?
            else:
                model_dict[field.name] = proto_obj.__getattribute__(field.name)
        return model_dict


__all__ = ["ProtobufConverter"]
