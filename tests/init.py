"""
Kassandra Bot Test Suite
========================

Test Katmanları:
- unit/        : İzole fonksiyon testleri (Mock API)
- integration/ : API endpoint testleri
- golden/      : Senaryo bazlı testler
- e2e/         : Uçtan uca testler (Gerçek API)

Çalıştırma:
    pytest                          # Tüm testler
    pytest -m unit                  # Sadece unit
    pytest -m "not e2e"             # E2E hariç
    pytest --cov=app                # Coverage ile
"""

__version__ = "1.0.0"