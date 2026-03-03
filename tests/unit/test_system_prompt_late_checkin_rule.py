from app.content.system_prompt import INFO_SYSTEM_PROMPT


def test_system_prompt_contains_late_checkin_hard_rule():
    assert "GEC GIRIS KURALI" in INFO_SYSTEM_PROMPT
    assert "Otele giris saat 14:00'dan sonradir" in INFO_SYSTEM_PROMPT
    assert "musaitlik kontrolu" in INFO_SYSTEM_PROMPT
