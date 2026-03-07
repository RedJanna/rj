from __future__ import annotations

import importlib
from pathlib import Path


def test_pdf_service_blank_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("KASSANDRA_PDF_CONFIG_FILE", "")
    import app.services.pdf_service as pdf_service

    reloaded = importlib.reload(pdf_service)

    assert isinstance(reloaded.CONFIG_PATH, Path)
    assert reloaded.CONFIG_PATH.name == "pdf_config.json"
