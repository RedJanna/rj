from __future__ import annotations

import os

from app.services import conversation_store


def test_conversation_store_default_path_points_project_conversations():
    # Varsayılan davranış: konuşmalar proje kökündeki conversations klasöründe tutulmalı.
    expected_suffix = os.path.join("KassandraOpenAI", "conversations")
    assert str(conversation_store.CONVERSATIONS_DIR).replace("\\", "/").endswith(expected_suffix.replace("\\", "/"))
