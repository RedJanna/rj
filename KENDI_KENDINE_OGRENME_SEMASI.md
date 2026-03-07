# Kendi Kendine Öğrenme Şeması

Bu doküman, sistemin yeni konu öğrenmesini ve admin onay akışını sade şekilde anlatır.

## 1) Ana Akış (Şema)

```text
[Müşteri mesajı]
      |
      v
[Bot mesajı sınıflandırır]
      |
      +--> [Net anlaşıldı] ------------------> [Normal cevap]
      |
      +--> [Emin değil / yeni konu]
                    |
                    v
        [Öğrenme kuyruğuna yaz]
        data/active_learning_queue.jsonl
                    |
                    v
        [Günlük aday kaydı oluştur]
        data/scenario_review_queue.json
                    |
                    v
            [Admin panel aday listesi]
                    |
                    +--> [Onayla (Taslak Üret)]
                    |           |
                    |           v
                    |   [GPT-5.2 ile taslak üret]
                    |   templates/senaryo_template_ornek.txt
                    |           |
                    |           v
                    |   [Dosyaya yaz]
                    |   C:\KassandraOpenAI\yenı_senaryolar\al-xxxx_revN.txt
                    |           |
                    |           v
                    |      [Durum: draft_ready]
                    |
                    +--> [Yeniden Düzenle]
                    |           |
                    |           v
                    |   [GPT-5.2 ile yeni revizyon]
                    |   C:\KassandraOpenAI\yenı_senaryolar\al-xxxx_rev(N+1).txt
                    |
                    +--> [Kesin Onay]
                    |           |
                    |           v
                    |   [Sisteme entegre et]
                    |   - tests/golden/scenarios/external_scenarios.json
                    |   - app/content/scenario_intent_examples.json
                    |           |
                    |           v
                    |      [Durum: approved]
                    |
                    +--> [Reddet] -----------> [Durum: rejected]
                    |
                    +--> [Klasörden Entegre Et (Toplu)]
                                |
                                v
                   [yenı_senaryolar/*.txt dosyalarını tara]
                                |
                                v
                   [Tekrar kontrolü]
                   - Daha önce işlenmiş dosya mı?
                   - Aynı içerik hash'i daha önce işlendi mi?
                                |
                                +--> Evet: [Atla]
                                |
                                +--> Hayır: [Entegre et + işaretle]
```

## 2) Butonlar Ne Yapar?

1. `Onayla (Taslak Üret)`
- Entegrasyon yapmaz.
- Zorunlu olarak `gpt-5.2` ile taslak metin üretir.
- `yenı_senaryolar` klasörüne `.txt` yazar.

2. `Yeniden Düzenle`
- Aynı aday için `gpt-5.2` ile yeni revizyon taslağı üretir.

3. `Kesin Onay`
- Taslağı sisteme kalıcı olarak entegre eder.
- Benzer soruların daha doğru yakalanmasını sağlar.

4. `Reddet`
- Adayı kapatır, sisteme entegre etmez.

5. `Klasörden Entegre Et`
- `yenı_senaryolar` içindeki taslakları toplu işler.
- İşlenen dosya/aynı içerik ikinci kez kullanılmaz.

## 3) Durum Geçişi (State)

```text
pending -> draft_ready -> approved
   |            |
   +----------> rejected
```

- `pending`: Yeni aday, henüz taslak yok.
- `draft_ready`: GPT-5.2 taslağı üretildi, admin incelemede.
- `approved`: Entegrasyon tamamlandı.
- `rejected`: Bilinçli olarak dışarıda bırakıldı.

## 4) Tekrar (Duplicate) Engeli Nasıl Çalışır?

Kontrol dosyası:
- `data/scenario_draft_ingest_state.json`

Tutulan bilgiler:
- İşlenmiş dosya yolu
- İçerik hash bilgisi (aynı içerik yakalama)
- İşlenme zamanı ve sonuç

Böylece:
- Aynı `.txt` dosyası yeniden entegre edilmez.
- Farklı isimle kopyalanmış aynı içerik de yeniden entegre edilmez.

## 5) Kritik Dizinler

- Kuyruk: `data/active_learning_queue.jsonl`
- Adaylar: `data/scenario_review_queue.json`
- Taslaklar: `C:\KassandraOpenAI\yenı_senaryolar`
- Taslak şablon: `C:\KassandraOpenAI\templates\senaryo_template_ornek.txt`
- Duplicate durumu: `data/scenario_draft_ingest_state.json`
