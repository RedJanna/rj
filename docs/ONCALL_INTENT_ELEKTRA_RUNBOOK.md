# ON-CALL RUNBOOK - Intent + Elektra (Tek Dosya)

Bu dosya, gece nobetinde "mesaj geldi ama cevap yanlis" durumunu hizli ve dogru yonetmek icin hazirlandi.

Kisa analoji:
- Intent sorunu = "resepsiyon misafiri yanlis masaya yonlendirdi"
- Elektra sorunu = "mutfak gecici kapali, fiyat cikmiyor"

Amac:
- Yanlis teshis yapmadan kok nedeni bulmak
- Guvenli cevap vermek (uydurma fiyat yok)
- Duzeltmeyi testle dogrulamak

---

## 0) 60 Saniyelik Hizli Tespit

Bu 3 soruyu sirayla cevapla:

1. Sistem ayakta mi?
- `curl -sS http://127.0.0.1:8000/health`

2. Mesaj fiyat/musaitlik sorusu mu?
- Ornek: "14-18 Agustos 2 yetiskin fiyat nedir?"

3. Cikis ne oldu?
- `reason_code=elektra_price_unavailable` ise once Elektra dalina git.
- Yanlis intent secildi ise Intent dalina git.

---

## 1) Karar Agaci (Jargonsuz)

Durum A:
- Belirti: fiyat sorusunda sistem "ekibe iletiyoruz" turu handoff veriyor.
- Anlam: kasadaki fiyat motoru su an bilgi donduremiyor.
- Gidilecek dal: Elektra.

Durum B:
- Belirti: kullanici rezervasyon baslatmak isterken sistem baska akisa kayiyor.
- Anlam: yonlendirme (intent) adiminda yanlis kapidan gecildi.
- Gidilecek dal: Intent.

Durum C:
- Belirti: `/health` bile cevap vermiyor.
- Anlam: bina kapali, once platformu ayaga kaldir.
- Gidilecek dal: Platform.

---

## 2) Elektra Dali (Fiyat Motoru)

### 2.1 Once durum kontrolu

Sadece SET/NOT_SET kontrol et (secret degeri yazma):
- `Elektra_Booking`
- `ELEKTRA_HOTEL_ID`
- `ELEKTRA_API_BASE_URL`

### 2.2 Beklenen guvenli davranis

Elektra sonucu yoksa sistem:
- `status=handoff`
- `reason_code=elektra_price_unavailable`

Bu dogru fren davranisidir (uydurma fiyat vermez).

Kod referansi:
- `app/routes/chat_routes.py` (price fallback guard)
- `app/handlers/elektra_price_entry_handler.py`

### 2.3 Test dogrulamasi

```bash
PYTHONPATH=. pytest -q tests/unit/test_chat_pipeline_routes.py -k "price_intent_without_elektra_result or low_confidence_known_intent"
PYTHONPATH=. pytest -q tests/unit/test_elektra_price_entry_handler.py
```

### 2.4 Cozum adimlari

1. Eksik env varsa tamamla (OS env veya secret manager).
2. Endpoint/path supheliyse probe calistir:
```bash
python3 tools/elektra_endpoint_probe.py --hotel-id 21966
```
3. Gerekirse endpoint override envlerini duzelt.
4. Smoke testi tekrar et.

---

## 3) Intent Dali (Yanlis Yonlendirme)

### 3.1 Belirti ornekleri

- "rezervasyon baslatalim" dediginde price/clarify aciliyor.
- Basit bilgi sorusu gereksiz handoff'a dusuyor.

### 3.2 Bakilacak dosyalar

- `app/services/intent_semantic_service.py`
- `app/services/intent_policy_service.py`
- `app/services/intent_normalizer_service.py`
- `app/routes/chat_routes.py`
- `app/content/intent_slot_contract.py`

### 3.3 Test dogrulamasi

```bash
PYTHONPATH=. pytest -q tests/unit/test_intent_router_service.py tests/unit/test_intent_policy_service.py tests/unit/test_chat_pipeline_routes.py
```

### 3.4 Cozum adimlari

1. Mesaji birebir yeniden uret.
2. Beklenen intent vs gercek intent farkini net yaz.
3. En dar noktada duzeltme yap (buyuk refactor yapma).
4. Yeni regression testi ekle.
5. Eski testlerin hepsi gectigini dogrula.

---

## 4) Platform Dali (Servis Ayakta Degil)

### 4.1 Kontrol

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/api/v1/health
```

### 4.2 Cozum

1. Backend start et (`start_backend.bat` veya uvicorn).
2. Preflight hatalarini gider.
3. Health yesile donunce tekrar Elektra/Intent dalina gec.

---

## 5) Musteriye Guvenli Cevap Sablonu

Elektra gecici yoksa:
- TR: "Talebinizi aldik, fiyat ve musaitlik bilgisini netlestirip en kisa surede sizinle paylasacagiz."
- EN: "We received your request. We will share accurate price and availability details shortly."

Kural:
- Emin olmadigin fiyat bilgisini asla yazma.

---

## 6) Incident Kapatma Formati

Raporu su formatta kapat:

- Incident:
- Beklenen:
- Gerceklesen:
- Kok neden sinifi: `intent` | `elektra` | `platform`
- Yapilan aksiyon:
- Calisan test komutlari:
- Son durum:
- Kalan risk:

---

## 7) Hizli Hatirlatma

- Once dogru teshis, sonra duzeltme.
- Elektra yoksa uydurma fiyat yok.
- Duzeltme varsa test zorunlu.
