import pytest

from app.services import elektraweb_booking_service as svc


@pytest.mark.unit
def test_resolve_endpoint_candidates_defaults_include_current_create_path():
    candidates = svc._resolve_endpoint_candidates("create_reservation", 21966)
    assert "/hotel/21966/createReservation" in candidates


@pytest.mark.unit
def test_resolve_endpoint_candidates_env_override_and_deduplicate(monkeypatch):
    monkeypatch.setenv(
        "ELEKTRA_CREATE_RESERVATION_PATHS",
        "/hotel/{hotel_id}/createReservation,/hotel/{hotel_id}/createReservation,/hotel/{hotel_id}/reservation/create",
    )
    candidates = svc._resolve_endpoint_candidates("create_reservation", 42)
    assert candidates == [
        "/hotel/42/createReservation",
        "/hotel/42/reservation/create",
    ]
