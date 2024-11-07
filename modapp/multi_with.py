from typing import Any, AsyncContextManager, Generic, TypeVar


TypeValue = TypeVar('TypeValue')


class MultiWith(Generic[TypeValue]):
    def __init__(self, context_manager: AsyncContextManager):
        self.usages = 0
        self._context_manager = context_manager
        self._value: TypeValue | None = None

    async def __aenter__(self) -> TypeValue:
        self.usages += 1
        if self._value is not None:
            return self._value
        else:
            self._value = await self._context_manager.__aenter__()
            assert self._value is not None
            return self._value

    async def __aexit__(self, exc_type, exc, tb):
        self.usages -= 1
        if self.usages == 0:
            await self._context_manager.__aexit__(exc_type, exc, tb)
            self._value = None
