from __future__ import annotations
from pathlib import Path

from tests.converters.protobuf.base_testsuite import ProtobufConverterBaseTestSuite


class TestProtobufConverterRawToModel(ProtobufConverterBaseTestSuite):
    def test_scalars(self, tmp_path: Path) -> None:
        context = self.arrange_test_scalars(tmp_path=tmp_path)

        raw_data = context.converter.model_to_raw(context.model_instance_ref)

        assert raw_data == context.proto_instance.SerializeToString()

    def test_defaults(self, tmp_path: Path) -> None:
        context = self.arrange_test_defaults(tmp_path=tmp_path)

        raw_data = context.converter.model_to_raw(context.model_instance_ref)

        assert raw_data == context.proto_instance.SerializeToString()

    def test_nested_messages(self, tmp_path: Path) -> None:
        context = self.arrange_test_nested_messages(tmp_path)

        raw_data = context.converter.model_to_raw(model=context.model_instance_ref)

        assert raw_data == context.proto_instance.SerializeToString()

    def test_nested_message_repeated(self, tmp_path: Path) -> None:
        context = self.arrange_nested_message_repeated_test(tmp_path)

        raw_data = context.converter.model_to_raw(model=context.model_instance_ref)

        assert raw_data == context.proto_instance.SerializeToString()

    def test_scalar_repeated(self, tmp_path: Path) -> None:
        context = self.arrange_scalar_repeated_test(tmp_path)

        raw_data = context.converter.model_to_raw(model=context.model_instance_ref)

        assert raw_data == context.proto_instance.SerializeToString()

    def test_message_repeated(self, tmp_path: Path) -> None:
        context = self.arrange_scalar_repeated_test(tmp_path)

        raw_data = context.converter.model_to_raw(model=context.model_instance_ref)

        assert raw_data == context.proto_instance.SerializeToString()

    def test_one_of_scalars(self, tmp_path: Path) -> None:
        context = self.arrange_one_of_scalars_test(tmp_path)

        raw_data = context.converter.model_to_raw(model=context.model_instance_ref)

        assert raw_data == context.proto_instance.SerializeToString()

    def test_one_of_defaults(self, tmp_path: Path) -> None:
        context = self.arrange_one_of_scalars_test(tmp_path)

        raw_data = context.converter.model_to_raw(model=context.model_instance_ref)

        assert raw_data == context.proto_instance.SerializeToString()

    def test_one_of_nested_messages(self, tmp_path: Path) -> None:
        context = self.arrange_one_of_scalars_test(tmp_path)

        raw_data = context.converter.model_to_raw(model=context.model_instance_ref)

        assert raw_data == context.proto_instance.SerializeToString()
