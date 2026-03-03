# app/services/cancel_service.py

import re
from datetime import datetime

from app.content.automation_info import get_runtime_text


def init_cancel_service(**deps):
    """
    Ana dosyadaki fonksiyon/ayarları bu modüle enjekte eder.
    Böylece cancel flow, ana dosyaya bağımlı kalmadan çalışır.
    """
    globals().update(deps)


# ======================================================
# CANCEL FLOW (V2) - CUSTOMER CANCELLATION HANDLER
# ======================================================
CANCEL_FLOW_V2_ENABLED = True

_CANCEL_STATE = {}

def _cancel_state_get(phone: str):
    try:
        conv_fn = globals().get("load_conversation")
        if callable(conv_fn):
            c = conv_fn(phone)
            st = c.get("cancel_state_v2")
            if st:
                return st
    except Exception:
        pass
    return _CANCEL_STATE.get(phone)

def _cancel_state_set(phone: str, state: dict):
    _CANCEL_STATE[phone] = state
    try:
        conv_fn = globals().get("load_conversation")
        save_fn = globals().get("save_conversation")
        if callable(conv_fn) and callable(save_fn):
            c = conv_fn(phone)
            c["cancel_state_v2"] = state
            save_fn(phone, c)
    except Exception:
        pass

def _cancel_state_clear(phone: str):
    _CANCEL_STATE.pop(phone, None)
    try:
        conv_fn = globals().get("load_conversation")
        save_fn = globals().get("save_conversation")
        if callable(conv_fn) and callable(save_fn):
            c = conv_fn(phone)
            if "cancel_state_v2" in c:
                del c["cancel_state_v2"]
                save_fn(phone, c)
    except Exception:
        pass

def _is_cancel_intent_v2(text: str) -> bool:
    t = (text or "").lower()
    t_norm = (
        t.replace("ı", "i")
        .replace("ğ", "g")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ü", "u")
        .replace("ç", "c")
    )

    # "ücretsiz iptal / refundable / non-refundable" gibi tarif sorulari gercek iptal niyeti degil.
    non_cancel_terms = [
        "ucretsiz iptal", "free cancellation", "free cancel",
        "iptal edilemez", "non-refundable", "non refundable", "refundable",
        "cancelation policy", "cancellation policy", "cancellation rules",
        "refund policy", "refund rules", "terms and conditions",
        "tarife", "tarif", "rate type", "rate plan",
        "cancelacion", "cancelación", "reembolso",
        "annulation", "remboursement",
        "stornierung", "ruckerstattung", "rückerstattung",
        "cancelamento",
        "отмена", "возврат", "услов",
        "إلغاء", "استرداد",
        "取消", "退款",
        "रद्द", "रिफंड",
    ]

    # Güçlü direkt iptal talebi (sorudan/politikadan ayir).
    direct_cancel_regex = [
        r"\brezervasyonumu iptal\b",
        r"\brezervasyonu iptal\b",
        r"\biptal etmek istiyorum\b",
        r"\biptal edin\b",
        r"\bvazgectim\b",
        r"\bvazgectim\b",
        r"\bcancel my reservation\b",
        r"\bcancel reservation\b",
        r"\bi want to cancel\b",
        r"\bquiero cancelar\b",
        r"\bannuler\b",
        r"\bstornieren\b",
        r"\bcancelar\b",
        r"\bотменить\b",
        r"\bإلغاء\b",
        r"\b取消\b",
        r"\bरद्द\b",
    ]
    if any(re.search(pattern, t_norm, flags=re.IGNORECASE) for pattern in direct_cancel_regex):
        return True

    # Politika/koşul sorularini iptal akışına sokma.
    has_cancel_noun = any(
        token in t_norm
        for token in [
            "iptal", "cancellation", "cancelation", "refund",
            "cancelacion", "cancelación", "annulation",
            "storno", "stornierung", "cancelamento",
            "отмена", "إلغاء", "取消", "रद्द",
        ]
    )
    if has_cancel_noun and any(term in t_norm for term in non_cancel_terms):
        return False

    # Son çare: yalnizca tek basina fiil oldugunda.
    fallback_verbs = [
        r"\bcancel\b",
        r"\bvazgec\b",
        r"\biptal et\b",
        r"\bcancelar\b",
        r"\bannuler\b",
        r"\bstornieren\b",
        r"\bотменить\b",
    ]
    return any(re.search(pattern, t_norm, flags=re.IGNORECASE) for pattern in fallback_verbs)

def _infer_kind_v2(text: str):
    t = (text or "").lower()
    if any(k in t for k in ["restoran", "restaurant", "dinner", "lunch", "breakfast", "kahvalt", "akşam", "aksam", "öğle", "ogle"]):
        return "restaurant"
    if any(k in t for k in ["otel", "hotel", "oda", "konaklama", "check-in", "checkin", "checkout", "giriş", "giris", "çıkış", "cikis"]):
        return "hotel"
    if any(k in t for k in ["transfer", "airport", "havaliman", "dalaman", "flight", "uçuş", "ucus"]):
        return "transfer"
    if any(k in t for k in ["tur", "tour", "aktivite", "activity", "gezi", "excursion"]):
        return "tour"
    return None

def _yes_v2(text: str) -> bool:
    t = (text or "").lower().strip()
    return t in ["evet", "onay", "onaylıyorum", "onayliyorum", "tamam", "yes", "ok", "okay", "confirm"]

def _no_v2(text: str) -> bool:
    t = (text or "").lower().strip()
    return t in ["hayır", "hayir", "no", "vazgeç", "vazgec", "iptal", "cancel", "nope"]

def _fmt_res_v2(i: int, r: dict) -> str:
    rid = r.get("id", "-")
    d = r.get("date", "-")
    tm = r.get("time", "-")
    g = r.get("guest_count", "-")
    n = r.get("customer_name", "-")
    return f"{i}) #{rid} • {d} {tm} • {g} kişi • {n}"


def _extract_hotel_cancel_rez_id(text: str) -> str:
    t = (text or "").lower()
    patterns = [
        r"\brez(?:ervasyon)?\s*id\s*[:#]?\s*([a-z0-9\-.]{4,})\b",
        r"\brez(?:ervasyon)?\s*no\s*[:#]?\s*([a-z0-9\-.]{4,})\b",
        r"\bvoucher\s*(?:no|number)?\s*[:#]?\s*([a-z0-9\-.]{4,})\b",
        r"#\s*([0-9][0-9\.]{3,})\b",
    ]
    for pat in patterns:
        m = re.search(pat, t, flags=re.IGNORECASE)
        if m:
            return (m.group(1) or "").strip()
    return ""


def _extract_hotel_cancel_rate_type(text: str) -> str:
    t = (text or "").lower().strip()
    if t in {"1", "1.", "1-", "1)"}:
        return "iptal_edilemez"
    if t in {"2", "2.", "2-", "2)"}:
        return "ucretsiz_iptal"
    if any(k in t for k in ["iptal edilemez", "non-refundable", "non refundable", "iade edilmez"]):
        return "iptal_edilemez"
    if any(k in t for k in ["ücretsiz iptal", "ucretsiz iptal", "free cancellation", "free cancel", "refundable"]):
        return "ucretsiz_iptal"
    short_token = re.search(r"(?:^|[,;:\-\s])([12])(?:\s*$|\s*(?:\)|\.|,|;))", t)
    if short_token:
        return "iptal_edilemez" if short_token.group(1) == "1" else "ucretsiz_iptal"
    return ""

async def _notify_admin_cancel_v2(reservation, phone: str, reason: str, source: str):
    try:
        send = globals().get("send_whatsapp_message")
        admin = globals().get("ADMIN_PHONE")
        if not callable(send) or not admin:
            return

        if reservation:
            msg = (
                "❌ REZERVASYON İPTAL EDİLDİ\n\n"
                f"🆔 #{reservation.get('id','-')}\n"
                f"📅 {reservation.get('date','-')}  🕐 {reservation.get('time','-')}\n"
                f"👥 {reservation.get('guest_count','-')} kişi\n"
                f"👤 {reservation.get('customer_name','-')}\n"
                f"📱 {reservation.get('customer_phone', phone) or phone}\n"
                f"📌 Kaynak: {source}\n"
                f"📝 Sebep: {reason or '-'}\n"
                f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            msg = (
                "❌ İPTAL TALEBİ (detay gerekiyor)\n\n"
                f"📱 Telefon: {phone}\n"
                f"📌 Kaynak: {source}\n"
                f"📝 Sebep: {reason or '-'}\n"
                f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

        await send(admin, msg)
    except Exception:
        pass

async def handle_cancel_flow_v2(phone: str, user_message: str):
    if not phone or not user_message:
        return None

    t = user_message.strip()
    tl = t.lower()

    st = _cancel_state_get(phone)
    if st:
        step = st.get("step")

        if step == "ask_type":
            kind = _infer_kind_v2(tl)
            if not kind:
                if tl in ["1", "restoran"]:
                    kind = "restaurant"
                elif tl in ["2", "otel"]:
                    kind = "hotel"
                elif tl in ["3", "tur"]:
                    kind = "tour"
                elif tl in ["4", "transfer"]:
                    kind = "transfer"
            if not kind:
                # Eski/yanlış kalan cancel state, normal konuşmayı bloke etmesin.
                if not _is_cancel_intent_v2(tl):
                    _cancel_state_clear(phone)
                    return None
                return "Hangi rezervasyon olduğunu belirtir misiniz? Örn: restoran / otel / tur / transfer"
            _cancel_state_clear(phone)
            return await _cancel_start_kind_v2(phone, kind, user_message)

        if step == "hotel_collect":
            rez_id = (st.get("rez_id") or "").strip()
            rate_type = (st.get("rate_type") or "").strip()
            if not rez_id:
                rez_id = _extract_hotel_cancel_rez_id(tl)
            if not rate_type:
                rate_type = _extract_hotel_cancel_rate_type(tl)

            _cancel_state_set(phone, {"step": "hotel_collect", "rez_id": rez_id, "rate_type": rate_type})

            missing = []
            if not rez_id:
                missing.append("reservation_id_or_voucher_no")
            if not rate_type:
                missing.append("rate_type")
            if missing:
                return get_runtime_text(("hotel_cancel_v1", "messages", "missing_slots"), lang="tr")

            _cancel_state_clear(phone)
            await _notify_admin_cancel_v2(
                None,
                phone,
                f"hotel_cancel_v1 rez_id={rez_id} rate_type={rate_type}",
                "customer_whatsapp_hotel_cancel_v1",
            )
            return get_runtime_text(("hotel_cancel_v1", "messages", "handoff"), lang="tr")

        if step == "pick_restaurant":
            choices = st.get("choices") or {}
            m = re.search(r"#?(\d+)", tl)
            rid = None
            if m:
                token = m.group(1)
                rid = choices.get(token, token)
            if not rid:
                return "Hangi rezervasyonu iptal etmek istersiniz? Listeden numara yazın (örn: 1) veya #id."
            _cancel_state_set(phone, {"step": "confirm_restaurant", "rid": str(rid)})
            return f"Onaylar mısınız: #{rid} numaralı restoran rezervasyonunu iptal edelim mi? (Evet / Hayır)"

        if step == "confirm_restaurant":
            rid = st.get("rid")
            if not rid:
                _cancel_state_clear(phone)
                return None
            if _yes_v2(t):
                _cancel_state_clear(phone)
                try:
                    cancel_fn = globals().get("cancel_reservation")
                    get_fn = globals().get("get_reservation")
                    if callable(cancel_fn):
                        cancel_fn(int(rid), reason="customer_request")
                    reservation = get_fn(int(rid)) if callable(get_fn) else None
                    await _notify_admin_cancel_v2(reservation, phone, "customer_request", "customer_whatsapp")
                except Exception:
                    await _notify_admin_cancel_v2(None, phone, "cancel_failed", "customer_whatsapp")
                return f"✅ Rezervasyonunuz iptal edildi. (#{rid})\nBaşka bir konuda yardımcı olabilir miyim?"
            if _no_v2(t):
                _cancel_state_clear(phone)
                return "Tamam, iptal etmiyorum. Başka bir konuda yardımcı olabilir miyim?"
            return "Lütfen 'Evet' veya 'Hayır' ile cevap verin."

    if not _is_cancel_intent_v2(tl):
        return None

    kind = _infer_kind_v2(tl)
    if not kind:
        _cancel_state_set(phone, {"step": "ask_type"})
        return (
            "Elbette yardımcı olayım. Hangi rezervasyonunuzu iptal etmek istiyorsunuz?\n\n"
            "1) Restoran\n2) Otel\n3) Tur\n4) Transfer\n\n"
            "Lütfen 1-4 yazın veya doğrudan türü yazın."
        )

    return await _cancel_start_kind_v2(phone, kind, user_message)

async def _cancel_start_kind_v2(phone: str, kind: str, original_message: str):
    if kind == "restaurant":
        get_list = globals().get("get_customer_reservations")
        if not callable(get_list):
            _cancel_state_set(phone, {"step": "ask_type"})
            await _notify_admin_cancel_v2(None, phone, "missing_get_customer_reservations", "customer_whatsapp")
            return "Restoran iptali için ekibimize bilgi veriyorum. Lütfen tarih/saat/isim bilgisini yazar mısınız?"

        try:
            all_res = get_list(phone) or []
        except Exception:
            all_res = []

        active = [r for r in all_res if (r.get("status") in ["pending", "confirmed"])]

        try:
            RS = globals().get("ReservationStatus")
            if RS:
                active = [r for r in all_res if (r.get("status") in [RS.PENDING.value, RS.CONFIRMED.value])]
        except Exception:
            pass

        if not active:
            _cancel_state_set(phone, {"step": "ask_type"})
            return "Sistemde aktif restoran rezervasyonu bulamadım. İptal etmek istediğiniz rezervasyon türü: restoran / otel / tur / transfer ?"

        if len(active) == 1:
            rid = active[0].get("id")
            _cancel_state_set(phone, {"step": "confirm_restaurant", "rid": str(rid)})
            return f"Onaylar mısınız: #{rid} numaralı restoran rezervasyonunu iptal edelim mi? (Evet / Hayır)"

        choices = {}
        out = []
        for i, r in enumerate(active, start=1):
            choices[str(i)] = str(r.get("id"))
            out.append(_fmt_res_v2(i, r))
        _cancel_state_set(phone, {"step": "pick_restaurant", "choices": choices})
        return "Hangi restoran rezervasyonunu iptal edelim? Lütfen numara ile cevap verin:\n\n" + "\n".join(out)

    await _notify_admin_cancel_v2(None, phone, original_message[:200], f"customer_whatsapp_{kind}")

    if kind == "hotel":
        rez_id = _extract_hotel_cancel_rez_id(original_message)
        rate_type = _extract_hotel_cancel_rate_type(original_message)
        _cancel_state_set(phone, {"step": "hotel_collect", "rez_id": rez_id, "rate_type": rate_type})
        if rez_id and rate_type:
            _cancel_state_clear(phone)
            await _notify_admin_cancel_v2(
                None,
                phone,
                f"hotel_cancel_v1 rez_id={rez_id} rate_type={rate_type}",
                "customer_whatsapp_hotel_cancel_v1",
            )
            return get_runtime_text(("hotel_cancel_v1", "messages", "handoff"), lang="tr")
        return get_runtime_text(("hotel_cancel_v1", "messages", "start"), lang="tr")
    if kind == "transfer":
        return (
            "Transfer iptali için lütfen şunları paylaşır mısınız?\n"
            "• Tarih\n• Uçuş no / iniş saati\n• Kişi sayısı\n\n"
            "Bu bilgileri yazarsanız ekibimiz iptal sürecini başlatacaktır."
        )
    if kind == "tour":
        return (
            "Tur/aktivite iptali için lütfen şunları paylaşır mısınız?\n"
            "• Tur/aktivite adı\n• Tarih\n• Kişi sayısı\n\n"
            "Bu bilgileri yazarsanız ekibimiz iptal sürecini başlatacaktır."
        )

    _cancel_state_set(phone, {"step": "ask_type"})
    return "Hangi rezervasyon olduğunu belirtir misiniz? Örn: restoran / otel / tur / transfer"


# === CANCEL_FLOW_V2 ===
