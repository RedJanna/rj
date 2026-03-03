from app.routes.chat_routes import (
    _extract_whatsapp_inbound_messages,
    _should_forward_reply,
)


def test_extract_whatsapp_inbound_messages_text() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.TEST123",
                                    "from": "+1 (555) 165-9223",
                                    "text": {"body": "Merhaba"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    out = _extract_whatsapp_inbound_messages(payload)
    assert out == [
        {
            "phone": "15551659223",
            "message": "Merhaba",
            "message_id": "wamid.TEST123",
        }
    ]


def test_extract_whatsapp_inbound_messages_ignores_status_only_payload() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {
                                    "id": "wamid.SENT1",
                                    "status": "sent",
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    assert _extract_whatsapp_inbound_messages(payload) == []


def test_should_forward_reply_filters_duplicates_and_empty() -> None:
    assert _should_forward_reply("ok", "cevap") is True
    assert _should_forward_reply("duplicate_message_id", "cevap") is False
    assert _should_forward_reply("duplicate", "cevap") is False
    assert _should_forward_reply("empty", "cevap") is False
    assert _should_forward_reply("ok", "") is False
