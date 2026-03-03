from __future__ import annotations

import json

from app.services import state_store_service as sss


def test_json_state_repository_save_json_retries_on_permission_error(tmp_path, monkeypatch):
    repo = sss.JsonStateRepository(tmp_path / "state.json")
    attempts = {"count": 0}
    real_replace = sss.os.replace

    def _flaky_replace(src, dst):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise PermissionError("locked")
        return real_replace(src, dst)

    monkeypatch.setattr(sss.os, "replace", _flaky_replace)

    payload = {"ok": True, "value": 42}
    repo.save_json(payload)

    assert attempts["count"] == 3
    with open(tmp_path / "state.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data == payload
