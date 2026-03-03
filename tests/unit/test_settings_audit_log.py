import pytest

from app.core import settings_service


@pytest.mark.unit
def test_append_and_read_settings_audit(tmp_path, monkeypatch):
    audit_file = tmp_path / "settings_audit.json"
    monkeypatch.setattr(settings_service, "SETTINGS_AUDIT_FILE", audit_file)

    settings_service.append_settings_audit_entry(
        key="quiet_auto_room_keys",
        old_value=["deluxe"],
        new_value=["deluxe", "premium"],
        updated_by="admin1",
    )

    items = settings_service.get_settings_audit(limit=10)
    assert len(items) == 1
    assert items[0]["key"] == "quiet_auto_room_keys"
    assert items[0]["old_value"] == ["deluxe"]
    assert items[0]["new_value"] == ["deluxe", "premium"]
    assert items[0]["updated_by"] == "admin1"

