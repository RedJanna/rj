from pathlib import Path

from app.services.state_store_service import JsonStateRepository
from app.services import transfer_reservation_service as trs


def _reset_repo(tmp_path: Path):
    trs._repo = JsonStateRepository(tmp_path / "transfer_reservations_test.json")


def test_maybe_create_transfer_reservation_from_chat(tmp_path):
    _reset_repo(tmp_path)
    conversation_messages = [
        {
            "user_message": "TK12213, 2 kişi + 1 bebek , 1 bagaj ve bebek koltuğu istemiyorum",
            "bot_reply": (
                "✅ Transfer Özeti:\n"
                "📍 Dalaman Havalimanı → Kassandra Ölüdeniz\n"
                "📅 13 Haziran saat 17:00\n"
                "✈️ Uçuş: TK12213\n"
                "👥 2 yetişkin, 1 bebek\n"
                "🧳 1 bagaj\n"
                "👶 Bebek koltuğu: Hayır\n"
                "💰 Ücret: 75€ (nakit)\n\n"
                "Bu bilgiler doğru mu?"
            ),
        },
        {
            "user_message": "evet",
            "bot_reply": "Transfer talebinizi aldım ve ekibimize ilettim. Şoförümüz havalimanında sizi karşılayacaktır.",
        },
    ]

    created = trs.maybe_create_transfer_reservation_from_chat(
        phone="905551110099",
        user_message=conversation_messages[-1]["user_message"],
        bot_reply=conversation_messages[-1]["bot_reply"],
        conversation_messages=conversation_messages,
    )

    assert created is not None
    assert created["status"] == "pending"
    assert created["flight_no"] == "TK12213"
    assert "13 Haziran" in created["transfer_date"]
    assert created["transfer_time"] == "17:00"


def test_status_alias_and_date_filter(tmp_path):
    _reset_repo(tmp_path)
    trs.create_transfer_reservation(
        customer_phone="905551110001",
        details={
            "transfer_date": "13 Haziran",
            "transfer_time": "17:00",
            "flight_no": "TK1001",
            "guest_text": "2 kişi",
            "luggage_text": "1 bagaj",
            "baby_seat": "Hayır",
            "price_text": "75€",
        },
    )
    r2 = trs.create_transfer_reservation(
        customer_phone="905551110002",
        details={
            "transfer_date": "14 Haziran",
            "transfer_time": "18:00",
            "flight_no": "TK1002",
            "guest_text": "3 kişi",
            "luggage_text": "2 bagaj",
            "baby_seat": "Evet",
            "price_text": "75€",
        },
    )
    trs.update_transfer_reservation_status(r2["id"], status="confirmed")

    all_items = trs.list_transfer_reservations(status="tümü")
    assert len(all_items) == 2

    confirmed = trs.list_transfer_reservations(status="onayli")
    assert len(confirmed) == 1
    assert confirmed[0]["flight_no"] == "TK1002"

    by_date = trs.list_transfer_reservations(status="all", date_query="13 Haziran")
    assert len(by_date) == 1
    assert by_date[0]["flight_no"] == "TK1001"

    by_iso = trs.list_transfer_reservations(status="all", date_query="2026-06-13")
    assert len(by_iso) == 1
    assert by_iso[0]["flight_no"] == "TK1001"

    by_dmy = trs.list_transfer_reservations(status="all", date_query="13/06/2026")
    assert len(by_dmy) == 1
    assert by_dmy[0]["flight_no"] == "TK1001"
