from __future__ import annotations

from app.content.system_prompt import INFO_SYSTEM_PROMPT


def test_policy_v2_contains_special_day_handoff_rule():
    assert "Ozel gun talepleri" in INFO_SYSTEM_PROMPT
    assert "dogum gunu, balayi, yildonumu, evlilik teklifi" in INFO_SYSTEM_PROMPT
    assert "canli musteri temsilcisine aktar" in INFO_SYSTEM_PROMPT


def test_policy_v2_contains_response_length_exception_rule():
    assert "fiyat listesi, coklu soru, politika veya zorunlu bilgilendirme" in INFO_SYSTEM_PROMPT
    assert "gerektigi kadar detay ver" in INFO_SYSTEM_PROMPT


def test_policy_v2_contains_testable_mandatory_rules():
    assert "V2 KATI VE TEST EDILEBILIR KURALLAR" in INFO_SYSTEM_PROMPT
    assert "Musterinin ayni mesajdaki tum sorularini tek cevapta yanitla" in INFO_SYSTEM_PROMPT
    assert "Soruda tarih geciyorsa, yanitta ayni tarih araligini tekrar yaz" in INFO_SYSTEM_PROMPT


def test_policy_v2_contains_language_priority_and_hotel_language_exception():
    assert "DIL POLITIKASI (EN UST ONCELIK)" in INFO_SYSTEM_PROMPT
    assert "EN > TR > RU > DE > AR > ES > FR > ZH > HI > PT" in INFO_SYSTEM_PROMPT
    assert "'Turkce ve Ingilizce'" in INFO_SYSTEM_PROMPT


def test_policy_v2_contains_operational_checklist_rules():
    assert "Her yanitta su iskeleti koru" in INFO_SYSTEM_PROMPT
    assert "'Yok/Uygun degil' deniyorsa konusmayi kapatma" in INFO_SYSTEM_PROMPT
    assert "Butce itirazinda" in INFO_SYSTEM_PROMPT
    assert "Gece gec check-in + ozel surpriz taleplerinde" in INFO_SYSTEM_PROMPT
    assert "Erken cikis + iade/kullanilmayan gece taleplerinde" in INFO_SYSTEM_PROMPT


def test_policy_v2_contains_reservation_change_and_cancel_rules():
    assert "TARIH DEGISIKLIGI AKISI" in INFO_SYSTEM_PROMPT
    assert "AYNI ODA TIPI musaitligini kontrol et" in INFO_SYSTEM_PROMPT
    assert "AYNI ODA TIPI YOKSA" in INFO_SYSTEM_PROMPT
    assert "musait tum oda tiplerini ve her birinin fiyatini" in INFO_SYSTEM_PROMPT
    assert "IPTAL TALEBI ILK ADIM" in INFO_SYSTEM_PROMPT
    assert "fiyat tipini sor: (1) Iptal edilemez (2) Ucretsiz iptal" in INFO_SYSTEM_PROMPT
    assert "REZERVASYON NUMARASI ACIKLAMASI" in INFO_SYSTEM_PROMPT
    assert "rezervasyon numarasi" in INFO_SYSTEM_PROMPT
    assert "REZERVASYON NUMARASI MECBURIYETI" in INFO_SYSTEM_PROMPT
    assert "rezervasyon numarasi paylasilmadan rezervasyon uzerinde islem yapma" in INFO_SYSTEM_PROMPT
    assert "REZERVASYON OLUSTURMA SONRASI" in INFO_SYSTEM_PROMPT
