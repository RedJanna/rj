from app.services.flow_fsm_service import decide_execution_order


def test_active_price_flow_prioritizes_price():
    out = decide_execution_order(primary_intent="OUT_OF_SCOPE_OTHER", active_flow="price")
    assert out["order"] == ["price", "booking"]
    assert out["reason"] == "active_flow_price_priority"


def test_price_intent_prioritizes_price_when_no_active_flow():
    out = decide_execution_order(primary_intent="PRICE_QUERY", active_flow=None)
    assert out["order"] == ["price", "booking"]
    assert out["reason"] == "intent_price_priority"


def test_default_prioritizes_booking():
    out = decide_execution_order(primary_intent="OUT_OF_SCOPE_OTHER", active_flow=None)
    assert out["order"] == ["booking", "price"]
    assert out["reason"] == "default_booking_priority"


def test_booking_state_priority_overrides_price_intent():
    out = decide_execution_order(
        primary_intent="PRICE_QUERY",
        active_flow=None,
        booking_flow_active=True,
        price_flow_active=False,
    )
    assert out["order"] == ["booking", "price"]
    assert out["reason"] == "booking_state_priority"


def test_price_state_priority_when_booking_not_active():
    out = decide_execution_order(
        primary_intent="OUT_OF_SCOPE_OTHER",
        active_flow=None,
        booking_flow_active=False,
        price_flow_active=True,
    )
    assert out["order"] == ["price", "booking"]
    assert out["reason"] == "price_state_priority"
