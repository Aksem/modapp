from modapp.base_transport import BaseTransportConfig


class InMemoryTransportConfig(BaseTransportConfig): ...


DEFAULT_CONFIG: InMemoryTransportConfig = {"max_message_size_kb": 4096}
