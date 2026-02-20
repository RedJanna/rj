# Kurulum / Kullanım (Kısa)

## Dosyaları repo'ya koy
- docs/AI_BRIEF.md
- docs/RUNBOOK.md
- docs/INTEGRATIONS.md
- docs/CHANGELOG.md
- tools/generate_project_snapshot.py

## İlk çalıştırma (Windows)
CMD:
  py -3.10 tools\generate_project_snapshot.py --root C:\KassandraOpenAI

## Otomatik güncelle (Git hook)
1) hooks/post-commit dosyasını şuraya kopyala:
   .git/hooks/post-commit
2) Çalıştırılabilir yap (Git Bash):
   chmod +x .git/hooks/post-commit

Artık her commit'te docs/AI_BRIEF.md içindeki AUTOGEN bölümü ve docs/_generated çıktıları güncellenir.
