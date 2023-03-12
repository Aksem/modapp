from __future__ import annotations
from datetime import timezone
from typing import List, TYPE_CHECKING, Dict, Optional, Any, Type

import orjson
from loguru import logger
from pydantic import ValidationError
from google.protobuf.timestamp_pb2 import Timestamp
from google.rpc import status_pb2
from google.rpc.error_details_pb2 import BadRequest

from modapp.models import BaseModel, to_camel
from modapp.routing import Route
from modapp.base_converter import BaseConverter
from modapp.errors import InvalidArgumentError, Status, NotFoundError, ServerError

if TYPE_CHECKING:
    from modapp.errors import BaseModappError


ProtoType = Any


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
                raise ServerError(f'Proto for {model_cls} not found')
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
            model_schema = model.__class__.schema()
            for field in model.__dict__:
                # convert datetime to google.protobuf.Timestamp instance
                # in pydantic model schema datetime has type 'string' and format 'date-time'
                if (
                    model_schema["properties"][to_camel(field)].get("format", None)
                    == "date-time"
                ):
                    json[to_camel(field)] = Timestamp(
                        seconds=int(
                            model.__dict__[field]
                            .replace(tzinfo=timezone.utc)
                            .timestamp()
                        )
                        # TODO: nanos?
                    )
                elif "$ref" in model_schema["properties"][to_camel(field)]:
                    # model reference, fix recursively
                    fix_json(model.__dict__[field], json[to_camel(field)])

        fix_json(model, json_reply)

        try:
            proto_reply_type = self.resolved_protos[model.__modapp_path__]
        except KeyError:
            proto_reply_type = self.resolve_proto(model.__modapp_path__)
            if proto_reply_type is None:
                raise ServerError(f'Proto for {model} not found')
            else:
                self.resolved_protos[model.__modapp_path__] = proto_reply_type
        return proto_reply_type(**json_reply).SerializeToString()

    def error_to_raw(self, error: BaseModappError, route: Route) -> bytes:
        if isinstance(error, InvalidArgumentError):
            return self.__invalid_argument_to_raw(error, route)
        elif isinstance(error, NotFoundError):
            return self.__not_found_to_raw(error, route)
        elif isinstance(error, ServerError):
            return self.__server_error_to_raw(error, route)
        raise NotImplementedError()

    def __invalid_argument_to_raw(
        self, error: InvalidArgumentError, route: Route
    ) -> bytes:
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

    def __not_found_to_raw(self, error: NotFoundError, route: Route) -> bytes:
        status_proto = status_pb2.Status(
            code=Status.NOT_FOUND.value, message="Not found."
        )
        return status_proto.SerializeToString()

    def __server_error_to_raw(self, error: ServerError, route: Route) -> bytes:
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
            field[0].name: field[1] for field in type(proto_obj).ListFields(proto_obj)
        }

        # updating forward refs is required to resolve all ForwardRef before getting schema
        model_cls.update_forward_refs()
        request_schema = model_cls.schema()

        # protobuff ListFields method doesn't return empty string fields, but they are not
        # neccessary required
        # request_dict.update({
        #     field.name: ''
        #     for field in proto_request.DESCRIPTOR.fields
        #     if (field.name not in request_dict
        #         and request_schema['properties'][field.name].get('type', None) == 'string')
        # })

        # protobuff ListFields method doesn't return boolean fields if they have value False)
        request_dict.update(
            {
                field.name: False
                for field in proto_obj.DESCRIPTOR.fields
                if (
                    field.name not in request_dict
                    and field.name in request_schema["properties"]
                    and request_schema["properties"][field.name].get("type", None)
                    == "boolean"
                )
            }
        )
        # it also doesn't return list fields if they are empty
        request_dict.update(
            {
                field.name: []
                for field in proto_obj.DESCRIPTOR.fields
                if (
                    field.name not in request_dict
                    and field.name in request_schema["properties"]
                    and request_schema["properties"][field.name].get("type", None)
                    == "array"
                )
            }
        )

        # protobuff ListFields method doesn't return enum fields if they have value 0)
        fields_to_update: List[str] = []
        for (field, field_value) in type(proto_obj).ListFields(proto_obj):
            if (
                field.name not in request_dict
                and field.name in request_schema["properties"]
                and request_schema["properties"][field.name].get("$ref", None)
                is not None
            ):
                definition_name = (
                    request_schema["properties"][field.name]
                    .get("$ref", "")
                    .split("/")[-1]
                )
                try:
                    # can ref be imported? TODO: check
                    definition = request_schema["definitions"][definition_name]
                except KeyError:
                    logger.warning(
                        f"Field '{field.name}' has reference to definition, but"
                        " definition was not found"
                    )
                    continue

                if definition["type"] == "integer" and "enum" in definition:
                    fields_to_update.append(field.name)

            # arrays items of complex types need to be converted explicitly
            if (
                field.name in request_schema["properties"]
                and request_schema["properties"][field.name].get("type", None) == "array"
            ):
                item_type_ref_path = request_schema["properties"][field.name][
                    "items"
                ].get("$ref", None)
                if item_type_ref_path is not None:
                    item_model_type = model_cls.__dict__['__fields__'][field.name].outer_type_.__args__[0]
                    request_dict[field.name] = [
                        self.__proto_obj_to_model(
                            item, item_model_type
                        )
                        for item in field_value
                    ]

        request_dict.update({field: 0 for field in fields_to_update})

        # request is not neccessary valid utf-8 string, handle errors
        logger.trace(str(request_dict).encode("utf-8", errors="replace"))
        try:
            return model_cls(**request_dict)
        except ValidationError as error:
            raise InvalidArgumentError(
                {str(error["loc"][0]): error["msg"] for error in error.errors()}
            )
