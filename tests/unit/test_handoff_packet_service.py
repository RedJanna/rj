from __future__ import annotations

from app.services.handoff_packet_service import build_handoff_packet, validate_handoff_packet


def test_validate_handoff_packet_ok():
    packet = build_handoff_packet(
        category="canli_destek",
        priority="medium",
        customer_phone="+905551112233",
        customer_message="Canlı desteğe bağlanmak istiyorum",
        detected_intent="HUMAN_AGENT_REQUEST",
        confidence=0.91,
    )
    ok, missing = validate_handoff_packet(packet)
    assert ok is True
    assert missing == []
    assert packet.get("language_lock") == "en"


def test_validate_handoff_packet_fails_missing_priority():
    packet = build_handoff_packet(
        category="canli_destek",
        priority="",
        customer_phone="+905551112233",
        customer_message="Canlı desteğe bağlanmak istiyorum",
    )
    ok, missing = validate_handoff_packet(packet)
    assert ok is False
    assert "priority" in missing


def test_validate_handoff_packet_fails_invalid_business_hours_type():
    packet = build_handoff_packet(
        category="canli_destek",
        priority="medium",
        customer_phone="+905551112233",
        customer_message="Canlı desteğe bağlanmak istiyorum",
    )
    packet["within_business_hours"] = "yes"
    ok, missing = validate_handoff_packet(packet)
    assert ok is False
    assert "within_business_hours" in missing


def test_validate_handoff_packet_fails_missing_language_lock():
    packet = build_handoff_packet(
        category="canli_destek",
        priority="medium",
        customer_phone="+905551112233",
        customer_message="Canlı desteğe bağlanmak istiyorum",
    )
    packet["language_lock"] = ""
    ok, missing = validate_handoff_packet(packet)
    assert ok is False
    assert "language_lock" in missing
