from __future__ import annotations
from datetime import timezone
from typing import List, TYPE_CHECKING, Dict, Optional, Any, Type, Set
import inspect

import orjson
import google.protobuf.descriptor as protobuf_descriptor
from loguru import logger
from pydantic import ValidationError
from google.protobuf.timestamp_pb2 import Timestamp
from google.rpc import status_pb2
from google.rpc.error_details_pb2 import BadRequest

from modapp.models import BaseModel, to_camel, to_snake
from modapp.base_converter import BaseConverter
from modapp.errors import InvalidArgumentError, Status, NotFoundError, ServerError

if TYPE_CHECKING:
    from modapp.errors import BaseModappError


ProtoType = Any


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


def get_schema_properties(model_schema: Dict[str, Any]) -> Dict[str, Any]:
    model_name = model_schema.get("$ref", "").split("/")[-1]
    if "properties" in model_schema:
        return model_schema["properties"]
    elif (
        "$ref" in model_schema
        and "definitions" in model_schema
        and model_name in model_schema["definitions"]
        and "properties" in model_schema["definitions"][model_name]
    ):
        # 'submodels'(models of fields) have $ref in schema and definitions
        return model_schema["definitions"][model_name]["properties"]
    else:
        raise Exception(f"No schema found for {model_name}")


class ProtobufConverter(BaseConverter):
    def __init__(self, protos: Dict[str, ProtoType]) -> None:
        super().__init__()
        self.protos = protos
        self.resolved_protos: Dict[Type[BaseModel], ProtoType] = {}

    def raw_to_model(self, raw: bytes, model_cls: Type[BaseModel]) -> BaseModel:
        try:
            proto_request_type = self.resolved_protos[model_cls]
        except KeyError:
            proto_request_type = self.resolve_proto(model_cls.__modapp_path__)
            if proto_request_type is None:
                raise ServerError(f"Proto for {model_cls} not found")
            else:
                self.resolved_protos[model_cls] = proto_request_type

        proto_request = proto_request_type.FromString(raw)
        return self.__proto_obj_to_model(proto_request, model_cls)

    def model_to_raw(self, model: BaseModel) -> bytes:
        # if reply is None:
        #     logger.error(f"Route handler '{route.path}' doesn't return value")
        #     raise ServerError("Internal error")

        json_reply = orjson.loads(model.json(by_alias=True))

        def fix_json(model, json) -> None:
            # model is field with reference, it can be also for example Enum
            if not isinstance(model, BaseModel):
                return

            model.__class__.update_forward_refs()
            # TODO: do we need the whole schema or field iterator would be enough?
            model_schema = model.__class__.schema()
            schema_properties = get_schema_properties(model_schema)

            # TODO: unify with code below
            try:
                proto_reply_type = self.resolved_protos[model.__modapp_path__]
            except KeyError:
                proto_reply_type = self.resolve_proto(model.__modapp_path__)
                if proto_reply_type is None:
                    raise ServerError(f"Proto for {model.__class__.__name__} not found")
                else:
                    self.resolved_protos[model.__modapp_path__] = proto_reply_type

            one_of_fields = proto_reply_type.DESCRIPTOR.oneofs_by_name.keys()

            for field in model.__dict__:
                field_camel_case = to_camel(field)
                # convert datetime to google.protobuf.Timestamp instance
                # in pydantic model schema datetime has type 'string' and format 'date-time'
                if (
                    schema_properties[field_camel_case].get("format", None)
                    == "date-time"
                ):
                    json[field_camel_case] = Timestamp(
                        seconds=int(
                            model.__dict__[field]
                            .replace(tzinfo=timezone.utc)
                            .timestamp()
                        )
                        # TODO: nanos?
                    )
                elif field_camel_case in one_of_fields:
                    # one_of field: match subfield by type and replace `field_camel_case` by
                    # subfield name in json
                    try:
                        subfield = next(
                            proto_field
                            for proto_field in proto_reply_type.DESCRIPTOR.oneofs_by_name[
                                field_camel_case
                            ].fields
                            if model_field_type_matches_proto_field(
                                model, field, proto_field
                            )
                        )
                    except StopIteration:
                        raise ServerError(
                            f"Cannot match field '{field_camel_case}' in proto"
                        )
                    if (
                        subfield.type
                        == protobuf_descriptor.FieldDescriptor.TYPE_MESSAGE
                    ):
                        # first fix submessage, then process parent message
                        fix_json(model.__dict__[field], json[field_camel_case])
                    json[subfield.name] = json[field_camel_case]
                    del json[field_camel_case]
                elif "$ref" in schema_properties[field_camel_case]:
                    # model reference, fix recursively
                    fix_json(model.__dict__[field], json[field_camel_case])
                elif (
                    schema_properties[field_camel_case].get("type", None) == "array"
                    and "$ref" in schema_properties[field_camel_case]["items"]
                ):
                    # array of model references
                    for idx, item in enumerate(model.__dict__[field]):
                        fix_json(item, json[field_camel_case][idx])

        fix_json(model, json_reply)

        try:
            proto_reply_type = self.resolved_protos[model.__modapp_path__]
        except KeyError:
            proto_reply_type = self.resolve_proto(model.__modapp_path__)
            if proto_reply_type is None:
                raise ServerError(f"Proto for {model} not found")
            else:
                self.resolved_protos[model.__modapp_path__] = proto_reply_type

        return proto_reply_type(**json_reply).SerializeToString()

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

    def resolve_proto(self, model_path: str) -> Optional[ProtoType]:
        try:
            return self.protos[model_path]
        except KeyError:
            logger.error(f"Proto for model {model_path} not found")
            return None

    def __proto_obj_to_model(
        self, proto_obj: ProtoType, model_cls: Type[BaseModel]
    ) -> BaseModel:
        request_dict = {
            field.name: proto_obj.__getattribute__(field.name)
            for field in proto_obj.DESCRIPTOR.fields
            # take only filled fields into account, default values for optional fields expected
            # to be in schema as well
            if not field.has_presence or proto_obj.HasField(field.name)
        }

        def update_type_refs(
            model_type: Type[BaseModel], updated_type_refs: Set[str]
        ) -> None:
            if model_type.__name__ in updated_type_refs:
                return

            model_type.update_forward_refs()
            updated_type_refs.add(model_type.__name__)
            for field in model_type.__fields__.items():
                # if field type is union, then type_ is empty and sub_fields need to be processed
                if field[1].sub_fields is not None:
                    for sub_field in field[1].sub_fields:
                        if issubclass(sub_field.type_, BaseModel):
                            update_type_refs(sub_field.type_, updated_type_refs)
                elif issubclass(field[1].type_, BaseModel):
                    update_type_refs(field[1].type_, updated_type_refs)

        # updating forward refs is required to resolve all ForwardRef before getting schema
        updated_type_refs: Set[str] = set()
        update_type_refs(model_cls, updated_type_refs)
        request_schema = model_cls.schema()
        schema_properties = get_schema_properties(request_schema)

        # convert one_of fields to union in model
        for one_of_field in proto_obj.DESCRIPTOR.oneofs_by_name.values():
            for subfield in one_of_field.fields:
                if subfield.name in request_dict:
                    request_dict[one_of_field.name] = request_dict[subfield.name]
                    del request_dict[subfield.name]

        # TODO: try to process only fields from request_dict
        for field in proto_obj.DESCRIPTOR.fields:
            if field.has_presence and not proto_obj.HasField(field.name):
                continue
            # first resolve one_of: get its name
            if field.containing_oneof is not None:
                field_name = field.containing_oneof.name
            else:
                field_name = field.name

            field_value = request_dict[field_name]

            # arrays need to be converted explicitly
            if (
                field_name in schema_properties
                and schema_properties[field_name].get("type", None) == "array"
            ):
                item_type_ref_path = schema_properties[field_name]["items"].get(
                    "$ref", None
                )
                if item_type_ref_path is not None:
                    # arrays items of complex types need to be converted explicitly
                    item_model_type = model_cls.__dict__["__fields__"][
                        to_snake(field_name)
                    ].outer_type_.__args__[0]
                    request_dict[field_name] = [
                        self.__proto_obj_to_model(item, item_model_type)
                        for item in field_value
                    ]
                else:
                    # arrays with simple types as well: RepeatedScalarContainer -> list
                    request_dict[field_name] = [*request_dict[field_name]]

            # convert subobjects
            elif field.type == protobuf_descriptor.FieldDescriptor.TYPE_MESSAGE:
                if field_name not in schema_properties:
                    logger.error(f"Field {field_name} not found in model schema")
                    continue
                model_field = model_cls.__dict__["__fields__"][to_snake(field_name)]
                # either field type or one of subfields in case of union should match message type

                types = [model_field.type_]
                if model_field.sub_fields is not None:
                    types += [subtype.type_ for subtype in model_field.sub_fields]
                try:
                    modapp_path = next(
                        modapp_path
                        for (modapp_path, proto_type) in self.protos.items()
                        if field.message_type.full_name
                        == proto_type.DESCRIPTOR.full_name
                    )
                except StopIteration:
                    logger.error(
                        f"Cannot resolve field type '{field.message_type.full_name}' in"
                        " model"
                    )
                    continue

                try:
                    item_model_type = next(
                        t
                        for t in types
                        if inspect.isclass(t)
                        and issubclass(t, BaseModel)
                        and t.__modapp_path__ == modapp_path
                    )
                except StopIteration:
                    logger.error(f"Cannot find modapp type '{modapp_path}' in")
                    continue

                request_dict[field_name] = self.__proto_obj_to_model(
                    request_dict[field_name], item_model_type
                )

        try:
            return model_cls(**request_dict)
        except ValidationError as error:
            raise InvalidArgumentError(
                {str(error["loc"][0]): error["msg"] for error in error.errors()}
            )


__all__ = ["ProtobufConverter"]
