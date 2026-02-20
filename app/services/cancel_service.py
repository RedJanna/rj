# app/services/cancel_service.py

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
    # "ücretsiz iptal" = fiyat tipi seçimi, gerçek iptal değil
    non_cancel = ["ucretsiz iptal", "ücretsiz iptal", "free cancel", "free cancellation",
                  "iptal edilemez", "iptal edilemeyen"]
    for phrase in non_cancel:
        if phrase in t:
            return False
    kws = ["iptal", "vazgeç", "vazgec", "cancel", "cancellation", "rezervasyon iptal", "rezervasyonu iptal"]
    return any(k in t for k in kws)

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
                return "Hangi rezervasyon olduğunu belirtir misiniz? Örn: restoran / otel / tur / transfer"
            _cancel_state_clear(phone)
            return await _cancel_start_kind_v2(phone, kind, user_message)

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
        return (
            "Otel rezervasyonu iptali için birkaç bilgiye ihtiyacım var:\n"
            "• Misafir adı\n• Giriş tarihi (check-in)\n• Varsa rezervasyon numarası\n\n"
            "Bu bilgileri yazarsanız rezervasyon ekibimiz iptal sürecini başlatacaktır."
        )
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
