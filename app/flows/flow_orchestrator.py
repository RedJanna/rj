from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from app.flows.flow_contract import Flow, FlowContext, FlowResult


@dataclass(frozen=True)
class FlowMatch:
    flow_name: str
    result: FlowResult


class FlowOrchestrator:
    """
    mode:
      - off: disabled
      - shadow: execute flow match for observability, but caller may ignore output
      - active: caller can use output for user-facing response
    """

    def __init__(
        self,
        flows: List[Tuple[str, Flow]],
        mode: str = "shadow",
        flow_selector: Optional[Callable[[FlowContext, List[str]], List[str]]] = None,
    ) -> None:
        self._flows = flows
        self._flow_by_name = {name: flow for name, flow in flows}
        self._default_order = [name for name, _ in flows]
        self._flow_selector = flow_selector
        self.mode = (mode or "shadow").strip().lower()

    def is_enabled(self) -> bool:
        return self.mode in {"shadow", "active"}

    def select(self, context: FlowContext) -> Optional[Tuple[str, Flow]]:
        if not self.is_enabled():
            return None
        ordered_names = list(self._default_order)
        if self._flow_selector is not None:
            try:
                selected_names = self._flow_selector(context, list(self._default_order))
                if selected_names:
                    ordered_names = [name for name in selected_names if name in self._flow_by_name]
            except Exception:
                ordered_names = list(self._default_order)

        for name in ordered_names:
            flow = self._flow_by_name.get(name)
            if flow is None:
                continue
            try:
                if flow.can_handle(context):
                    return name, flow
            except Exception:
                continue
        return None

    def run(self, context: FlowContext) -> Optional[FlowMatch]:
        selected = self.select(context)
        if not selected:
            return None
        flow_name, flow = selected
        result = flow.handle(context)
        return FlowMatch(flow_name=flow_name, result=result)
