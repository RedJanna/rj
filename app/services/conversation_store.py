import re
import json
import os
from pathlib import Path
from typing import List, Dict
from datetime import datetime, timedelta

# ======================================================
# 7. MESAJ KAYIT SİSTEMİ
# ======================================================

CONVERSATIONS_DIR = Path(
    os.getenv("KASSANDRA_CONVERSATIONS_DIR", "conversations")
).expanduser()
CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_EXPIRY_MINUTES = 10
MAX_HISTORY_MESSAGES = 10

def get_conversation_file(phone: str) -> Path:
    safe_phone = re.sub(r'[^\d]', '', phone)
    return CONVERSATIONS_DIR / f"{safe_phone}.json"

def load_conversation(phone: str) -> dict:
    if not phone:
        return {"phone": None, "messages": [], "created_at": None, "updated_at": None}
    
    file_path = get_conversation_file(phone)
    
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    
    return {
        "phone": phone,
        "messages": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

def clear_conversation(phone: str):
    """
    Belirli bir telefon numarasının konuşma geçmişini temizle.
    Dosyayı silmez, içeriği sıfırlar.
    """
    if not phone:
        return
    
    clean_phone = re.sub(r'[^\d]', '', phone)
    file_path = get_conversation_file(clean_phone)
    
    if file_path.exists():
        try:
            # Dosyayı sil
            file_path.unlink()
            print(f"🗑️ Konuşma geçmişi temizlendi: {clean_phone}")
        except Exception as e:
            print(f"❌ Konuşma temizleme hatası: {e}")

def schedule_conversation_cleanup(phone: str, delay_minutes: int = 5):
    """
    Belirli bir süre sonra konuşma geçmişini temizle.
    Follow-up mesajından sonra çağrılır.
    """
    import threading
    
    def cleanup():
        clear_conversation(phone)
        clear_reservation_flow(phone)
        print(f"🧹 Otomatik temizlik: {phone} - Konuşma + Rezervasyon akışı temizlendi")
    
    # delay_minutes dakika sonra temizle
    timer = threading.Timer(delay_minutes * 60, cleanup)
    timer.daemon = True  # Ana program kapanınca timer'ı da kapat
    timer.start()
    print(f"⏰ Temizlik zamanlandı: {phone} - {delay_minutes} dakika sonra")

def save_conversation(phone: str, conversation: dict):
    """Tüm konuşma nesnesini (dict) JSON olarak kaydeder (cancel state için)."""
    if not phone:
        return
    if not isinstance(conversation, dict):
        return

    conversation.setdefault("phone", phone)
    conversation.setdefault("messages", [])

    now_iso = datetime.now().isoformat()
    if not conversation.get("created_at"):
        conversation["created_at"] = now_iso
    conversation["updated_at"] = now_iso

    file_path = get_conversation_file(phone)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(conversation, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Konuşma kaydetme hatası: {e}")

def save_message(phone: str, user_message: str, bot_reply: str, is_price_template: bool = False):
    if not phone:
        return

    conversation = load_conversation(phone)

    # 10 dakika inaktivite kontrolü — eski konuşmayı sıfırla
    updated_at = conversation.get("updated_at")
    if updated_at and conversation.get("messages"):
        try:
            last_update = datetime.fromisoformat(updated_at)
            if datetime.now() - last_update > timedelta(minutes=HISTORY_EXPIRY_MINUTES):
                conversation["messages"] = []
                conversation["created_at"] = datetime.now().isoformat()
                print(f"🔄 Konuşma süresi doldu, sıfırlandı: {re.sub(r'[^0-9]', '', phone)[:6]}***")
        except (ValueError, TypeError):
            pass

    message_entry = {
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M:%S"),
        "user_message": user_message,
        "bot_reply": bot_reply,
        "is_price_template": is_price_template
    }

    conversation["messages"].append(message_entry)
    conversation["updated_at"] = datetime.now().isoformat()

    file_path = get_conversation_file(phone)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(conversation, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Mesaj kaydetme hatası: {e}")

def get_recent_messages(phone: str, count: int = 10) -> List[dict]:
    if not phone:
        return []

    conversation = load_conversation(phone)

    # 10 dakika inaktivite kontrolü — eski konuşmayı boş döndür
    updated_at = conversation.get("updated_at")
    if updated_at and conversation.get("messages"):
        try:
            last_update = datetime.fromisoformat(updated_at)
            if datetime.now() - last_update > timedelta(minutes=HISTORY_EXPIRY_MINUTES):
                return []
        except (ValueError, TypeError):
            pass

    messages = conversation.get("messages", [])
    recent = messages[-count:] if len(messages) > count else messages

    openai_messages = []
    for msg in recent:
        openai_messages.append({"role": "user", "content": msg["user_message"]})
        openai_messages.append({"role": "assistant", "content": msg["bot_reply"]})

    return openai_messages


# ======================================================
# 8. KONUŞMA GEÇMİŞİ (RAM)
# ======================================================

conversation_history: Dict[str, List[dict]] = {}
last_activity: Dict[str, datetime] = {}

def get_conversation_history(phone: str) -> List[dict]:
    if not phone:
        return []

    if phone in conversation_history:
        if phone in last_activity:
            if datetime.now() - last_activity[phone] > timedelta(minutes=HISTORY_EXPIRY_MINUTES):
                conversation_history.pop(phone, None)
                last_activity.pop(phone, None)
            else:
                return conversation_history[phone]

    recent = get_recent_messages(phone, MAX_HISTORY_MESSAGES)
    if recent:
        conversation_history[phone] = recent
        last_activity[phone] = datetime.now()

    return recent

def add_to_history(phone: str, role: str, content: str):
    if not phone:
        return

    if phone not in conversation_history:
        conversation_history[phone] = []

    conversation_history[phone].append({"role": role, "content": content})

    if len(conversation_history[phone]) > MAX_HISTORY_MESSAGES * 2:
        conversation_history[phone] = conversation_history[phone][-MAX_HISTORY_MESSAGES * 2:]

    last_activity[phone] = datetime.now()


# ======================================================
# 9. TELEFON NUMARASI TAM TEMİZLEME (PURGE)
# ======================================================

def _clean_phone(phone: str) -> str:
    if not phone:
        return ""
    return re.sub(r"[^\d]", "", phone)


def preview_phone_data(phone: str) -> dict:
    """Temizlenecek verilerin önizlemesini döndür."""
    from app.services.price_flow_service import get_price_flow
    from app.services.restaurant_reservation_flow_service import get_reservation_flow, ReservationState
    from app.services.booking_flow_service import get_booking_flow
    from app.services.followup_service import load_followups
    from app.services.access_control_service import is_paused
    from app.services.reminder_service import load_reminders
    from kassandra_fallback_eklenti import load_rate_limits

    clean = _clean_phone(phone)
    if not clean:
        return {"error": "Geçersiz telefon numarası"}

    result = {"phone": clean, "items": {}}

    # Konuşma dosyası
    conv = load_conversation(clean)
    msg_count = len(conv.get("messages", []))
    if msg_count > 0:
        result["items"]["conversation"] = {
            "exists": True,
            "message_count": msg_count,
            "updated_at": conv.get("updated_at")
        }

    # RAM cache
    if clean in conversation_history:
        result["items"]["ram_cache"] = {
            "exists": True,
            "entries": len(conversation_history[clean])
        }

    # Price flow
    pf = get_price_flow(clean)
    if pf and pf.get("state", "idle") != "idle":
        result["items"]["price_flow"] = {"exists": True, "state": pf.get("state")}
    elif pf and pf.get("last_query"):
        result["items"]["price_flow"] = {"exists": True, "state": "last_query only"}

    # Reservation flow
    rf = get_reservation_flow(clean)
    if rf.get("state", ReservationState.IDLE.value) != ReservationState.IDLE.value:
        result["items"]["reservation_flow"] = {"exists": True, "state": rf.get("state")}

    # Booking flow
    bf = get_booking_flow(clean)
    if bf and bf.get("state"):
        result["items"]["booking_flow"] = {"exists": True, "state": bf.get("state")}

    # Follow-up
    followups = load_followups()
    if clean in followups.get("pending", {}):
        result["items"]["followup"] = {"exists": True}

    # Rate limits
    rl_data = load_rate_limits()
    if clean in rl_data.get("limits", {}) or clean in rl_data.get("blocked", {}):
        result["items"]["rate_limit"] = {
            "exists": True,
            "blocked": clean in rl_data.get("blocked", {})
        }

    # Paused
    if is_paused(clean):
        result["items"]["paused"] = {"exists": True}

    # Reminders
    rem_data = load_reminders()
    phone_reminders = [r for r in rem_data.get("scheduled", [])
                       if _clean_phone(r.get("phone", "")) == clean]
    if phone_reminders:
        result["items"]["reminders"] = {"exists": True, "count": len(phone_reminders)}

    result["total_items"] = len(result["items"])
    return result


def purge_phone_data(phone: str, *, hard_delete_bookings: bool = False) -> dict:
    """Telefon numarasına ait TÜM verileri temizle. Sıfırdan konuşma başlat."""
    from app.services.price_flow_service import _load_flows as load_price_flows, _save_flows as save_price_flows
    from app.services.restaurant_reservation_flow_service import clear_reservation_flow
    from app.services.booking_flow_service import purge_booking_flow_data
    from app.services.booking_flow_service import archive_and_delete_bookings_by_phone
    from app.services.followup_service import cancel_followup
    from app.services.access_control_service import resume_conversation
    from app.services.reminder_service import load_reminders, save_reminders
    from app.services.message_id_service import clear_message_ids
    from app.services.routing_state_service import clear_active_flow
    from kassandra_fallback_eklenti import load_rate_limits, save_rate_limits

    clean = _clean_phone(phone)
    if not clean:
        return {"success": False, "error": "Geçersiz telefon numarası"}

    cleared = []

    # 1. Konuşma dosyası
    file_path = get_conversation_file(clean)
    if file_path.exists():
        try:
            file_path.unlink()
            cleared.append("conversation")
        except Exception as e:
            print(f"❌ Konuşma silme hatası: {e}")

    # 2. RAM cache
    if clean in conversation_history:
        del conversation_history[clean]
        cleared.append("ram_cache")
    if clean in last_activity:
        del last_activity[clean]

    # 3. Price flow (last_query dahil tamamen sil)
    pf_data = load_price_flows()
    if clean in pf_data:
        del pf_data[clean]
        save_price_flows(pf_data)
        cleared.append("price_flow")

    # 4. Reservation flow
    try:
        clear_reservation_flow(clean)
        cleared.append("reservation_flow")
    except Exception:
        pass

    # 5. Follow-up
    try:
        cancel_followup(clean)
        cleared.append("followup")
    except Exception:
        pass

    # 5.5 Booking flow (state + offer cache + payment context)
    try:
        if purge_booking_flow_data(clean):
            cleared.append("booking_flow")
    except Exception:
        pass

    # 6. Rate limits (blocked + limits)
    rl_data = load_rate_limits()
    rl_changed = False
    if clean in rl_data.get("blocked", {}):
        del rl_data["blocked"][clean]
        rl_changed = True
    if clean in rl_data.get("limits", {}):
        del rl_data["limits"][clean]
        rl_changed = True
    if rl_changed:
        save_rate_limits(rl_data)
        cleared.append("rate_limits")

    # 7. Paused
    try:
        resume_conversation(clean)
        cleared.append("paused")
    except Exception:
        pass

    # 8. Reminders
    rem_data = load_reminders()
    original_count = len(rem_data.get("scheduled", []))
    rem_data["scheduled"] = [
        r for r in rem_data.get("scheduled", [])
        if _clean_phone(r.get("phone", "")) != clean
    ]
    if len(rem_data["scheduled"]) < original_count:
        save_reminders(rem_data)
        cleared.append("reminders")

    # 9. Message ID store
    try:
        clear_message_ids(clean)
        cleared.append("message_ids")
    except Exception:
        pass

    # 10. Router active flow state
    try:
        clear_active_flow(clean)
        cleared.append("routing_state")
    except Exception:
        pass

    # 11. Hard purge: booking kayıtlarını arşivleyip sil (sadece test/isteğe bağlı)
    if hard_delete_bookings:
        try:
            deleted = archive_and_delete_bookings_by_phone(clean)
            cleared.append(f"hotel_bookings_hard_delete:{deleted}")
        except Exception:
            pass

    print(f"🧹 PURGE tamamlandı: {clean[:6]}*** | Temizlenen: {', '.join(cleared)}")
    return {
        "success": True,
        "phone": clean,
        "hard_delete_bookings": bool(hard_delete_bookings),
        "cleared": cleared,
    }
