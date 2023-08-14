"""
Notes:
1. Use test-specific packages in protos, because protoc has global definition storage and messages
    with the same name and in the same package can conflict even if they are in different files.
"""
from __future__ import annotations
import math
from pathlib import Path

from tests.converters.protobuf.base_testsuite import ProtobufConverterBaseTestSuite


class TestProtobufConverterRawToModel(ProtobufConverterBaseTestSuite):
    def test_scalars(self, tmp_path: Path) -> None:
        context = self.arrange_test_scalars(tmp_path=tmp_path)

        model_instance = context.converter.raw_to_model(
            raw=context.proto_instance.SerializeToString(), model_cls=context.model_cls
        )

        # compare one by one, because float cannot be compared automatically in class instance
        assert math.isclose(
            model_instance.double_value, context.model_instance_ref.double_value
        )
        # float seems to be not very precise, even math.isclose returns False
        assert (
            abs(model_instance.float_value - context.model_instance_ref.float_value)
            < 0.01
        )
        assert model_instance.int32_value == context.model_instance_ref.int32_value
        assert model_instance.int64_value == context.model_instance_ref.int64_value
        assert model_instance.uint32_value == context.model_instance_ref.uint32_value
        assert model_instance.uint64_value == context.model_instance_ref.uint64_value
        assert model_instance.sint32_value == context.model_instance_ref.sint32_value
        assert model_instance.sint64_value == context.model_instance_ref.sint64_value
        assert model_instance.fixed32_value == context.model_instance_ref.fixed32_value
        assert model_instance.fixed64_value == context.model_instance_ref.fixed64_value
        assert (
            model_instance.sfixed32_value == context.model_instance_ref.sfixed32_value
        )
        assert (
            model_instance.sfixed64_value == context.model_instance_ref.sfixed64_value
        )
        assert model_instance.bool_value == context.model_instance_ref.bool_value
        assert model_instance.string_value == context.model_instance_ref.string_value
        assert model_instance.bytes_value == context.model_instance_ref.bytes_value

    def test_enum(self, tmp_path: Path) -> None:
        context = self.arrange_test_enum(tmp_path=tmp_path)

        model_instance = context.converter.raw_to_model(
            raw=context.proto_instance.SerializeToString(), model_cls=context.model_cls
        )

        assert model_instance.color == context.model_instance_ref.color

    def test_defaults(self, tmp_path: Path) -> None:
        context = self.arrange_test_defaults(tmp_path=tmp_path)

        model_instance = context.converter.raw_to_model(
            raw=context.proto_instance.SerializeToString(), model_cls=context.model_cls
        )

        # compare one by one, because float cannot be compared automatically in class instance
        assert math.isclose(
            model_instance.double_value, context.model_instance_ref.double_value
        )
        # float seems to be not very precise, even math.isclose returns False
        assert abs(model_instance.float_value) < 0.01
        assert model_instance.int32_value == context.model_instance_ref.int32_value
        assert model_instance.int64_value == context.model_instance_ref.int64_value
        assert model_instance.uint32_value == context.model_instance_ref.uint32_value
        assert model_instance.uint64_value == context.model_instance_ref.uint64_value
        assert model_instance.sint32_value == context.model_instance_ref.sint32_value
        assert model_instance.sint64_value == context.model_instance_ref.sint64_value
        assert model_instance.fixed32_value == context.model_instance_ref.fixed32_value
        assert model_instance.fixed64_value == context.model_instance_ref.fixed64_value
        assert (
            model_instance.sfixed32_value == context.model_instance_ref.sfixed32_value
        )
        assert (
            model_instance.sfixed64_value == context.model_instance_ref.sfixed64_value
        )
        assert model_instance.bool_value == context.model_instance_ref.bool_value
        assert model_instance.string_value == context.model_instance_ref.string_value
        assert model_instance.bytes_value == context.model_instance_ref.bytes_value
        # TODO: enum
        # TODO: repeated
        # TODO: message?

    def test_nested_messages(self, tmp_path: Path) -> None:
        context = self.arrange_test_nested_messages(tmp_path)

        model_instance = context.converter.raw_to_model(
            raw=context.proto_instance.SerializeToString(), model_cls=context.model_cls
        )

        assert model_instance == context.model_instance_ref

    def test_scalar_repeated(self, tmp_path: Path) -> None:
        context = self.arrange_scalar_repeated_test(tmp_path)

        model_instance = context.converter.raw_to_model(
            raw=context.proto_instance.SerializeToString(), model_cls=context.model_cls
        )

        assert model_instance == context.model_instance_ref

    def test_message_repeated(self, tmp_path: Path) -> None:
        context = self.arrange_message_repeated_test(tmp_path)

        model_instance = context.converter.raw_to_model(
            raw=context.proto_instance.SerializeToString(), model_cls=context.model_cls
        )

        assert model_instance == context.model_instance_ref

    def test_nested_message_repeated(self, tmp_path: Path) -> None:
        context = self.arrange_nested_message_repeated_test(tmp_path)

        model_instance = context.converter.raw_to_model(
            raw=context.proto_instance.SerializeToString(),
            model_cls=context.model_cls,
        )

        assert model_instance == context.model_instance_ref

    def test_one_of_scalars(self, tmp_path: Path) -> None:
        context = self.arrange_one_of_scalars_test(tmp_path)

        model_instance = context.converter.raw_to_model(
            raw=context.proto_instance.SerializeToString(), model_cls=context.model_cls
        )

        assert model_instance.str_or_int64 == context.model_instance_ref.str_or_int64
        assert math.isclose(
            model_instance.bool_or_double, context.model_instance_ref.bool_or_double
        )

    def test_one_of_defaults(self, tmp_path: Path) -> None:
        context = self.arrange_one_of_defaults_test(tmp_path)

        model_instance = context.converter.raw_to_model(
            raw=context.proto_instance.SerializeToString(), model_cls=context.model_cls
        )

        assert model_instance.bool_or_str == context.model_instance_ref.bool_or_str
        assert model_instance.double_or_str == context.model_instance_ref.double_or_str

    def test_one_of_nested_messages(self, tmp_path: Path) -> None:
        context = self.arrange_one_of_nested_messages_test(tmp_path)

        model_instance = context.converter.raw_to_model(
            raw=context.proto_instance.SerializeToString(),
            model_cls=context.model_cls,
        )

        assert model_instance == context.model_instance_ref
