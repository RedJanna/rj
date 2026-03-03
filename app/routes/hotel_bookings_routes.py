"""Hotel booking admin routes extracted from the legacy monolith."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import APIRouter, Body
from fastapi.responses import HTMLResponse


def _format_exception_detail(exc: Exception, max_len: int = 800) -> str:
    detail = str(exc or "").strip()
    if not detail:
        detail = repr(exc).strip()
    if not detail:
        detail = f"{exc.__class__.__name__} (empty error message)"
    elif exc.__class__.__name__ not in detail:
        detail = f"{exc.__class__.__name__}: {detail}"
    return detail[:max_len]


def _fmt_amount(value: Any) -> str:
    try:
        v = float(value)
    except Exception:
        return str(value)
    if abs(v - int(v)) < 1e-9:
        return str(int(v))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _extract_elektra_amount(payload: Any) -> Optional[float]:
    if not isinstance(payload, dict):
        return None

    keys = [
        "_final-request-total-price",
        "total-price",
        "total_price",
        "discounted-price",
        "discounted_price",
        "price",
    ]
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue

    for container_key in ("data", "result", "reservation", "booking"):
        nested = payload.get(container_key)
        if isinstance(nested, dict):
            amount = _extract_elektra_amount(nested)
            if amount is not None:
                return amount

    return None


def build_hotel_bookings_router(
    get_pending_hotel_bookings_fn: Callable[[], Any],
    get_all_hotel_bookings_fn: Callable[[int], Any],
    get_hotel_booking_stats_fn: Callable[[], Any],
    get_hotel_booking_fn: Callable[[int], Dict[str, Any] | None],
    update_hotel_booking_status_fn: Callable[..., Any],
    create_elektraweb_reservation_fn: Callable[..., Awaitable[Dict[str, Any]]],
    send_whatsapp_message_fn: Callable[[str, str], Awaitable[Any]],
    booking_status: Any,
    admin_phone: str,
    create_hotel_booking_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    elektra_config_error_cls: Any = None,
    get_elektraweb_reservation_fn: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
    update_elektraweb_reservation_fn: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
    cancel_elektraweb_reservation_fn: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
    hoteladvisor_select_fn: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
    hoteladvisor_execute_fn: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
    hoteladvisor_function_fn: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
    hoteladvisor_update_fn: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
    get_reservation_guests_fn: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
    save_reservation_guest_fn: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
    get_portal_installments_fn: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
) -> APIRouter:
    router = APIRouter(tags=["hotel-bookings"])

    def _normalize_child_ages(raw_child_ages: Any) -> list[int]:
        out: list[int] = []
        for a in (raw_child_ages or []):
            try:
                ia = int(a)
            except Exception:
                continue
            if 0 <= ia <= 16:
                out.append(ia)
        return out[:4]

    def _child_bucket_counts(child_ages: list[int]) -> Dict[str, int]:
        return {
            "CHD1": len([a for a in child_ages if 6 <= a <= 16]),
            "CHD2": len([a for a in child_ages if 1 <= a <= 5]),
            "BABY": len([a for a in child_ages if a == 0]),
        }

    def _child_age_fields(child_ages: list[int]) -> Dict[str, int]:
        ages = sorted(child_ages)
        return {
            "CHD1AGE": int(ages[0]) if len(ages) > 0 else 0,
            "CHD2AGE": int(ages[1]) if len(ages) > 1 else 0,
            "CHD3AGE": int(ages[2]) if len(ages) > 2 else 0,
            "CHD4AGE": int(ages[3]) if len(ages) > 3 else 0,
        }

    async def _approve_booking_core(booking_id: int, *, bypass_status_check: bool = False):
        booking = get_hotel_booking_fn(booking_id)
        if not booking:
            return {"success": False, "error": "Booking not found"}
        if (not bypass_status_check) and booking["status"] != booking_status.PENDING_APPROVAL:
            return {
                "success": False,
                "error": f"Booking status: {booking['status']} (pending_approval olmali)",
            }

        update_hotel_booking_status_fn(
            booking_id,
            booking_status.APPROVED,
            approved_by="Admin Panel",
            approved_at=datetime.now().isoformat(),
        )

        try:
            child_ages = None
            if booking.get("child_ages"):
                try:
                    child_ages = json.loads(booking["child_ages"])
                except Exception:
                    pass

            effective_price = booking.get("discounted_price") or booking.get("total_price", 0)
            try:
                effective_price = float(effective_price)
            except (TypeError, ValueError):
                effective_price = 0.0

            elektra_resp = await create_elektraweb_reservation_fn(
                hotel_id=booking["hotel_id"],
                from_date=booking["check_in"],
                to_date=booking["check_out"],
                room_type_id=booking["room_type_id"],
                board_type_id=booking["board_type_id"],
                rate_type_id=booking["rate_type_id"],
                rate_code_id=booking["rate_code_id"],
                price_agency_id=booking["price_agency_id"],
                currency_id=booking.get("currency_id", 0),
                currency_code=booking.get("currency", "EUR"),
                total_price=effective_price,
                adult_count=booking["adult_count"],
                child_ages=child_ages,
                guest_first_name=booking["guest_first_name"],
                guest_last_name=booking["guest_last_name"],
                guest_title_id=booking.get("guest_title_id", 0),  # 0=MR default
                guest_phone=booking.get("guest_phone", ""),
                guest_email=booking.get("guest_email", ""),
                special_requests=booking.get("special_requests", ""),
                is_refundable=bool(booking.get("is_refundable", False)),
            )

            elektra_res_id = elektra_resp.get("reservation-id") or elektra_resp.get("id") or ""
            voucher_no = str(
                elektra_resp.get("voucher-no")
                or elektra_resp.get("voucherno")
                or ""
            ).strip()
            confirmation_url = elektra_resp.get("confirmation-url") or elektra_resp.get("confirmationUrl") or ""
            effective_elektra_resp = elektra_resp

            if get_elektraweb_reservation_fn and (elektra_res_id or voucher_no):
                try:
                    fetched = await get_elektraweb_reservation_fn(
                        hotel_id=booking["hotel_id"],
                        reservation_id=elektra_res_id or None,
                        voucher_no=voucher_no or None,
                    )
                    if isinstance(fetched, dict) and fetched:
                        effective_elektra_resp = fetched
                        voucher_no = str(
                            fetched.get("voucher-no")
                            or fetched.get("voucherno")
                            or voucher_no
                        ).strip()
                        confirmation_url = (
                            fetched.get("confirmation-url")
                            or fetched.get("confirmationUrl")
                            or confirmation_url
                        )
                except Exception as fetch_exc:
                    print(f"[ELEKTRA] WARN: getReservation after create failed: {fetch_exc}")

            if not voucher_no and str(elektra_res_id).strip():
                voucher_no = str(elektra_res_id).strip()
                print(
                    "[PAYMENT] voucher-no missing after create, fallback to reservation-id | "
                    f"booking_id={booking_id} reservation_id={elektra_res_id}"
                )

            pax_sync_status = "skipped"
            pax_sync_error = ""
            if hoteladvisor_update_fn and str(elektra_res_id).strip():
                try:
                    normalized_child_ages = _normalize_child_ages(child_ages)
                    row = {
                        "ID": int(elektra_res_id),
                        "HOTELID": int(booking["hotel_id"]),
                        "ADULT": int(booking.get("adult_count") or 0),
                    }
                    row.update(_child_bucket_counts(normalized_child_ages))
                    row.update(_child_age_fields(normalized_child_ages))
                    pax_update_payload = {
                        "Row": row,
                        "SelectAfterUpdate": [
                            "ID", "HOTELID", "ADULT", "CHD1", "CHD2", "BABY",
                            "CHD1AGE", "CHD2AGE", "CHD3AGE", "CHD4AGE",
                        ],
                    }
                    pax_resp = await hoteladvisor_update_fn(name="HOTEL_RES", payload=pax_update_payload)
                    pax_sync_status = "ok"
                    print(
                        "[ELEKTRA] pax sync after create OK | "
                        f"booking_id={booking_id} res_id={elektra_res_id} "
                        f"payload={json.dumps(pax_update_payload, ensure_ascii=False)} "
                        f"resp={json.dumps(pax_resp, ensure_ascii=False)[:500]}"
                    )
                except Exception as pax_exc:
                    pax_sync_status = "failed"
                    pax_sync_error = _format_exception_detail(pax_exc, 500)
                    print(
                        "[ELEKTRA] WARN: pax sync after create failed | "
                        f"booking_id={booking_id} res_id={elektra_res_id} err={pax_sync_error}"
                    )

            price = (
                _extract_elektra_amount(effective_elektra_resp)
                or _extract_elektra_amount(elektra_resp)
                or booking.get("discounted_price")
                or booking.get("total_price", 0)
            )
            update_hotel_booking_status_fn(
                booking_id,
                booking_status.ELEKTRA_CREATED,
                elektra_reservation_id=str(elektra_res_id),
                total_price=float(price),
                discounted_price=float(price),
                elektra_response=json.dumps(effective_elektra_resp, ensure_ascii=False)[:2000],
                admin_notes=(
                    f"pax_sync={pax_sync_status}"
                    + (f" err={pax_sync_error}" if pax_sync_error else "")
                )[:500],
            )

            print(f"[ELEKTRA] createReservation FULL response: {json.dumps(effective_elektra_resp, ensure_ascii=False)[:3000]}")

            lang = booking.get("lang", "tr")
            guest_name = f"{booking.get('guest_first_name', '')} {booking.get('guest_last_name', '')}".strip()
            last_name = booking.get("guest_last_name", "")
            check_in = booking.get("check_in", "")
            room_type_id = booking.get("room_type_id", "")

            payment_link = ""
            if voucher_no:
                payment_link = (
                    f"https://kassandra-butik-otel.rezervasyonal.com/Online"
                    f"?Voucherno={voucher_no}"
                    f"&LastName={last_name}"
                    f"&CheckInDate={check_in}"
                    f"&RoomTypeId={room_type_id}"
                    f"&submit=true&redirect=Deposit"
                )

            if lang == "en":
                msg = (
                    f"Great news, {guest_name}! Your reservation is confirmed.\n\n"
                    f"🆔 Reservation number: {elektra_res_id or '-'}\n"
                    f"🎫 Voucher No: {voucher_no or '-'}\n"
                    f"Room: {booking.get('room_type_display', booking.get('room_type', ''))}\n"
                    f"Check-in: {check_in}\n"
                    f"Check-out: {booking.get('check_out', '')}\n"
                    f"Price: {price} {booking.get('currency', 'EUR')}\n\n"
                    f"A deposit is required for confirmation.\n"
                    f"How would you like to make the payment?\n\n"
                    f"1) Payment link (Credit/Debit card)\n"
                    f"2) Bank transfer (EFT/Wire)\n\n"
                    f"Please choose your preferred payment method."
                )
            else:
                msg = (
                    f"✅ Sayın {guest_name}, rezervasyonunuz oluşturuldu.\n\n"
                    f"🆔 Rezervasyon numarası: {elektra_res_id or '-'}\n"
                    f"🎫 Voucher No: {voucher_no or '-'}\n"
                    f"🛏️ Oda: {booking.get('room_type_display', booking.get('room_type', ''))}\n"
                    f"📅 Giriş: {check_in}\n"
                    f"📅 Çıkış: {booking.get('check_out', '')}\n"
                    f"💶 Toplam Fiyat: {_fmt_amount(price)} {booking.get('currency', 'EUR')}\n\n"
                    f"Rezervasyonun kesinleşmesi için ön ödeme gerekmektedir.\n"
                    f"Lütfen ödeme yönteminizi seçin:\n\n"
                    f"1) Ödeme linki (Kredi/Banka kartı)\n"
                    f"2) Havale/EFT\n\n"
                    f"Tercihinizi 1 veya 2 olarak iletebilirsiniz."
                )
            await send_whatsapp_message_fn(booking["customer_phone"], msg)

            if confirmation_url:
                if lang == "en":
                    conf_msg = f"Your reservation confirmation form:\n{confirmation_url}"
                else:
                    conf_msg = f"Rezervasyon onay formunuz:\n{confirmation_url}"
                await send_whatsapp_message_fn(booking["customer_phone"], conf_msg)

            return {
                "success": True,
                "message": "ElektraWeb'de olusturuldu, musteri bilgilendirildi",
                "elektra_reservation_id": str(elektra_res_id),
                "voucher_no": str(voucher_no),
                "payment_link": payment_link,
            }
        except Exception as e:
            error_detail = _format_exception_detail(e, 800)
            error_code = "ELEKTRA_API_ERROR"
            error_message = f"ElektraWeb API hatasi: {error_detail}"
            if elektra_config_error_cls and isinstance(e, elektra_config_error_cls):
                if "ELEKTRA_WALKIN_AGENCY_ID" in error_detail:
                    error_code = "ELEKTRA_CONFIG_MISSING_WALKIN"
                    error_message = (
                        "Elektra ayari eksik: ELEKTRA_WALKIN_AGENCY_ID tanimlanmali "
                        "(WALKIN acenta id)."
                    )
                else:
                    error_code = "ELEKTRA_CONFIG_ERROR"
                    error_message = f"Elektra config hatasi: {error_detail}"

            update_hotel_booking_status_fn(
                booking_id,
                booking_status.ELEKTRA_FAILED,
                elektra_response=_format_exception_detail(e, 500),
            )
            await send_whatsapp_message_fn(
                admin_phone,
                f"ELEKTRA HATA: Booking #{booking_id} olusturulamadi!\nHata: {error_detail}",
            )
            return {
                "success": False,
                "error_code": error_code,
                "error": error_message,
                "error_detail": error_detail,
            }

    def _parse_child_ages_csv(raw: Any) -> list[int]:
        if raw is None:
            return []
        if isinstance(raw, list):
            src = raw
        else:
            txt = str(raw).strip()
            if not txt:
                return []
            src = [x.strip() for x in txt.split(",")]
        out: list[int] = []
        for x in src:
            try:
                age = int(x)
            except Exception:
                continue
            if 0 <= age <= 16:
                out.append(age)
        return out[:4]

    def _calc_nights(check_in: str, check_out: str) -> int:
        try:
            d1 = datetime.strptime(check_in, "%Y-%m-%d")
            d2 = datetime.strptime(check_out, "%Y-%m-%d")
            return max(1, (d2 - d1).days)
        except Exception:
            return 1

    def _normalize_phone(phone: Any) -> str:
        return "".join(ch for ch in str(phone or "") if ch.isdigit())

    def _normalize_room_text(text: Any) -> str:
        t = str(text or "").lower().strip()
        t = t.replace("ı", "i").replace("ğ", "g").replace("ş", "s").replace("ö", "o").replace("ü", "u").replace("ç", "c")
        t = re.sub(r"[^a-z0-9]+", " ", t)
        return re.sub(r"\s+", " ", t).strip()

    def _find_template_booking_by_phone(phone: str) -> Optional[Dict[str, Any]]:
        clean = _normalize_phone(phone)
        if not clean:
            return None
        last10 = clean[-10:]
        candidates = get_all_hotel_bookings_fn(200) or []
        for b in candidates:
            b_phone = _normalize_phone(b.get("customer_phone") or b.get("guest_phone"))
            if not b_phone.endswith(last10):
                continue
            if int(b.get("room_type_id") or 0) <= 0:
                continue
            if int(b.get("board_type_id") or 0) <= 0:
                continue
            if int(b.get("rate_type_id") or 0) <= 0:
                continue
            if int(b.get("rate_code_id") or 0) <= 0:
                continue
            if int(b.get("price_agency_id") or 0) <= 0:
                continue
            return b
        return None

    def _extract_booking_refs(booking: Dict[str, Any]) -> tuple[str, str]:
        reservation_id = str(booking.get("elektra_reservation_id") or "").strip()
        voucher_no = ""
        raw = booking.get("elektra_response")
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    if not reservation_id:
                        reservation_id = str(data.get("reservation-id") or data.get("id") or "").strip()
                    voucher_no = str(data.get("voucher-no") or data.get("voucherno") or "").strip()
            except Exception:
                pass
        return reservation_id, voucher_no

    def _collect_dict_rows(node: Any) -> list[Dict[str, Any]]:
        rows: list[Dict[str, Any]] = []

        def _walk(x: Any) -> None:
            if isinstance(x, dict):
                if x:
                    rows.append(x)
                for v in x.values():
                    if isinstance(v, (dict, list)):
                        _walk(v)
            elif isinstance(x, list):
                for it in x:
                    if isinstance(it, (dict, list)):
                        _walk(it)

        _walk(node)
        return rows

    def _extract_rates(raw: Any) -> Dict[str, float]:
        rates: Dict[str, float] = {}
        for r in _collect_dict_rows(raw):
            cur = str(
                r.get("CURRENCY")
                or r.get("currency")
                or r.get("CURCODE")
                or r.get("curcode")
                or r.get("CURRENCYCODE")
                or r.get("currencycode")
                or ""
            ).strip().upper()
            rv_raw = r.get("RATE") if r.get("RATE") is not None else r.get("rate")
            try:
                rv = float(rv_raw)
            except Exception:
                continue
            if cur and rv > 0:
                rates[cur] = rv
        return rates

    @router.get("/admin/hotel-bookings/pending")
    async def get_pending_bookings_api():
        return {"bookings": get_pending_hotel_bookings_fn()}

    @router.get("/admin/hotel-bookings/all")
    async def get_all_bookings_api(limit: int = 50):
        return {"bookings": get_all_hotel_bookings_fn(limit)}

    @router.get("/admin/hotel-bookings/stats")
    async def hotel_booking_stats_api():
        return get_hotel_booking_stats_fn()

    @router.get("/admin/hotel-bookings/{booking_id}")
    async def get_booking_api(booking_id: int):
        booking = get_hotel_booking_fn(booking_id)
        if not booking:
            return {"error": "Booking not found"}
        return booking

    @router.post("/admin/hotel-bookings/{booking_id}/approve")
    async def approve_booking_api(booking_id: int):
        return await _approve_booking_core(booking_id)

    @router.post("/admin/hotel-bookings/{booking_id}/reject")
    async def reject_booking_api(booking_id: int, reason: str = ""):
        booking = get_hotel_booking_fn(booking_id)
        if not booking:
            return {"success": False, "error": "Booking not found"}

        update_hotel_booking_status_fn(
            booking_id,
            booking_status.REJECTED,
            rejected_by="Admin Panel",
            rejected_at=datetime.now().isoformat(),
            rejection_reason=reason,
        )

        lang = booking.get("lang", "tr")
        if lang == "en":
            msg = "We're sorry, but we couldn't accommodate your reservation at this time. Would you like us to help with an alternative?"
        else:
            msg = "Maalesef rezervasyon talebiniz su anda karsilanamamaktadir. Size alternatif sunmamizi ister misiniz?"

        await send_whatsapp_message_fn(booking["customer_phone"], msg)
        return {"success": True, "message": "Reddedildi, musteri bilgilendirildi"}

    @router.post("/admin/hotel-bookings/{booking_id}/retry")
    async def retry_booking_api(booking_id: int):
        booking = get_hotel_booking_fn(booking_id)
        if not booking:
            return {"success": False, "error": "Booking not found"}
        allowed_retry_statuses = {booking_status.ELEKTRA_FAILED, booking_status.APPROVED}
        if booking["status"] not in allowed_retry_statuses:
            return {
                "success": False,
                "error": "Sadece basarisiz veya takili (approved) bookinglar tekrar denenebilir",
            }

        return await _approve_booking_core(booking_id, bypass_status_check=True)

    @router.post("/admin/hotel-bookings/{booking_id}/recreate")
    async def recreate_booking_api(booking_id: int):
        if not create_hotel_booking_fn:
            return {"success": False, "error": "Booking create fonksiyonu bagli degil"}
        source = get_hotel_booking_fn(booking_id)
        if not source:
            return {"success": False, "error": "Booking not found"}
        if source.get("status") == booking_status.PENDING_APPROVAL:
            return {"success": False, "error": "Bu kayit zaten pending_approval"}

        child_ages = []
        try:
            child_ages = json.loads(source.get("child_ages") or "[]")
            if not isinstance(child_ages, list):
                child_ages = []
        except Exception:
            child_ages = []

        booking_data = {
            "customer_phone": source.get("customer_phone", ""),
            "guest_first_name": source.get("guest_first_name", ""),
            "guest_last_name": source.get("guest_last_name", ""),
            "guest_title_id": int(source.get("guest_title_id") or 1),
            "hotel_id": int(source.get("hotel_id") or int(os.getenv("ELEKTRA_HOTEL_ID", "21966"))),
            "check_in": source.get("check_in", ""),
            "check_out": source.get("check_out", ""),
            "nights": int(source.get("nights") or _calc_nights(source.get("check_in", ""), source.get("check_out", ""))),
            "adult_count": int(source.get("adult_count") or 1),
            "child_ages": child_ages,
            "room_type": source.get("room_type", ""),
            "room_type_display": source.get("room_type_display", ""),
            "room_type_id": int(source.get("room_type_id") or 0),
            "board_type_id": int(source.get("board_type_id") or 0),
            "rate_type_id": int(source.get("rate_type_id") or 0),
            "rate_code_id": int(source.get("rate_code_id") or 0),
            "price_agency_id": int(source.get("price_agency_id") or 0),
            "currency_id": int(source.get("currency_id") or 44),
            "currency": str(source.get("currency") or "EUR"),
            "total_price": float(source.get("total_price") or 0.0),
            "discounted_price": float(source.get("discounted_price") or source.get("total_price") or 0.0),
            "is_refundable": bool(source.get("is_refundable")),
            "special_requests": source.get("special_requests", ""),
            "guest_phone": source.get("guest_phone") or source.get("customer_phone") or "",
            "guest_email": source.get("guest_email", ""),
            "lang": source.get("lang") or "tr",
        }

        created = create_hotel_booking_fn(booking_data)
        new_id = int(created.get("id") or 0)
        if new_id > 0:
            update_hotel_booking_status_fn(
                new_id,
                booking_status.PENDING_APPROVAL,
                admin_notes=f"Admin recreate from #{booking_id} at {datetime.now().isoformat()}",
            )
        return {
            "success": True,
            "message": "Yeni pending booking olusturuldu",
            "source_booking_id": booking_id,
            "new_booking_id": new_id,
        }

    @router.post("/admin/hotel-bookings/manual-create")
    async def manual_create_booking_api(payload: Optional[Dict[str, Any]] = Body(default=None)):
        if not create_hotel_booking_fn:
            return {"success": False, "error": "Booking create fonksiyonu bagli degil"}
        data = dict(payload or {})

        source_booking_id = data.get("source_booking_id")
        source_booking = None
        if source_booking_id:
            try:
                source_booking = get_hotel_booking_fn(int(source_booking_id))
            except Exception:
                source_booking = None
            if not source_booking:
                return {"success": False, "error": "source_booking_id bulunamadi"}
        if not source_booking:
            source_booking = _find_template_booking_by_phone(data.get("customer_phone"))

        def _pick(key: str, default: Any = None):
            if key in data and data.get(key) not in (None, ""):
                return data.get(key)
            if source_booking and source_booking.get(key) not in (None, ""):
                return source_booking.get(key)
            return default

        check_in = str(_pick("check_in", "")).strip()
        check_out = str(_pick("check_out", "")).strip()
        if not check_in or not check_out:
            return {"success": False, "error": "check_in ve check_out zorunlu (YYYY-MM-DD)"}

        child_ages = _parse_child_ages_csv(_pick("child_ages", []))
        try:
            adult_count = max(1, int(_pick("adult_count", 1)))
        except Exception:
            adult_count = 1

        booking_data = {
            "customer_phone": str(_pick("customer_phone", "")).strip(),
            "guest_first_name": str(_pick("guest_first_name", "")).strip(),
            "guest_last_name": str(_pick("guest_last_name", "")).strip(),
            "guest_title_id": int(_pick("guest_title_id", 1) or 1),
            "hotel_id": int(_pick("hotel_id", int(os.getenv("ELEKTRA_HOTEL_ID", "21966"))) or int(os.getenv("ELEKTRA_HOTEL_ID", "21966"))),
            "check_in": check_in,
            "check_out": check_out,
            "nights": _calc_nights(check_in, check_out),
            "adult_count": adult_count,
            "child_ages": child_ages,
            "room_type": str(_pick("room_type", "manual_test")).strip(),
            "room_type_display": str(_pick("room_type_display", "Manual Test Room")).strip(),
            "room_type_id": int(_pick("room_type_id", 0) or 0),
            "board_type_id": int(_pick("board_type_id", 0) or 0),
            "rate_type_id": int(_pick("rate_type_id", 0) or 0),
            "rate_code_id": int(_pick("rate_code_id", 0) or 0),
            "price_agency_id": int(_pick("price_agency_id", int(os.getenv("ELEKTRA_WALKIN_AGENCY_ID", "0") or 0)) or 0),
            "currency_id": int(_pick("currency_id", 44) or 44),
            "currency": str(_pick("currency", "EUR")).strip().upper() or "EUR",
            "total_price": float(_pick("total_price", 0) or 0.0),
            "discounted_price": float(_pick("discounted_price", _pick("total_price", 0)) or 0.0),
            "is_refundable": bool(_pick("is_refundable", False)),
            "special_requests": str(_pick("special_requests", "MANUAL TEST")).strip(),
            "guest_phone": str(_pick("guest_phone", _pick("customer_phone", ""))).strip(),
            "guest_email": str(_pick("guest_email", "")).strip(),
            "lang": str(_pick("lang", "tr")).strip() or "tr",
        }

        required = ["customer_phone", "guest_first_name", "guest_last_name", "room_type_id", "board_type_id", "rate_type_id", "rate_code_id", "price_agency_id"]
        missing = [k for k in required if not booking_data.get(k)]
        if missing:
            return {"success": False, "error": f"Eksik zorunlu alanlar: {', '.join(missing)}"}

        created = create_hotel_booking_fn(booking_data)
        new_id = int(created.get("id") or 0)
        if new_id > 0:
            note_src = f"source=#{source_booking_id}" if source_booking_id else "source=manual"
            update_hotel_booking_status_fn(
                new_id,
                booking_status.PENDING_APPROVAL,
                admin_notes=f"Admin manual create ({note_src}) at {datetime.now().isoformat()}",
            )
        return {
            "success": True,
            "message": "Manual test booking olusturuldu",
            "booking_id": new_id,
        }

    @router.post("/admin/hotel-bookings/manual-quote-fill")
    async def manual_quote_fill_api(payload: Optional[Dict[str, Any]] = Body(default=None)):
        data = dict(payload or {})
        from_date = str(data.get("check_in") or "").strip()
        to_date = str(data.get("check_out") or "").strip()
        room_hint = str(data.get("room_type_display") or "").strip()
        currency = str(data.get("currency") or "EUR").strip().upper() or "EUR"
        try:
            adult = max(1, int(data.get("adult_count") or 1))
        except Exception:
            adult = 1
        child_ages = _parse_child_ages_csv(data.get("child_ages", ""))
        is_refundable = data.get("is_refundable")
        if isinstance(is_refundable, str):
            is_refundable = is_refundable.strip().lower() in {"1", "true", "yes", "evet"}
        elif not isinstance(is_refundable, bool):
            is_refundable = None
        if not from_date or not to_date:
            return {"success": False, "error": "check_in ve check_out zorunlu"}

        try:
            from app.services.elektraweb_booking_service import fetch_price

            hotel_id = int(os.getenv("ELEKTRA_HOTEL_ID", "21966"))
            raw = await fetch_price(
                hotel_id=str(hotel_id),
                from_date=from_date,
                to_date=to_date,
                adult=adult,
                child_ages=child_ages or None,
                currency=currency,
                language="tr",
                timeout_sec=20,
            )
            offers = []
            if isinstance(raw, list):
                offers = [x for x in raw if isinstance(x, dict)]
            elif isinstance(raw, dict):
                for k in ("data", "result", "offers", "items", "rows"):
                    v = raw.get(k)
                    if isinstance(v, list):
                        offers = [x for x in v if isinstance(x, dict)]
                        break

            exp_elder = len([a for a in child_ages if 6 <= a <= 16])
            exp_younger = len([a for a in child_ages if 1 <= a <= 5])
            exp_baby = len([a for a in child_ages if a == 0])
            room_hint_n = _normalize_room_text(room_hint)

            best = None
            best_score = -10_000
            ranked: list[tuple[int, Dict[str, Any], Dict[str, int], str]] = []
            for of in offers:
                score = 0
                room_name = of.get("room-type") or of.get("room_type") or of.get("room-name") or ""
                room_name_n = _normalize_room_text(room_name)
                if room_hint_n and room_name_n:
                    if room_hint_n in room_name_n or room_name_n in room_hint_n:
                        score += 30
                pax = of.get("pax-count") if isinstance(of.get("pax-count"), dict) else {}
                pa = int((pax or {}).get("adult") or 0)
                pe = int((pax or {}).get("elder-child-count") or 0)
                py = int((pax or {}).get("younger-child-count") or 0)
                pb = int((pax or {}).get("baby-count") or 0)
                pax_view = {"adult": pa, "elder-child-count": pe, "younger-child-count": py, "baby-count": pb}
                if pa == adult and pe == exp_elder and py == exp_younger and pb == exp_baby:
                    score += 100
                else:
                    score -= 100
                cancel = of.get("cancellation-penalty") or {}
                ref = cancel.get("is-refundable")
                if isinstance(is_refundable, bool) and ref is not None:
                    if bool(ref) == bool(is_refundable):
                        score += 5
                    else:
                        score -= 5
                ranked.append((score, of, pax_view, room_name))
                if score > best_score:
                    best = of
                    best_score = score

            if not best or best_score < 0:
                ranked.sort(key=lambda x: x[0], reverse=True)
                suggestions = []
                for score, of, pax_view, room_name in ranked[:5]:
                    p = of.get("discounted-price")
                    if p is None:
                        p = of.get("price")
                    suggestions.append(
                        {
                            "score": score,
                            "room": room_name,
                            "pax": pax_view,
                            "price": p,
                            "room_type_id": int(of.get("room-type-id") or 0),
                            "board_type_id": int(of.get("board-type-id") or 0),
                            "rate_type_id": int(of.get("rate-type-id") or 0),
                            "rate_code_id": int(of.get("rate-code-id") or 0),
                            "price_agency_id": int(of.get("price-agency-id") or 0),
                        }
                    )
                return {
                    "success": False,
                    "error": "Bu kisi dagilimi ve oda icin birebir uygun quote bulunamadi. Farkli oda/fiyat secin.",
                    "requested": {
                        "adult": adult,
                        "elder-child-count": exp_elder,
                        "younger-child-count": exp_younger,
                        "baby-count": exp_baby,
                    },
                    "suggestions": suggestions,
                }

            price = best.get("discounted-price")
            if price is None:
                price = best.get("price")
            return {
                "success": True,
                "fill": {
                    "room_type_id": int(best.get("room-type-id") or 0),
                    "board_type_id": int(best.get("board-type-id") or 0),
                    "rate_type_id": int(best.get("rate-type-id") or 0),
                    "rate_code_id": int(best.get("rate-code-id") or 0),
                    "price_agency_id": int(best.get("price-agency-id") or 0),
                    "total_price": float(price or 0.0),
                    "currency": str(currency),
                    "room_type_display": room_hint or (best.get("room-type") or best.get("room_type") or ""),
                },
                "diagnostic": {
                    "requested": {
                        "adult": adult,
                        "elder-child-count": exp_elder,
                        "younger-child-count": exp_younger,
                        "baby-count": exp_baby,
                    }
                },
            }
        except Exception as e:
            return {"success": False, "error": _format_exception_detail(e, 1200)}

    @router.get("/admin/hotel-bookings/template/by-phone")
    async def get_booking_template_by_phone(phone: str):
        template = _find_template_booking_by_phone(phone)
        if not template:
            return {"success": False, "error": "Bu telefon icin uygun template booking bulunamadi"}
        return {"success": True, "template": template}

    @router.post("/admin/hotel-bookings/{booking_id}/elektra/sync")
    async def sync_elektra_booking_api(booking_id: int):
        if not get_elektraweb_reservation_fn:
            return {"success": False, "error": "Elektra sync fonksiyonu bagli degil"}

        booking = get_hotel_booking_fn(booking_id)
        if not booking:
            return {"success": False, "error": "Booking not found"}

        reservation_id, voucher_no = _extract_booking_refs(booking)
        if not reservation_id and not voucher_no:
            return {"success": False, "error": "Elektra reservation-id/voucher bulunamadi"}

        try:
            elektra_resp = await get_elektraweb_reservation_fn(
                hotel_id=booking["hotel_id"],
                reservation_id=reservation_id or None,
                voucher_no=voucher_no or None,
            )
            resolved_res_id = (
                elektra_resp.get("reservation-id")
                or elektra_resp.get("id")
                or reservation_id
            )

            update_hotel_booking_status_fn(
                booking_id,
                booking.get("status", booking_status.APPROVED),
                elektra_reservation_id=str(resolved_res_id or ""),
                elektra_response=json.dumps(elektra_resp, ensure_ascii=False)[:4000],
                admin_notes=f"Elektra senkron: {datetime.now().isoformat()}",
            )
            return {
                "success": True,
                "message": "Elektra rezervasyon bilgisi guncellendi",
                "elektra_reservation_id": str(resolved_res_id or ""),
                "elektra_response": elektra_resp,
            }
        except Exception as e:
            err_text = _format_exception_detail(e, 2000)
            # Bazi tenantlarda getReservation endpoint'i bulunmuyor (404 tum adaylar).
            # Bu durumda mevcut local Elektra response ile soft-success don.
            if "HTTP 404" in err_text and "failed for all endpoint candidates" in err_text:
                cached_raw = booking.get("elektra_response")
                cached_data: Dict[str, Any] = {}
                if cached_raw:
                    try:
                        parsed = json.loads(cached_raw)
                        if isinstance(parsed, dict):
                            cached_data = parsed
                    except Exception:
                        cached_data = {}

                update_hotel_booking_status_fn(
                    booking_id,
                    booking.get("status", booking_status.APPROVED),
                    admin_notes=(
                        "Elektra senkron (soft): tenant getReservation endpoint'i bulunamadi, "
                        f"local cache kullanildi. {datetime.now().isoformat()}"
                    ),
                )
                return {
                    "success": True,
                    "soft_fallback": True,
                    "message": "Tenant getReservation endpoint'i bulunamadi, local cache gosteriliyor.",
                    "elektra_reservation_id": reservation_id,
                    "elektra_response": cached_data,
                    "warning": err_text[:1000],
                }

            return {"success": False, "error": err_text[:1000]}

    @router.post("/admin/hotel-bookings/{booking_id}/elektra/update")
    async def update_elektra_booking_api(
        booking_id: int,
        payload: Optional[Dict[str, Any]] = Body(default=None),
    ):
        if not update_elektraweb_reservation_fn:
            return {"success": False, "error": "Elektra update fonksiyonu bagli degil"}

        booking = get_hotel_booking_fn(booking_id)
        if not booking:
            return {"success": False, "error": "Booking not found"}

        reservation_id, _voucher_no = _extract_booking_refs(booking)
        if not reservation_id:
            return {"success": False, "error": "Elektra reservation-id bulunamadi"}

        try:
            incoming = payload or {}

            def _to_int(v: Any, default: int = 0) -> int:
                try:
                    return int(v)
                except Exception:
                    return int(default)

            def _to_float(v: Any, default: float = 0.0) -> float:
                try:
                    return float(v)
                except Exception:
                    return float(default)

            adult_count = max(1, _to_int(booking.get("adult_count"), 1))
            guest_title_id = _to_int(booking.get("guest_title_id"), 0)  # 0=MR, 1=MS, 2=CHILD, 3=BABY
            guest_first_name = str(booking.get("guest_first_name") or "")
            guest_last_name = str(booking.get("guest_last_name") or "")
            guest_phone = str(booking.get("guest_phone") or "")
            guest_email = str(booking.get("guest_email") or "")

            guest_list = [{
                "title-id": guest_title_id,
                "name": guest_first_name,
                "surname": guest_last_name,
            }]
            if guest_phone:
                guest_list[0]["phone"] = guest_phone
            if guest_email:
                guest_list[0]["email"] = guest_email
            for _ in range(max(0, adult_count - 1)):
                guest_list.append({"title-id": 1, "name": "", "surname": ""})

            effective_price = booking.get("discounted_price") or booking.get("total_price") or 0
            effective_currency = str(booking.get("currency") or "EUR").strip().upper() or "EUR"

            full_updates: Dict[str, Any] = {
                "check-in": str(incoming.get("check-in") or booking.get("check_in") or ""),
                "check-out": str(incoming.get("check-out") or booking.get("check_out") or ""),
                "rate-type-id": _to_int(booking.get("rate_type_id"), 0),
                "rate-code-id": _to_int(booking.get("rate_code_id"), 0),
                "board-type-id": _to_int(booking.get("board_type_id"), 0),
                "room-type-id": _to_int(booking.get("room_type_id"), 0),
                "price-agency-id": _to_int(booking.get("price_agency_id"), 0),
                "currency-code": effective_currency,
                "total-price": _to_float(effective_price, 0.0),
                "adult-count": adult_count,
                "guest-list": guest_list,
                "payer-info": {
                    "name": guest_first_name,
                    "surname": guest_last_name,
                },
            }

            note = str(incoming.get("note") or "").strip()
            if note:
                full_updates["note"] = note
            elif booking.get("special_requests"):
                full_updates["note"] = str(booking.get("special_requests"))

            elektra_resp = await update_elektraweb_reservation_fn(
                hotel_id=booking["hotel_id"],
                reservation_id=reservation_id,
                updates=full_updates,
            )

            local_updates: Dict[str, Any] = {
                "admin_notes": f"Elektra update: {datetime.now().isoformat()} | fields={','.join((incoming or {}).keys())[:180]}"
            }
            if isinstance(incoming, dict):
                if incoming.get("check-in"):
                    local_updates["check_in"] = incoming.get("check-in")
                if incoming.get("check-out"):
                    local_updates["check_out"] = incoming.get("check-out")
                if incoming.get("note"):
                    local_updates["special_requests"] = str(incoming.get("note"))

            update_hotel_booking_status_fn(
                booking_id,
                booking.get("status", booking_status.APPROVED),
                **local_updates,
            )
            return {"success": True, "message": "Elektra rezervasyon guncellendi", "elektra_response": elektra_resp}
        except Exception as e:
            err_text = _format_exception_detail(e, 2000)
            err_low = err_text.lower()

            # Tenant bazli bazi Elektra kurulumlarinda update endpoint'i kullanilamaz
            # (verification_exception / endpoint yok).
            # GUVENLIK KURALI: Odeme bagli risk nedeniyle update sirasinda
            # ASLA recreate/cancel fallback uygulanmaz.
            should_try_recreate = (
                ("verification_exception" in err_low)
                or ("updatereservation failed for all endpoint candidates" in err_low)
                or ("/reservation/update -> http 404" in err_low)
            )
            if should_try_recreate:
                return {
                    "success": False,
                    "error": (
                        "Elektra update endpoint kullanilamiyor. Guvenlik nedeniyle "
                        "recreate/cancel fallback KALICI OLARAK KAPALI. "
                        "Eski rezervasyon aynen korunmustur; otomatik iptal/yeni olusturma yapilmadi."
                    ),
                    "error_detail": err_text[:1200],
                }

            return {"success": False, "error": err_text[:1000]}

    @router.post("/admin/hotel-bookings/{booking_id}/elektra/cancel")
    async def cancel_elektra_booking_api(booking_id: int, reason: str = ""):
        if not cancel_elektraweb_reservation_fn:
            return {"success": False, "error": "Elektra cancel fonksiyonu bagli degil"}

        booking = get_hotel_booking_fn(booking_id)
        if not booking:
            return {"success": False, "error": "Booking not found"}

        reservation_id, _voucher_no = _extract_booking_refs(booking)
        if not reservation_id:
            return {"success": False, "error": "Elektra reservation-id bulunamadi"}

        try:
            elektra_resp = await cancel_elektraweb_reservation_fn(
                hotel_id=booking["hotel_id"],
                reservation_id=reservation_id,
                reason=reason or "Admin panel cancel",
            )
            update_hotel_booking_status_fn(
                booking_id,
                "cancelled",
                admin_notes=f"Elektra cancel: {datetime.now().isoformat()} | reason={reason or '-'}",
                elektra_response=json.dumps(elektra_resp, ensure_ascii=False)[:4000],
            )
            return {"success": True, "message": "Elektra rezervasyon iptal edildi", "elektra_response": elektra_resp}
        except Exception as e:
            return {"success": False, "error": _format_exception_detail(e, 1000)}

    @router.post("/admin/hotel-bookings/elektra/hoteladvisor/select/{name}")
    async def hoteladvisor_select_api(name: str, payload: Optional[Dict[str, Any]] = Body(default=None)):
        if not hoteladvisor_select_fn:
            return {"success": False, "error": "HotelAdvisor select fonksiyonu bagli degil"}
        try:
            data = await hoteladvisor_select_fn(name=name, payload=payload or {})
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": _format_exception_detail(e, 1200)}

    @router.post("/admin/hotel-bookings/elektra/hoteladvisor/execute/{name}")
    async def hoteladvisor_execute_api(name: str, payload: Optional[Dict[str, Any]] = Body(default=None)):
        if not hoteladvisor_execute_fn:
            return {"success": False, "error": "HotelAdvisor execute fonksiyonu bagli degil"}
        try:
            data = await hoteladvisor_execute_fn(name=name, payload=payload or {})
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": _format_exception_detail(e, 1200)}

    @router.post("/admin/hotel-bookings/elektra/hoteladvisor/function/{name}")
    async def hoteladvisor_function_api(name: str, payload: Optional[Dict[str, Any]] = Body(default=None)):
        if not hoteladvisor_function_fn:
            return {"success": False, "error": "HotelAdvisor function fonksiyonu bagli degil"}
        try:
            data = await hoteladvisor_function_fn(name=name, payload=payload or {})
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": _format_exception_detail(e, 1200)}

    @router.post("/admin/hotel-bookings/{booking_id}/elektra/hoteladvisor/guests")
    async def hoteladvisor_booking_guests_api(booking_id: int, payload: Optional[Dict[str, Any]] = Body(default=None)):
        if not get_reservation_guests_fn:
            return {"success": False, "error": "HotelAdvisor guest read fonksiyonu bagli degil"}
        booking = get_hotel_booking_fn(booking_id)
        if not booking:
            return {"success": False, "error": "Booking not found"}
        reservation_id, voucher_no = _extract_booking_refs(booking)
        req = dict(payload or {})
        if reservation_id and "reservation-id" not in req:
            req["reservation-id"] = reservation_id
        if voucher_no and "voucher-no" not in req:
            req["voucher-no"] = voucher_no
        if "hotel-id" not in req and booking.get("hotel_id"):
            req["hotel-id"] = int(booking["hotel_id"])
        try:
            data = await get_reservation_guests_fn(payload=req)
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": _format_exception_detail(e, 1200), "request": req}

    @router.post("/admin/hotel-bookings/{booking_id}/elektra/hoteladvisor/guest-save")
    async def hoteladvisor_booking_guest_save_api(booking_id: int, payload: Optional[Dict[str, Any]] = Body(default=None)):
        if not save_reservation_guest_fn:
            return {"success": False, "error": "HotelAdvisor guest save fonksiyonu bagli degil"}
        booking = get_hotel_booking_fn(booking_id)
        if not booking:
            return {"success": False, "error": "Booking not found"}
        reservation_id, voucher_no = _extract_booking_refs(booking)
        req = dict(payload or {})
        if reservation_id and "reservation-id" not in req:
            req["reservation-id"] = reservation_id
        if voucher_no and "voucher-no" not in req:
            req["voucher-no"] = voucher_no
        if "hotel-id" not in req and booking.get("hotel_id"):
            req["hotel-id"] = int(booking["hotel_id"])
        try:
            data = await save_reservation_guest_fn(payload=req)
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": _format_exception_detail(e, 1200), "request": req}

    @router.post("/admin/hotel-bookings/{booking_id}/elektra/hoteladvisor/installments")
    async def hoteladvisor_booking_installments_api(booking_id: int, payload: Optional[Dict[str, Any]] = Body(default=None)):
        if not get_portal_installments_fn:
            return {"success": False, "error": "HotelAdvisor installment fonksiyonu bagli degil"}
        booking = get_hotel_booking_fn(booking_id)
        if not booking:
            return {"success": False, "error": "Booking not found"}
        req = dict(payload or {})
        if "hotel-id" not in req and booking.get("hotel_id"):
            req["hotel-id"] = int(booking["hotel_id"])
        try:
            data = await get_portal_installments_fn(payload=req)
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": _format_exception_detail(e, 1200), "request": req}

    @router.post("/admin/hotel-bookings/{booking_id}/force-deposit-zero")
    async def force_deposit_zero_api(booking_id: int):
        if not hoteladvisor_update_fn:
            return {"success": False, "error": "HotelAdvisor update fonksiyonu bagli degil"}

        booking = get_hotel_booking_fn(booking_id)
        if not booking:
            return {"success": False, "error": "Booking not found"}

        reservation_id, _voucher_no = _extract_booking_refs(booking)
        if not reservation_id:
            return {"success": False, "error": "Elektra reservation-id bulunamadi"}

        hotel_id = int(booking.get("hotel_id") or int(os.getenv("ELEKTRA_HOTEL_ID", "21966")))
        row = {
            "ID": int(reservation_id),
            "HOTELID": hotel_id,
            "DEPOSITPERCENT": "0",
        }
        req = {
            "Row": row,
            "SelectAfterUpdate": ["ID", "HOTELID", "DEPOSITPERCENT"],
        }

        try:
            data = await hoteladvisor_update_fn(name="HOTEL_RES", payload=req)
            update_hotel_booking_status_fn(
                booking_id,
                booking.get("status", booking_status.APPROVED),
                admin_notes=f"DEPOSITPERCENT=0 force: {datetime.now().isoformat()}",
            )
            return {
                "success": True,
                "message": "DEPOSITPERCENT 0 olarak guncellendi",
                "booking_id": booking_id,
                "reservation_id": str(reservation_id),
                "request": req,
                "data": data,
            }
        except Exception as e:
            return {
                "success": False,
                "error": _format_exception_detail(e, 1200),
                "booking_id": booking_id,
                "reservation_id": str(reservation_id),
                "request": req,
            }

    @router.post("/admin/hotel-bookings/{booking_id}/payment-try-test")
    async def payment_try_test_api(booking_id: int):
        booking = get_hotel_booking_fn(booking_id)
        if not booking:
            return {"success": False, "error": "Booking not found"}
        if not (hoteladvisor_select_fn and hoteladvisor_execute_fn and hoteladvisor_function_fn):
            return {"success": False, "error": "HotelAdvisor fonksiyonlari bagli degil"}

        reservation_id, _voucher_no = _extract_booking_refs(booking)
        if not reservation_id:
            return {"success": False, "error": "Reservation ID bulunamadi"}

        hotel_id = int(booking.get("hotel_id") or int(os.getenv("ELEKTRA_HOTEL_ID", "21966")))
        check_in = str(booking.get("check_in") or datetime.now().strftime("%Y-%m-%d"))
        booking_currency = str(booking.get("currency") or "EUR").strip().upper() or "EUR"
        nights = max(1, int(booking.get("nights") or 1))
        total_price = float(booking.get("discounted_price") or booking.get("total_price") or 0.0)
        one_night_base = float(total_price / nights) if total_price > 0 else 0.0

        result: Dict[str, Any] = {
            "success": True,
            "booking_id": booking_id,
            "reservation_id": reservation_id,
            "steps": {},
            "computed": {},
        }

        # Step 1: Kurlar
        rates: Dict[str, float] = {}
        try:
            ex_raw = await hoteladvisor_function_fn(
                name="FN_HOTEL_EXCHANGERATES_ALL",
                payload={"DATE": check_in, "HOTELID": hotel_id},
            )
            rates = _extract_rates(ex_raw)
            result["steps"]["exchange"] = {
                "success": True,
                "currencies": sorted(list(rates.keys())),
            }
        except Exception as e:
            result["steps"]["exchange"] = {"success": False, "error": _format_exception_detail(e, 800)}

        try_amount_try = 0
        if booking_currency in rates and "TRY" in rates and one_night_base > 0:
            try:
                amount_try = (one_night_base * float(rates[booking_currency])) / float(rates["TRY"])
                try_amount_try = int(round(amount_try))
            except Exception:
                try_amount_try = 0
        result["computed"] = {
            "booking_currency": booking_currency,
            "one_night_base": one_night_base,
            "try_amount": try_amount_try,
        }

        # Step 2: HESAPKODU
        hesap_code = ""
        try:
            hesap_raw = await hoteladvisor_select_fn(
                name="QWEB_FOLYO_HESAP",
                payload={
                    "Select": ["KISINO", "SATIR", "KALANODEME"],
                    "Paging": {"Current": 1, "ItemsPerPage": 100},
                    "Where": [{"Column": "FOLYONO", "Operator": "=", "Value": int(reservation_id)}],
                },
            )
            rows = [r for r in _collect_dict_rows(hesap_raw) if str(r.get("KISINO") or "").strip()]
            if rows:
                try:
                    rows.sort(key=lambda r: float(r.get("KALANODEME") or 0), reverse=True)
                except Exception:
                    pass
                hesap_code = str(rows[0].get("KISINO") or "").strip()
            result["steps"]["hesap"] = {
                "success": bool(hesap_code),
                "hesap_code": hesap_code,
                "row_count": len(rows),
            }
            if not hesap_code:
                result["steps"]["hesap"]["error"] = "KISINO bulunamadi"
        except Exception as e:
            result["steps"]["hesap"] = {"success": False, "error": _format_exception_detail(e, 800)}

        # Step 3: DEPKODU
        dep_code = ""
        try:
            dep_raw = await hoteladvisor_select_fn(
                name="QA_HOTEL_DEPARTMENT",
                payload={"Select": ["CODE", "NAME", "ID"], "Paging": {"Current": 1, "ItemsPerPage": 200}},
            )
            dep_rows = _collect_dict_rows(dep_raw)
            for r in dep_rows:
                code = str(r.get("CODE") or r.get("DEPKODU") or "").strip()
                if code:
                    dep_code = code
                    break
            if not dep_code:
                for r in dep_rows:
                    if r.get("ID") is not None:
                        dep_code = str(r.get("ID"))
                        break
            result["steps"]["department"] = {
                "success": bool(dep_code),
                "dep_code": dep_code,
                "row_count": len(dep_rows),
            }
            if not dep_code:
                result["steps"]["department"]["error"] = "CODE/ID bulunamadi"
        except Exception as e:
            result["steps"]["department"] = {"success": False, "error": _format_exception_detail(e, 800)}

        # Step 4: SP_WEB_PAYMENT denemesi
        sp_payload = {
            "KNO": int(reservation_id),
            "TLTUTAR": float(try_amount_try or 0),
            "DOVIZTUTAR": float(try_amount_try or 0),
            "DOVIZKODU": "TRY",
            "DEPKODU": dep_code,
            "HESAPKODU": hesap_code,
            "RECTYPE": 1,
            "DEPOSITPERCENT": 0,
            "HOTELID": hotel_id,
            "TENNANTID": hotel_id,
        }
        try:
            sp_resp = await hoteladvisor_execute_fn(name="SP_WEB_PAYMENT", payload=sp_payload)
            result["steps"]["sp_web_payment"] = {
                "success": True,
                "request": sp_payload,
                "response": sp_resp,
            }
        except Exception as e:
            result["steps"]["sp_web_payment"] = {
                "success": False,
                "request": sp_payload,
                "error": _format_exception_detail(e, 1200),
            }

        # Genel durum
        result["success"] = all(
            bool(result["steps"].get(k, {}).get("success"))
            for k in ("exchange", "hesap", "department", "sp_web_payment")
        )
        return result

    @router.get("/admin/hotel-bookings-page", response_class=HTMLResponse)
    async def hotel_bookings_page():
        from app.web.admin_pages import HOTEL_BOOKINGS_HTML

        return HOTEL_BOOKINGS_HTML

    return router
