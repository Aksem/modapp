from __future__ import annotations
import importlib
import uuid
from inspect import isclass
from dataclasses import dataclass
from typing import Generic, Type
from pathlib import Path

from google.protobuf import message
from google.protobuf.internal import enum_type_wrapper
from grpc_tools import protoc
from google.protobuf import descriptor_pool

from modapp.models import ModelType
from modapp.converters.protobuf import ProtobufConverter
from modapp.validators.pydantic import PydanticValidator
import tests.converters.protobuf.data as data


def new_descriptor_pool():
    return descriptor_pool.DescriptorPool()


def generate_proto(proto_str: str, tmp_path: Path) -> dict[str, Type[message.Message]]:
    proto_name = f"proto_{uuid.uuid4()}".replace("-", "_")
    proto_file_path = tmp_path / f"{proto_name}.proto"
    proto_file_path.write_text(proto_str)

    # protos on loading are stored in a global pool(default one), and protos may not be generated
    # and loaded twice. To avoid duplicate error, create a new descriptor pool for each test(it
    # is expected that `generate_proto` is called only once per test)
    descriptor_pool.Default = new_descriptor_pool
    protoc.main(
        [
            "grpc_tools.protoc",
            f"-I{tmp_path}",
            f"--python_out={tmp_path}",
            f"--pyi_out={tmp_path}",
            f"--grpc_python_out={tmp_path}",
            proto_file_path.absolute().as_posix(),
        ]
    )

    py_module_path = tmp_path / f"{proto_name}_pb2.py"
    spec = importlib.util.spec_from_file_location(proto_name, py_module_path)
    py_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(py_module)

    proto_classes = {
        item.DESCRIPTOR.full_name: item
        for item in py_module.__dict__.values()
        if isclass(item)
        and issubclass(item, message.Message)
        or isinstance(item, enum_type_wrapper.EnumTypeWrapper)
    }
    return proto_classes


@dataclass
class PydanticTestContext(Generic[ModelType]):
    converter: ProtobufConverter
    proto_instance: message.Message
    generated_protos: dict[str, Type[message.Message]]
    model_cls: Type[ModelType]
    # reference model instance
    model_instance_ref: ModelType


# TODO: test special data types like path, timestamp etc
# TODO: test errors
# TODO: test different letter cases in keys
# TODO: test maps
# TODO: test model defaults
# TODO: test correct result if wrong model is passed to raw_to_model
class ProtobufConverterBaseTestSuite:
    def arrange_test_scalars(
        self, tmp_path: Path
    ) -> PydanticTestContext[data.MessageWithScalars]:
        generated_protos = generate_proto(
            data.message_with_scalars_proto_src,
            tmp_path,
        )
        converter = ProtobufConverter(
            protos=generated_protos, validator=PydanticValidator()
        )
        proto_instance = generated_protos[
            "modapp.tests.converters.protobuf.scalars.MessageWithScalars"
        ](
            double_value=7821931.22,
            float_value=4324.62,
            int32_value=83424,
            int64_value=4234234245,
            uint32_value=86767,
            uint64_value=656478,
            sint32_value=543536,
            sint64_value=85954,
            fixed32_value=825376,
            fixed64_value=934243,
            sfixed32_value=985435,
            sfixed64_value=845352,
            bool_value=True,
            string_value="string in message to convert",
            bytes_value=b"932AF390QWE"
        )
        model_instance = data.MessageWithScalars(
            double_value=7821931.22,
            float_value=4324.62,
            int32_value=83424,
            int64_value=4234234245,
            uint32_value=86767,
            uint64_value=656478,
            sint32_value=543536,
            sint64_value=85954,
            fixed32_value=825376,
            fixed64_value=934243,
            sfixed32_value=985435,
            sfixed64_value=845352,
            bool_value=True,
            string_value="string in message to convert",
            bytes_value=b"932AF390QWE",
        )
        return PydanticTestContext[data.MessageWithScalars](
            converter=converter,
            proto_instance=proto_instance,
            generated_protos=generated_protos,
            model_cls=data.MessageWithScalars,
            model_instance_ref=model_instance,
        )

    def test_scalars(self, tmp_path: Path) -> None:
        raise NotImplementedError()

    def arrange_test_enum(
        self, tmp_path: Path
    ) -> PydanticTestContext[data.MessageWithEnum]:
        generated_protos = generate_proto(
            data.message_with_enum_proto_src,
            tmp_path,
        )
        converter = ProtobufConverter(
            protos=generated_protos, validator=PydanticValidator()
        )
        proto_instance = generated_protos[
            "modapp.tests.converters.protobuf.enum_test.MessageWithEnum"
        ](
            color=generated_protos[
                "modapp.tests.converters.protobuf.enum_test.Color"
            ].COLOR_YELLOW,
        )
        model_instance = data.MessageWithEnum(
            color=data.Color.COLOR_YELLOW,
        )
        return PydanticTestContext[data.MessageWithEnum](
            converter=converter,
            proto_instance=proto_instance,
            generated_protos=generated_protos,
            model_cls=data.MessageWithEnum,
            model_instance_ref=model_instance,
        )

    def test_enum(self, tmp_path: Path) -> None:
        raise NotImplementedError()

    def arrange_test_defaults(
        self, tmp_path: Path
    ) -> PydanticTestContext[data.MessageToTestDefaults]:
        generated_protos = generate_proto(
            data.message_to_test_defaults_proto_src,
            tmp_path,
        )
        converter = ProtobufConverter(
            protos=generated_protos, validator=PydanticValidator()
        )
        proto_instance = generated_protos[
            "modapp.tests.converters.protobuf.defaults.MessageToTestDefaults"
        ]()
        model_instance = data.MessageToTestDefaults(
            double_value=0,
            float_value=0,
            int32_value=0,
            int64_value=0,
            uint32_value=0,
            uint64_value=0,
            sint32_value=0,
            sint64_value=0,
            fixed32_value=0,
            fixed64_value=0,
            sfixed32_value=0,
            sfixed64_value=0,
            bool_value=False,
            string_value="",
            bytes_value=b"",
        )
        return PydanticTestContext[data.MessageToTestDefaults](
            converter=converter,
            proto_instance=proto_instance,
            generated_protos=generated_protos,
            model_cls=data.MessageToTestDefaults,
            model_instance_ref=model_instance,
        )

    def test_defaults(self, tmp_path: Path) -> None:
        raise NotImplementedError()

    def arrange_test_nested_messages(
        self, tmp_path: Path
    ) -> PydanticTestContext[data.RootMessage]:
        generated_protos = generate_proto(
            data.nested_messages_proto_src,
            tmp_path,
        )
        converter = ProtobufConverter(
            protos=generated_protos, validator=PydanticValidator()
        )
        level3_proto_instance = generated_protos[
            "modapp.tests.converters.protobuf.nested_messages.MessageLevel3"
        ](result="success")
        level2_proto_instance = generated_protos[
            "modapp.tests.converters.protobuf.nested_messages.MessageLevel2"
        ](level3=level3_proto_instance)
        level1_proto_instance = generated_protos[
            "modapp.tests.converters.protobuf.nested_messages.MessageLevel1"
        ](level2=level2_proto_instance)
        proto_instance = generated_protos[
            "modapp.tests.converters.protobuf.nested_messages.RootMessage"
        ](level1=level1_proto_instance)
        model_instance = data.RootMessage(
            level1=data.MessageLevel1(
                level2=data.MessageLevel2(level3=data.MessageLevel3(result="success"))
            )
        )
        return PydanticTestContext[data.RootMessage](
            converter=converter,
            proto_instance=proto_instance,
            generated_protos=generated_protos,
            model_cls=data.RootMessage,
            model_instance_ref=model_instance,
        )

    def test_nested_messages(self, tmp_path: Path) -> None:
        raise NotImplementedError()

    def arrange_scalar_repeated_test(
        self, tmp_path: Path
    ) -> PydanticTestContext[data.MessageWithScalarRepeated]:
        generated_protos = generate_proto(
            data.message_with_scalar_repeated_proto_src,
            tmp_path,
        )
        converter = ProtobufConverter(
            protos=generated_protos, validator=PydanticValidator()
        )
        proto_instance = generated_protos[
            "modapp.tests.converters.protobuf.scalar_repeated.MessageWithScalarRepeated"
        ](integer_repeated=[56, -223, 91, 4412])
        model_instance = data.MessageWithScalarRepeated(
            integer_repeated=[56, -223, 91, 4412]
        )
        return PydanticTestContext[data.MessageWithScalarRepeated](
            converter=converter,
            proto_instance=proto_instance,
            generated_protos=generated_protos,
            model_cls=data.MessageWithScalarRepeated,
            model_instance_ref=model_instance,
        )

    def test_scalar_repeated(self, tmp_path: Path) -> None:
        raise NotImplementedError()

    def arrange_message_repeated_test(
        self, tmp_path: Path
    ) -> PydanticTestContext[data.MessageWithMessageRepeated]:
        generated_protos = generate_proto(
            data.message_repeated_proto_src,
            tmp_path,
        )
        converter = ProtobufConverter(
            protos=generated_protos, validator=PydanticValidator()
        )
        proto_instance = generated_protos[
            "modapp.tests.converters.protobuf.message_repeated.MessageWithMessageRepeated"
        ](
            message_repeated=[
                generated_protos[
                    "modapp.tests.converters.protobuf.message_repeated.User"
                ](first_name="Alex", last_name="Smith"),
                generated_protos[
                    "modapp.tests.converters.protobuf.message_repeated.User"
                ](first_name="John", last_name="Houston"),
            ]
        )
        model_instance = data.MessageWithMessageRepeated(
            message_repeated=[
                data.User(first_name="Alex", last_name="Smith"),
                data.User(first_name="John", last_name="Houston"),
            ]
        )
        return PydanticTestContext[data.MessageWithMessageRepeated](
            converter=converter,
            proto_instance=proto_instance,
            generated_protos=generated_protos,
            model_cls=data.MessageWithMessageRepeated,
            model_instance_ref=model_instance,
        )

    def test_message_repeated(self, tmp_path: Path) -> None:
        raise NotImplementedError()

    def arrange_nested_message_repeated_test(
        self, tmp_path: Path
    ) -> PydanticTestContext[data.MessageWithNestedMessageRepeated]:
        generated_protos = generate_proto(
            data.nested_message_repeated_proto_src,
            tmp_path,
        )
        converter = ProtobufConverter(
            protos=generated_protos, validator=PydanticValidator()
        )
        proto_instance = generated_protos[
            "modapp.tests.converters.protobuf.nested_message_repeated.MessageWithNestedMessageRepeated"
        ](
            message_repeated=[
                generated_protos[
                    "modapp.tests.converters.protobuf.nested_message_repeated.UserWithAddress"
                ](
                    first_name="Alex",
                    last_name="Smith",
                    address=generated_protos[
                        "modapp.tests.converters.protobuf.nested_message_repeated.Address"
                    ](postal_code=1000, country="EN"),
                ),
                generated_protos[
                    "modapp.tests.converters.protobuf.nested_message_repeated.UserWithAddress"
                ](
                    first_name="John",
                    last_name="Houston",
                    address=generated_protos[
                        "modapp.tests.converters.protobuf.nested_message_repeated.Address"
                    ](postal_code=8510, country="US"),
                ),
            ]
        )
        model_instance = data.MessageWithNestedMessageRepeated(
            message_repeated=[
                data.UserWithAddress(
                    first_name="Alex",
                    last_name="Smith",
                    address=data.Address(postal_code=1000, country="EN"),
                ),
                data.UserWithAddress(
                    first_name="John",
                    last_name="Houston",
                    address=data.Address(postal_code=8510, country="US"),
                ),
            ]
        )
        return PydanticTestContext[data.MessageWithNestedMessageRepeated](
            converter=converter,
            proto_instance=proto_instance,
            generated_protos=generated_protos,
            model_cls=data.MessageWithNestedMessageRepeated,
            model_instance_ref=model_instance,
        )

    def test_nested_message_repeated(self, tmp_path: Path) -> None:
        raise NotImplementedError()

    def arrange_one_of_scalars_test(
        self, tmp_path: Path
    ) -> PydanticTestContext[data.MessageToTestOneOfScalars]:
        generated_protos = generate_proto(
            data.one_of_scalars_proto_src,
            tmp_path,
        )
        converter = ProtobufConverter(
            protos=generated_protos, validator=PydanticValidator()
        )
        proto_instance = generated_protos[
            "modapp.tests.converters.protobuf.one_of_scalars.MessageToTestOneOfScalars"
        ](str_field="string in one field", double_field=9514.73)
        model_instance = data.MessageToTestOneOfScalars(
            str_or_int64="string in one field", bool_or_double=9514.73
        )
        return PydanticTestContext[data.MessageToTestOneOfScalars](
            converter=converter,
            proto_instance=proto_instance,
            generated_protos=generated_protos,
            model_cls=data.MessageToTestOneOfScalars,
            model_instance_ref=model_instance,
        )

    def test_one_of_scalars(self, tmp_path: Path) -> None:
        raise NotImplementedError()

    def arrange_one_of_defaults_test(
        self, tmp_path: Path
    ) -> PydanticTestContext[data.MessageToTestOneOfDefaults]:
        generated_protos = generate_proto(
            data.one_of_defaults_proto_src,
            tmp_path,
        )
        converter = ProtobufConverter(
            protos=generated_protos, validator=PydanticValidator()
        )
        proto_instance = generated_protos[
            "modapp.tests.converters.protobuf.one_of_defaults.MessageToTestOneOfDefaults"
        ]()
        model_instance = data.MessageToTestOneOfDefaults(
            bool_or_str=True, double_or_str="default_string"
        )
        return PydanticTestContext[data.MessageToTestOneOfDefaults](
            converter=converter,
            proto_instance=proto_instance,
            generated_protos=generated_protos,
            model_cls=data.MessageToTestOneOfDefaults,
            model_instance_ref=model_instance,
        )

    def test_one_of_defaults(self, tmp_path: Path) -> None:
        raise NotImplementedError()

    def arrange_one_of_nested_messages_test(
        self, tmp_path: Path
    ) -> PydanticTestContext[data.MessageToTestOneOfNestedMessages]:
        generated_protos = generate_proto(
            data.one_of_nested_messages_proto_src,
            tmp_path,
        )
        converter = ProtobufConverter(
            protos=generated_protos, validator=PydanticValidator()
        )
        proto_instance = generated_protos[
            "modapp.tests.converters.protobuf.one_of_nested_messages.MessageToTestOneOfNestedMessages"
        ](
            root_msg=generated_protos[
                "modapp.tests.converters.protobuf.one_of_nested_messages.RootMessage"
            ](
                level1=generated_protos[
                    "modapp.tests.converters.protobuf.one_of_nested_messages.MessageLevel1"
                ](
                    level2=generated_protos[
                        "modapp.tests.converters.protobuf.one_of_nested_messages.MessageLevel2"
                    ](
                        level3=generated_protos[
                            "modapp.tests.converters.protobuf.one_of_nested_messages.MessageLevel3"
                        ](result="success")
                    )
                )
            ),
            level2_msg=generated_protos[
                "modapp.tests.converters.protobuf.one_of_nested_messages.MessageLevel2"
            ](
                level3=generated_protos[
                    "modapp.tests.converters.protobuf.one_of_nested_messages.MessageLevel3"
                ](result="success 2")
            ),
        )
        model_instance = data.MessageToTestOneOfNestedMessages(
            root_msg_or_level1_msg=data.RootMessage(
                level1=data.MessageLevel1(
                    level2=data.MessageLevel2(
                        level3=data.MessageLevel3(result="success")
                    )
                )
            ),
            level1_or_level2_msg=data.MessageLevel2(
                level3=data.MessageLevel3(result="success 2")
            ),
        )
        return PydanticTestContext[data.MessageToTestOneOfNestedMessages](
            converter=converter,
            proto_instance=proto_instance,
            generated_protos=generated_protos,
            model_cls=data.MessageToTestOneOfNestedMessages,
            model_instance_ref=model_instance,
        )

    def test_one_of_nested_messages(self, tmp_path: Path) -> None:
        raise NotImplementedError()
