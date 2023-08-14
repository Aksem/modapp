from __future__ import annotations
from enum import Enum

from modapp.models import BaseModel


class MessageWithScalars(BaseModel):
    double_value: float
    float_value: float
    int32_value: int
    int64_value: int
    uint32_value: int
    uint64_value: int
    sint32_value: int
    sint64_value: int
    fixed32_value: int
    fixed64_value: int
    sfixed32_value: int
    sfixed64_value: int
    bool_value: bool
    string_value: str
    bytes_value: bytes

    __modapp_path__ = "modapp.tests.converters.protobuf.scalars.MessageWithScalars"


# list of scalar types in proto 3:
# https://protobuf.dev/programming-guides/proto3/#scalar
message_with_scalars_proto_src = """
syntax = "proto3";
package modapp.tests.converters.protobuf.scalars;

message MessageWithScalars {
    double double_value = 1;
    float float_value = 2;
    int32 int32_value = 3;
    int64 int64_value = 4;
    uint32 uint32_value = 5;
    uint64 uint64_value = 6;
    sint32 sint32_value = 7;
    sint64 sint64_value = 8;
    fixed32 fixed32_value = 9;
    fixed64 fixed64_value = 10;
    sfixed32 sfixed32_value = 11;
    sfixed64 sfixed64_value = 12;
    bool bool_value = 13;
    string string_value = 14;
    bytes bytes_value = 15;
}
"""


class MessageWithEnum(BaseModel):
    color: Color

    __modapp_path__ = "modapp.tests.converters.protobuf.enum_test.MessageWithEnum"


class Color(Enum):
    COLOR_YELLOW = 0
    COLOR_BLUE = 1


message_with_enum_proto_src = """
syntax = "proto3";
package modapp.tests.converters.protobuf.enum_test;

message MessageWithEnum {
    Color color = 1;
}

enum Color {
    COLOR_YELLOW = 0;
    COLOR_BLUE = 1;
}
"""


class MessageToTestDefaults(BaseModel):
    double_value: float
    float_value: float
    int32_value: int
    int64_value: int
    uint32_value: int
    uint64_value: int
    sint32_value: int
    sint64_value: int
    fixed32_value: int
    fixed64_value: int
    sfixed32_value: int
    sfixed64_value: int
    bool_value: bool
    string_value: str
    bytes_value: bytes

    __modapp_path__ = "modapp.tests.converters.protobuf.defaults.MessageToTestDefaults"


# default values in proto 3: https://protobuf.dev/programming-guides/proto3/#default
message_to_test_defaults_proto_src = """
syntax = "proto3";
package modapp.tests.converters.protobuf.defaults;

message MessageToTestDefaults {
    double double_value = 1;
    float float_value = 2;
    int32 int32_value = 3;
    int64 int64_value = 4;
    uint32 uint32_value = 5;
    uint64 uint64_value = 6;
    sint32 sint32_value = 7;
    sint64 sint64_value = 8;
    fixed32 fixed32_value = 9;
    fixed64 fixed64_value = 10;
    sfixed32 sfixed32_value = 11;
    sfixed64 sfixed64_value = 12;
    bool bool_value = 13;
    string string_value = 14;
    bytes bytes_value = 15;
}
"""


nested_messages_proto_src = """
syntax = "proto3";
package modapp.tests.converters.protobuf.nested_messages;

message RootMessage {
    MessageLevel1 level1 = 1;
}

message MessageLevel1 {
    MessageLevel2 level2 = 1;
}

message MessageLevel2 {
    MessageLevel3 level3 = 1;
}

message MessageLevel3 {
    string result = 1;
}
"""


class RootMessage(BaseModel):
    level1: MessageLevel1

    __modapp_path__ = "modapp.tests.converters.protobuf.nested_messages.RootMessage"


class MessageLevel1(BaseModel):
    level2: MessageLevel2

    __modapp_path__ = "modapp.tests.converters.protobuf.nested_messages.MessageLevel1"


class MessageLevel2(BaseModel):
    level3: MessageLevel3

    __modapp_path__ = "modapp.tests.converters.protobuf.nested_messages.MessageLevel2"


class MessageLevel3(BaseModel):
    result: str

    __modapp_path__ = "modapp.tests.converters.protobuf.nested_messages.MessageLevel3"


message_with_scalar_repeated_proto_src = """
syntax = "proto3";
package modapp.tests.converters.protobuf.scalar_repeated;

message MessageWithScalarRepeated {
    repeated int64 integer_repeated = 1;
}
"""


class MessageWithScalarRepeated(BaseModel):
    integer_repeated: list[int]

    __modapp_path__ = (
        "modapp.tests.converters.protobuf.scalar_repeated.MessageWithScalarRepeated"
    )


message_repeated_proto_src = """
syntax = "proto3";
package modapp.tests.converters.protobuf.message_repeated;

message MessageWithMessageRepeated {
    repeated User message_repeated = 1;
}

message User {
    string first_name = 1;
    string last_name = 2;
}
"""


class MessageWithMessageRepeated(BaseModel):
    message_repeated: list[User]

    __modapp_path__ = (
        "modapp.tests.converters.protobuf.message_repeated.MessageWithMessageRepeated"
    )


class User(BaseModel):
    first_name: str
    last_name: str

    __modapp_path__ = "modapp.tests.converters.protobuf.message_repeated.User"


nested_message_repeated_proto_src = """
syntax = "proto3";
package modapp.tests.converters.protobuf.nested_message_repeated;

message MessageWithNestedMessageRepeated {
    repeated UserWithAddress message_repeated = 1;
}

message UserWithAddress {
    string first_name = 1;
    string last_name = 2;
    Address address = 3;
}

message Address {
    int32 postal_code = 1;
    string country = 2;
}
"""


class MessageWithNestedMessageRepeated(BaseModel):
    message_repeated: list[UserWithAddress]

    __modapp_path__ = "modapp.tests.converters.protobuf.nested_message_repeated.MessageWithNestedMessageRepeated"


class UserWithAddress(BaseModel):
    first_name: str
    last_name: str
    address: Address

    __modapp_path__ = (
        "modapp.tests.converters.protobuf.nested_message_repeated.UserWithAddress"
    )


class Address(BaseModel):
    postal_code: int
    country: str

    __modapp_path__ = "modapp.tests.converters.protobuf.nested_message_repeated.Address"


one_of_scalars_proto_src = """
syntax = "proto3";
package modapp.tests.converters.protobuf.one_of_scalars;

message MessageToTestOneOfScalars {
    oneof str_or_int64 {
        string str_field = 1;
        int64 int64_field = 2;
    }

    oneof bool_or_double {
        bool bool_field = 3;
        double double_field = 4;
    }
}
"""


class MessageToTestOneOfScalars(BaseModel):
    # one field to test value of first type in union, one to test value of second type in union
    str_or_int64: str | int
    bool_or_double: bool | float

    __modapp_path__ = (
        "modapp.tests.converters.protobuf.one_of_scalars.MessageToTestOneOfScalars"
    )


one_of_defaults_proto_src = """
syntax = "proto3";
package modapp.tests.converters.protobuf.one_of_defaults;

message MessageToTestOneOfDefaults {
    oneof bool_or_str {
        bool bool_field = 1;
        string str_field = 2;
    }

    oneof double_or_str {
        double double_field = 3;
        string str_field_2 = 4;
    }
}
"""


class MessageToTestOneOfDefaults(BaseModel):
    # default value has first type in union
    bool_or_str: bool | str = True
    # default value has second type in union
    double_or_str: float | str = "default_string"

    __modapp_path__ = (
        "modapp.tests.converters.protobuf.one_of_defaults.MessageToTestOneOfDefaults"
    )


one_of_nested_messages_proto_src = """
syntax = "proto3";
package modapp.tests.converters.protobuf.one_of_nested_messages;

message MessageToTestOneOfNestedMessages {
    oneof root_msg_or_level1_msg {
        RootMessage root_msg = 1;
        MessageLevel1 level1_msg = 2;
    }

    oneof level1_or_level2_msg {
        MessageLevel1 level1_msg_2 = 3;
        MessageLevel2 level2_msg = 4;
    }
}

message RootMessage {
    MessageLevel1 level1 = 1;
}

message MessageLevel1 {
    MessageLevel2 level2 = 1;
}

message MessageLevel2 {
    MessageLevel3 level3 = 1;
}

message MessageLevel3 {
    string result = 1;
}
"""


class MessageToTestOneOfNestedMessages(BaseModel):
    # value has first type in union
    root_msg_or_level1_msg: RootMessage | MessageLevel1
    # value has second type in union
    level1_or_level2_msg: MessageLevel1 | MessageLevel2

    __modapp_path__ = "modapp.tests.converters.protobuf.one_of_nested_messages.MessageToTestOneOfNestedMessages"
