from typing_extensions import NotRequired

from modapp.base_transport import BaseTransportConfig


class WebSocketifyTransportConfig(BaseTransportConfig):
    port: NotRequired[int]


DEFAULT_CONFIG: WebSocketifyTransportConfig = {
    "port": 3000,
    "max_message_size_kb": 4096,
}
