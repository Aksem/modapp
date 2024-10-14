from typing_extensions import NotRequired

from modapp.base_transport import BaseTransportConfig


class WebAiohttpTransportConfig(BaseTransportConfig):
    # if port is None, one will be selected automatically. Selected port is available in `port`
    # attribute of the transport after its start
    port: NotRequired[int | None]
    cors_allow: NotRequired[str | None]


DEFAULT_CONFIG: WebAiohttpTransportConfig = {
    "port": 3000,
    "max_message_size_kb": 4096,
    "cors_allow": None,
}
