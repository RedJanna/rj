from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


@dataclass(frozen=True)
class FlowContext:
    user_id: str
    channel: str
    message: str
    locale: str
    correlation_id: str
    state: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FlowResult:
    reply_messages: List[str] = field(default_factory=list)
    next_state: Dict[str, Any] = field(default_factory=dict)
    side_effects: List[Dict[str, Any]] = field(default_factory=list)
    handoff: Optional[Dict[str, Any]] = None


class Flow(Protocol):
    def can_handle(self, context: FlowContext) -> bool:
        ...

    def handle(self, context: FlowContext) -> FlowResult:
        ...

