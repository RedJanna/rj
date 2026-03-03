from __future__ import annotations

from app.flows.flow_contract import FlowContext, FlowResult
from app.flows.flow_orchestrator import FlowOrchestrator


class _DummyFlow:
    def __init__(self, can: bool, reply: str = "") -> None:
        self._can = can
        self._reply = reply

    def can_handle(self, context: FlowContext) -> bool:
        return self._can

    def handle(self, context: FlowContext) -> FlowResult:
        return FlowResult(reply_messages=[self._reply] if self._reply else [])


def _ctx() -> FlowContext:
    return FlowContext(
        user_id="u1",
        channel="whatsapp",
        message="merhaba",
        locale="tr",
        correlation_id="cid-1",
        state={},
    )


def test_orchestrator_selects_first_match():
    orch = FlowOrchestrator(
        flows=[
            ("f1", _DummyFlow(can=False)),
            ("f2", _DummyFlow(can=True, reply="ok")),
            ("f3", _DummyFlow(can=True, reply="late")),
        ],
        mode="active",
    )
    result = orch.run(_ctx())
    assert result is not None
    assert result.flow_name == "f2"
    assert result.result.reply_messages == ["ok"]


def test_orchestrator_off_mode_disables_run():
    orch = FlowOrchestrator(
        flows=[("f1", _DummyFlow(can=True, reply="ok"))],
        mode="off",
    )
    assert orch.run(_ctx()) is None


def test_orchestrator_uses_selector_order():
    def selector(context: FlowContext, names: list[str]) -> list[str]:
        return ["f3", "f2", "f1"]

    orch = FlowOrchestrator(
        flows=[
            ("f1", _DummyFlow(can=False)),
            ("f2", _DummyFlow(can=True, reply="middle")),
            ("f3", _DummyFlow(can=True, reply="first")),
        ],
        mode="active",
        flow_selector=selector,
    )
    result = orch.run(_ctx())
    assert result is not None
    assert result.flow_name == "f3"
    assert result.result.reply_messages == ["first"]
