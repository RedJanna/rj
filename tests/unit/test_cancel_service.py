import pytest

from app.services.cancel_service import _is_cancel_intent_v2


@pytest.mark.unit
@pytest.mark.parametrize(
    "message, expected",
    [
        ("Can you share refundable and non-refundable options with cancellation rules?", False),
        ("İptal/iade koşulları nedir?", False),
        ("Non-refundable ve refundable farkı nedir?", False),
        ("Cancel my reservation", True),
        ("Rezervasyonumu iptal etmek istiyorum", True),
    ],
)
def test_cancel_intent_detection_distinguishes_policy_vs_action(message: str, expected: bool):
    assert _is_cancel_intent_v2(message) is expected
