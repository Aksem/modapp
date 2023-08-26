from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Coroutine

if TYPE_CHECKING:
    from typing import Sequence, Type

    from .params import Depends


DependencyOverrides = dict[Callable[..., Any], Callable[..., Any]]
DependencyFunc = Callable[..., Any] | Coroutine[Any, None, Any]


class Dependant:
    def __init__(
        self,
        callable: DependencyFunc,
        name: str | None = None,
        dependencies: Sequence[Dependant] | None = None,
    ) -> None:
        self.callable = callable
        self.name = name
        self.dependencies = dependencies

    @classmethod
    def from_depends_list(
        cls: Type[Dependant],
        callable: DependencyFunc,
        depends_map: dict[str, Depends],
    ) -> Dependant:
        return cls(
            callable=callable,
            dependencies=[
                Dependant(dep.dependency, name) for name, dep in depends_map.items()
            ],
        )
