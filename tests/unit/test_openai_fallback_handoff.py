from __future__ import annotations

import pytest

from app.handlers.openai_fallback_handler import handle_openai_fallback


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeClient:
    def __init__(self, content: str):
        self._content = content

        class _Chat:
            def __init__(self, outer):
                class _Completions:
                    def __init__(self, parent):
                        self._parent = parent

                    def create(self, **_kwargs):
                        return _FakeCompletion(self._parent._content)

                self.completions = _Completions(outer)

        self.chat = _Chat(self)


class _FailingClient:
    def __init__(self):
        class _Completions:
            @staticmethod
            def create(**_kwargs):
                raise TimeoutError("openai timeout")

        class _Chat:
            def __init__(self):
                self.completions = _Completions()

        self.chat = _Chat()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_openai_fallback_promotes_ai_handoff_to_technical_handoff(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-local-test")
    events: dict = {"handoff_notifications": [], "takeover": [], "saved": []}

    async def _notify_admin_handoff(**kwargs):
        events["handoff_notifications"].append(kwargs)

    def _activate_human_takeover(phone: str, reason: str = ""):
        events["takeover"].append((phone, reason))
        return True

    def _response_factory(reply: str, status: str = "ok", **_kwargs):
        return {"reply": reply, "status": status}

    result = await handle_openai_fallback(
        client=_FakeClient("Talebinizi canlı müşteri temsilcimize aktarıyorum."),
        openai_model="gpt-test",
        info_system_prompt="",
        history=[],
        user_message="iade istiyorum",
        phone="905551112233",
        start_time=0.0,
        add_to_history_fn=lambda *_args, **_kwargs: None,
        save_message_fn=lambda *args, **_kwargs: events["saved"].append(args),
        schedule_followup_fn=lambda *_args, **_kwargs: None,
        record_metric_fn=lambda *_args, **_kwargs: None,
        maybe_start_qa_background_fn=lambda *_args, **_kwargs: None,
        qa_enabled=False,
        qa_agent=None,
        admin_phone="",
        send_whatsapp_message_fn=lambda *_args, **_kwargs: None,
        qa_fail_notifications=[],
        record_error_fn=lambda *_args, **_kwargs: None,
        response_factory=_response_factory,
        notify_admin_handoff_fn=_notify_admin_handoff,
        activate_human_takeover_fn=_activate_human_takeover,
    )

    assert result["status"] == "handoff"
    assert len(events["handoff_notifications"]) == 1
    assert events["takeover"] == [("905551112233", "ai_declared_handoff")]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_openai_fallback_keeps_ok_status_when_no_handoff_phrase(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-local-test")
    def _response_factory(reply: str, status: str = "ok", **_kwargs):
        return {"reply": reply, "status": status}

    result = await handle_openai_fallback(
        client=_FakeClient("Yardımcı olayım, giriş ve çıkış tarihinizi paylaşabilir misiniz?"),
        openai_model="gpt-test",
        info_system_prompt="",
        history=[],
        user_message="fiyat alabilir miyim",
        phone="905551112233",
        start_time=0.0,
        add_to_history_fn=lambda *_args, **_kwargs: None,
        save_message_fn=lambda *_args, **_kwargs: None,
        schedule_followup_fn=lambda *_args, **_kwargs: None,
        record_metric_fn=lambda *_args, **_kwargs: None,
        maybe_start_qa_background_fn=lambda *_args, **_kwargs: None,
        qa_enabled=False,
        qa_agent=None,
        admin_phone="",
        send_whatsapp_message_fn=lambda *_args, **_kwargs: None,
        qa_fail_notifications=[],
        record_error_fn=lambda *_args, **_kwargs: None,
        response_factory=_response_factory,
        notify_admin_handoff_fn=None,
        activate_human_takeover_fn=None,
    )

    assert result["status"] == "ok"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_openai_fallback_sanitizes_technical_placeholder_and_booking_contact_block(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-local-test")

    raw_reply = (
        "Size uygun oda tipleri:\n"
        "1. Deluxe - € [fiyat bilgisi için müsaitlik kontrolü yapıyorum, lütfen bekleyiniz]\n\n"
        "Rezervasyonunuzu ilerletebilmem için lütfen:\n"
        "- Adınız ve soyadınız\n"
        "- Telefon numaranız\n"
        "- E-posta adresiniz"
    )

    captured = {"saved": None}

    def _response_factory(reply: str, status: str = "ok", **_kwargs):
        return {"reply": reply, "status": status}

    result = await handle_openai_fallback(
        client=_FakeClient(raw_reply),
        openai_model="gpt-test",
        info_system_prompt="",
        history=[],
        user_message="4 Ağustos giriş 6 Ağustos çıkış fiyat alabilir miyim",
        phone="905551112233",
        start_time=0.0,
        add_to_history_fn=lambda *_args, **_kwargs: None,
        save_message_fn=lambda *_args, **_kwargs: captured.update({"saved": _args[2]}),
        schedule_followup_fn=lambda *_args, **_kwargs: None,
        record_metric_fn=lambda *_args, **_kwargs: None,
        maybe_start_qa_background_fn=lambda *_args, **_kwargs: None,
        qa_enabled=False,
        qa_agent=None,
        admin_phone="",
        send_whatsapp_message_fn=lambda *_args, **_kwargs: None,
        qa_fail_notifications=[],
        record_error_fn=lambda *_args, **_kwargs: None,
        response_factory=_response_factory,
        notify_admin_handoff_fn=None,
        activate_human_takeover_fn=None,
    )

    assert result["status"] == "ok"
    assert "[fiyat bilgisi için" not in result["reply"].lower()
    assert "rezervasyonunuzu ilerletebilmem için" not in result["reply"].lower()
    assert captured["saved"] == result["reply"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_openai_fallback_returns_deterministic_reply_on_exception(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-local-test")
    saved_logs = []

    def _response_factory(reply: str, status: str = "ok", **_kwargs):
        return {"reply": reply, "status": status}

    result = await handle_openai_fallback(
        client=_FailingClient(),
        openai_model="gpt-test",
        info_system_prompt="",
        history=[],
        user_message="Rezervasyon hakkında bilgi alabilir miyim?",
        phone="905551112233",
        start_time=0.0,
        add_to_history_fn=lambda *_args, **_kwargs: None,
        save_message_fn=lambda *_args, **_kwargs: saved_logs.append(_args),
        schedule_followup_fn=lambda *_args, **_kwargs: None,
        record_metric_fn=lambda *_args, **_kwargs: None,
        maybe_start_qa_background_fn=lambda *_args, **_kwargs: None,
        qa_enabled=False,
        qa_agent=None,
        admin_phone="",
        send_whatsapp_message_fn=lambda *_args, **_kwargs: None,
        qa_fail_notifications=[],
        record_error_fn=lambda *_args, **_kwargs: None,
        response_factory=_response_factory,
        notify_admin_handoff_fn=None,
        activate_human_takeover_fn=None,
    )

    assert result["status"] == "fallback_deterministic"
    assert result["reply"]
    assert any("FALLBACK-DETERMINISTIC" in call[2] for call in saved_logs if len(call) >= 3)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_openai_fallback_collapses_booking_contact_block_to_single_step_when_booking_intent(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-local-test")

    raw_reply = (
        "Rezervasyon talebiniz için teşekkür ederim.\n\n"
        "Lütfen rezervasyonunuzu oluşturabilmem için aşağıdaki bilgileri paylaşır mısınız?\n\n"
        "1. Adınız ve soyadınız\n"
        "2. Telefon numaranız\n"
        "3. E-posta adresiniz\n"
        "4. Giriş tarihi\n"
        "5. Çıkış tarihi"
    )

    def _response_factory(reply: str, status: str = "ok", **_kwargs):
        return {"reply": reply, "status": status}

    result = await handle_openai_fallback(
        client=_FakeClient(raw_reply),
        openai_model="gpt-test",
        info_system_prompt="",
        history=[],
        user_message="premium oda rezervasyon yapmak istiyorum",
        phone="905551112233",
        start_time=0.0,
        add_to_history_fn=lambda *_args, **_kwargs: None,
        save_message_fn=lambda *_args, **_kwargs: None,
        schedule_followup_fn=lambda *_args, **_kwargs: None,
        record_metric_fn=lambda *_args, **_kwargs: None,
        maybe_start_qa_background_fn=lambda *_args, **_kwargs: None,
        qa_enabled=False,
        qa_agent=None,
        admin_phone="",
        send_whatsapp_message_fn=lambda *_args, **_kwargs: None,
        qa_fail_notifications=[],
        record_error_fn=lambda *_args, **_kwargs: None,
        response_factory=_response_factory,
        notify_admin_handoff_fn=None,
        activate_human_takeover_fn=None,
    )

    assert result["status"] == "ok"
    assert "adım adım" in result["reply"].lower()
    assert "ad soyad" in result["reply"].lower()
    assert "telefon numaranız" not in result["reply"].lower()
    assert "e-posta adresiniz" not in result["reply"].lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_openai_fallback_collapses_transfer_multi_info_to_single_step(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-local-test")

    raw_reply = (
        "Transfer talebiniz için teşekkürler.\n\n"
        "Lütfen aşağıdaki bilgileri paylaşır mısınız?\n"
        "1. Tarih\n"
        "2. Saat\n"
        "3. Uçuş numarası\n"
        "4. Kişi sayısı\n"
        "5. İsim\n"
        "6. Telefon"
    )

    def _response_factory(reply: str, status: str = "ok", **_kwargs):
        return {"reply": reply, "status": status}

    result = await handle_openai_fallback(
        client=_FakeClient(raw_reply),
        openai_model="gpt-test",
        info_system_prompt="",
        history=[],
        user_message="transfer rezervasyonu yapmak istiyorum",
        phone="905551112233",
        start_time=0.0,
        add_to_history_fn=lambda *_args, **_kwargs: None,
        save_message_fn=lambda *_args, **_kwargs: None,
        schedule_followup_fn=lambda *_args, **_kwargs: None,
        record_metric_fn=lambda *_args, **_kwargs: None,
        maybe_start_qa_background_fn=lambda *_args, **_kwargs: None,
        qa_enabled=False,
        qa_agent=None,
        admin_phone="",
        send_whatsapp_message_fn=lambda *_args, **_kwargs: None,
        qa_fail_notifications=[],
        record_error_fn=lambda *_args, **_kwargs: None,
        response_factory=_response_factory,
        notify_admin_handoff_fn=None,
        activate_human_takeover_fn=None,
    )

    assert result["status"] == "ok"
    assert "adım adım" in result["reply"].lower()
    assert "transfer tarih" in result["reply"].lower()
    assert "uçuş numarası" not in result["reply"].lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_openai_fallback_collapses_restaurant_multi_info_to_single_step(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-local-test")

    raw_reply = (
        "Restoran rezervasyonu için aşağıdaki bilgileri paylaşın:\n"
        "1. Tarih\n"
        "2. Saat\n"
        "3. Kişi sayısı\n"
        "4. İsim\n"
        "5. Telefon"
    )

    def _response_factory(reply: str, status: str = "ok", **_kwargs):
        return {"reply": reply, "status": status}

    result = await handle_openai_fallback(
        client=_FakeClient(raw_reply),
        openai_model="gpt-test",
        info_system_prompt="",
        history=[],
        user_message="restoran için masa ayırtmak istiyorum",
        phone="905551112233",
        start_time=0.0,
        add_to_history_fn=lambda *_args, **_kwargs: None,
        save_message_fn=lambda *_args, **_kwargs: None,
        schedule_followup_fn=lambda *_args, **_kwargs: None,
        record_metric_fn=lambda *_args, **_kwargs: None,
        maybe_start_qa_background_fn=lambda *_args, **_kwargs: None,
        qa_enabled=False,
        qa_agent=None,
        admin_phone="",
        send_whatsapp_message_fn=lambda *_args, **_kwargs: None,
        qa_fail_notifications=[],
        record_error_fn=lambda *_args, **_kwargs: None,
        response_factory=_response_factory,
        notify_admin_handoff_fn=None,
        activate_human_takeover_fn=None,
    )

    assert result["status"] == "ok"
    assert "adım adım" in result["reply"].lower()
    assert "kişi sayısını" in result["reply"].lower()
    assert "telefon" not in result["reply"].lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_openai_fallback_blocks_self_confirmed_reservation_reply(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-local-test")
    events = {"handoff": []}

    async def _notify_admin_handoff(**kwargs):
        events["handoff"].append(kwargs)

    def _response_factory(reply: str, status: str = "ok", **kwargs):
        return {"reply": reply, "status": status, **kwargs}

    history = [
        {"role": "assistant", "content": "📋 REZERVASYON ÖZETİ:\n✅ Onaylamak için 'Evet', iptal için 'Hayır' yazın."},
    ]

    result = await handle_openai_fallback(
        client=_FakeClient("Teşekkür ederim, restoran rezervasyonunuz onaylanmıştır."),
        openai_model="gpt-test",
        info_system_prompt="",
        history=history,
        user_message="Evet",
        phone="905551112233",
        start_time=0.0,
        add_to_history_fn=lambda *_args, **_kwargs: None,
        save_message_fn=lambda *_args, **_kwargs: None,
        schedule_followup_fn=lambda *_args, **_kwargs: None,
        record_metric_fn=lambda *_args, **_kwargs: None,
        maybe_start_qa_background_fn=lambda *_args, **_kwargs: None,
        qa_enabled=False,
        qa_agent=None,
        admin_phone="",
        send_whatsapp_message_fn=lambda *_args, **_kwargs: None,
        qa_fail_notifications=[],
        record_error_fn=lambda *_args, **_kwargs: None,
        response_factory=_response_factory,
        notify_admin_handoff_fn=_notify_admin_handoff,
        activate_human_takeover_fn=lambda *_args, **_kwargs: None,
    )

    assert result["status"] == "handoff"
    assert result["reason_code"] == "reservation_self_confirm_guard"
    assert "kesin onay" in result["reply"].lower()
    assert len(events["handoff"]) == 1
    assert events["handoff"][0]["category"] == "restoran_rezervasyon"
