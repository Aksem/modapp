from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, Callable

if TYPE_CHECKING:
    from typing import Optional, Sequence, Type

    from .params import Depends


DependencyOverrides = Dict[Callable[..., Any], Callable[..., Any]]


class Dependant:
    def __init__(
        self,
        callable: Callable,
        name: Optional[str] = None,
        dependencies: Optional[Sequence[Dependant]] = None,
    ) -> None:
        self.callable = callable
        self.name = name
        self.dependencies = dependencies

    @classmethod
    def from_depends_list(
        cls: Type[Dependant], callable: Callable, depends_map: Dict[str, Depends]
    ) -> Dependant:
        return cls(
            callable=callable,
            dependencies=[
                Dependant(dep.dependency, name) for name, dep in depends_map.items()
            ],
        )
