"""Tool registry.

Agents reach the industrial data layer only through declared tools. Each tool wraps a deterministic
operation — a database read, a model call, a retrieval — so an agent cannot improvise a data source.
Registration is explicit and testable.
"""

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., object]
    returns_model_output: bool = False


@dataclass
class ToolRegistry:
    _tools: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"duplicate tool registration: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unregistered tool: {name}") from exc

    def names(self) -> list[str]:
        return sorted(self._tools)


registry = ToolRegistry()
