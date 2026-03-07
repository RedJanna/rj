# Skill Review Checklist

Bu checklist, yeni/degisen bir skill merge edilmeden once hizli kalite kontrol icin kullanilir.

## A) Trigger Kalitesi

- [ ] `name` kisa, benzersiz ve anlamli.
- [ ] `description` "ne zaman kullanilir" kismini acikca soyluyor.
- [ ] Skill baska skill ile cakismiyorsa net ayrim yazili.

## B) Icerik Kalitesi

- [ ] Overview kismi 1-2 paragrafi gecmiyor.
- [ ] Workflow numarali ve uygulanabilir.
- [ ] Kapsam ve kapsam disi bolumu var.
- [ ] Girdi sozlesmesi var (hangi bilgi lazim?).
- [ ] Cikti formati var (rapor standardi).

## C) Teknik Kalite

- [ ] Ilgili dosya haritasi ekli.
- [ ] En az bir dogrulama komutu var.
- [ ] Referans dosyalari gerekiyorsa `references/` altina ayrildi.
- [ ] Tekrar eden operasyon script'e alinmasi gerekiyorsa not edildi.

## D) Guvenlik

- [ ] Secret/token degerleri asla dosyaya yazilmiyor.
- [ ] PII/log maskeleme kurali belirtilmis.
- [ ] Riskli/mutating adimlar icin acik kosul var.

## E) Bakim Kolayligi

- [ ] Skill dosyasi gereksiz uzun degil.
- [ ] Jargon minimum, dil net.
- [ ] Gelecek degisikliklerde hangi dosyanin guncellenecegi belli.

