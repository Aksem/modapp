from typing_extensions import NotRequired

from modapp.base_transport import BaseTransportConfig


class GrpcTransportConfig(BaseTransportConfig):
    address: NotRequired[str]
    port: NotRequired[int]
    # not all clients supports error details passed in response metadata. Enables this feature
    error_details: NotRequired[bool]


DEFAULT_CONFIG: GrpcTransportConfig = {
    "address": "127.0.0.1",
    "port": 50051,
    "max_message_size_kb": 4096,
    "error_details": False
}
