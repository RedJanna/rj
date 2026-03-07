# Skill Development Playbook

Bu belge, projede yeni skill uretmek veya var olan skill'i gelistirmek icin uygulama rehberidir.
Amac: skill dosyalari hem geliştirici hem model tarafinda net, bakimi kolay ve stabil olsun.

## 1) Skill Nedir (Pratik Tanim)

Skill, "belirli bir is icin uzmanlasmis mini operasyon kilavuzu"dur.
Bir skill genelde su 4 parcadan olusur:

- `SKILL.md`: asil davranis ve workflow
- `agents/openai.yaml`: UI/agent metadata
- `references/`: gerektiğinde okunacak detay bilgi
- `scripts/`: tekrar eden adimlari otomatik yapan scriptler (opsiyonel)

## 2) Skill Yazim Kurallari

### 2.1 SKILL.md yapisi

Her skill su sirayla yazilmali:

1. `Overview`: skill neyi cozer
2. `Ne Zaman Kullanilir`: tetikleyici durumlar
3. `Kapsam ve Sinirlar`: nereye kadar gider, neyi yapmaz
4. `Girdi Sozlesmesi`: bu skill calisabilmesi icin gereken bilgiler
5. `Operasyonel Workflow`: adim adim yapilacaklar
6. `Cikti Formati`: rapor/sonuc standardi
7. `Dosya Haritasi`: bakilacak kod/test dosyalari
8. `Guvenlik Kurallari`: secret/PII/log disiplini

### 2.2 Dil ve uslup

- Kisa cumle, net emir kipleri.
- Jargon zorunlu degilse kullanma.
- "Neden" yerine agirlikla "ne yapilir" yaz.
- Her kritik karar icin en az bir somut ornek ver.

### 2.3 Dosya baglantisi disiplini

- Bir kural yaziyorsan ilgili dosya adini da ver.
- Test gerektiren kuralda dogrudan test komutu yaz.
- "genel kontrol et" yerine "su dosyaya bak" de.

## 3) Skill Tasarim Patternleri

### 3.1 Workflow-based (onerilen)

Karmaşık operasyonlarda standart:
- Incident al
- Teshis et
- Duzelt
- Dogrula
- Raporla

### 3.2 Guard-based

Yanlis aksiyon riski yuksekse:
- Yapma kurallari acik yazilir
- Guvenli fallback net tanimlanir

### 3.3 Delegation-based

Bir skill baska skill'e devredecekse:
- "Hangi belirti -> Hangi skill" tablosu eklenir

## 4) Isimlendirme ve Organizasyon

### 4.1 Klasor yapisi

- Domain'e gore ayir: `skills/operations/...`, `skills/development/...` gibi
- Skill adi fiil+amac mantiginda olsun:
  - `intent-ops-triage`
  - `elektra-endpoint-ops`

### 4.2 Dosya adlari

- `SKILL.md` sabit
- `agents/openai.yaml` sabit
- `references/` icindeki adlar amac bazli:
  - `demo_ops_report.md`
  - `incident_patterns.md`

## 5) Gelecekte Bakim Kolayligi Icin Kurallar

- Skill icinde tek bir "source of truth" olsun.
- Kopya kurallar farkli skilllere dagitilmasin.
- Kritik kararlar mutlaka regression test ismiyle baglansin.
- Her skill icin "kapsam disi" bolumu yazilsin (yanlis kullanim azalir).

## 6) Minimum Kalite Kriteri (Done Definition)

Bir skill "hazir" sayilmasi icin:

- `description` net ve tetikleyici durumlari kapsiyor.
- `SKILL.md` icinde workflow adimlari numarali.
- En az 1 girdi ornegi ve 1 cikti ornegi var.
- Guvenlik kurali var (secret/log disiplini).
- En az 1 test komutu var.

## 7) Hizli Akis (30 Dakika)

1. Problem sinifini yaz (2-3 cumle)
2. SKILL.md iskeletini doldur
3. Dosya haritasi ekle
4. Cikti formatini sabitle
5. Agent metadata ekle
6. Tek incident ornegi ile kontrol et

## 8) Bu Repo Icin Onerilen Sonraki Skill Alanlari

- `intent-regression-guard`
- `elektra-config-readiness`
- `live-handoff-quality-check`

