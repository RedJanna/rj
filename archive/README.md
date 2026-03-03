# Archive Policy

Bu klasor, calisan kod agacindan uzaklastirilmis yedek/snapshot dosyalari icindir.

- `archive/backups/` altina tasinan dosyalar kaynak agacinda kullanilmaz.
- Runtime veya "yanlislikla calisabilecek" dosyalar (ozellikle `*.py.bak_*`) burada tutulur.
- Uzun sureli saklama gerekiyorsa harici depoya (zip/artifact storage) alinmasi onerilir.

Not:
- `archive/backups/**` `.gitignore` ile ignore edilir.
- Gerekirse sadece secili dosyalar bilincli olarak `git add -f` ile eklenebilir.
