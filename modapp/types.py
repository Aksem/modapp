from typing import Any, Callable, TypeVar

DecoratedCallable = TypeVar("DecoratedCallable", bound=Callable[..., Any])
Metadata = dict[str, str | int | bool]
