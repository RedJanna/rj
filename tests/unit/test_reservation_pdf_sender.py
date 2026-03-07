from __future__ import annotations

import pytest

from app.services.reservation_pdf_sender import build_reservation_pdf_sender


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pdf_sender_upload_payload_and_phone_normalization(monkeypatch, tmp_path):
    pdf_file = tmp_path / "r.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\n%test")
    calls = {"upload_data": None, "message_json": None}

    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, files=None, data=None, json=None):
            if url.endswith("/media"):
                calls["upload_data"] = data
                return _FakeResponse(200, {"id": "media_123"})
            calls["message_json"] = json
            return _FakeResponse(200, {"messages": [{"id": "wamid"}]})

    monkeypatch.setattr("app.services.reservation_pdf_sender.httpx.AsyncClient", _FakeAsyncClient)

    sender = build_reservation_pdf_sender(
        generate_reservation_pdf_fn=lambda _r: str(pdf_file),
        whatsapp_phone_id="123",
        whatsapp_token="token",
    )
    ok = await sender("+90 530 449 84 53", {"id": 99})

    assert ok is True
    assert calls["upload_data"] == {"messaging_product": "whatsapp"}
    assert calls["message_json"]["to"] == "905304498453"
