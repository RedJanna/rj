"""
PDF Koordinat Test Aracı
========================
Bu script ile koordinatları test edebilirsiniz.

KULLANIM:
1. pdf_config.json dosyasını düzenleyin
2. Bu script'i çalıştırın: python test_pdf.py
3. Oluşan PDF'i kontrol edin
4. Koordinatları ayarlayıp tekrar test edin

KOORDİNAT İPUÇLARI:
- x artır = metin SAĞA kayar
- x azalt = metin SOLA kayar  
- y artır = metin YUKARI kayar
- y azalt = metin AŞAĞI kayar
"""

import json
from pathlib import Path
from datetime import datetime
from io import BytesIO

# Config dosyası
CONFIG_PATH = Path("C:/KassandraOpenAI/pdf_config.json")

def load_config():
    """Config dosyasını yükle"""
    if not CONFIG_PATH.exists():
        print(f"❌ Config bulunamadı: {CONFIG_PATH}")
        return None
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_test_pdf():
    """Test PDF oluştur"""
    try:
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError as e:
        print(f"❌ Kütüphane eksik: {e}")
        print("💡 Çözüm: pip install pypdf reportlab")
        return
    
    # Config yükle
    config = load_config()
    if not config:
        return
    
    pdf_settings = config['pdf_settings']
    font_settings = config['font_settings']
    coords = config['coordinates']
    
    # Template kontrol
    template_path = Path(pdf_settings['template_path'])
    if not template_path.exists():
        print(f"❌ Template bulunamadı: {template_path}")
        return
    
    print(f"✅ Template: {template_path}")
    
    # Font yükle
    font_name = "Helvetica"
    font_path = Path(font_settings['font_path'])
    if font_path.exists():
        try:
            pdfmetrics.registerFont(TTFont('CustomFont', str(font_path)))
            font_name = "CustomFont"
            print(f"✅ Font: {font_path}")
        except Exception as e:
            print(f"⚠️ Font yüklenemedi: {e}")
    
    # Test verileri
    test_data = {
        "reservation_no": "TEST-999",
        "created_date": datetime.now().strftime("%d.%m.%Y / %H:%M"),
        "customer_name": "Ömer Alperen Gönen",
        "phone": "+90 530 123 45 67",
        "guests": "3",
        "special_request": "Köşede masa istiyorum",
        "meal_type": "Akşam Yemeği",
        "date": "25 Ocak 2026",
        "time": "19:30"
    }
    
    # Template oku
    reader = PdfReader(str(template_path))
    page = reader.pages[0]
    w = float(page.mediabox.width)
    h = float(page.mediabox.height)
    
    print(f"📐 PDF boyutu: {w:.0f} x {h:.0f} pt")
    
    # Overlay oluştur
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    
    # Renk ayarla
    c.setFillColorRGB(
        font_settings['color_r'],
        font_settings['color_g'],
        font_settings['color_b']
    )
    
    # Her alan için metin yaz
    for field_name, field_config in coords.items():
        if field_name.startswith('_'):
            continue
            
        x = field_config['x']
        y = field_config['y']
        align = field_config.get('align', 'left')
        
        # Font boyutu
        if field_name in ['reservation_no', 'created_date']:
            c.setFont(font_name, font_settings['size_small'])
        else:
            c.setFont(font_name, font_settings['size_normal'])
        
        # Metin
        text = test_data.get(field_name, f"[{field_name}]")
        
        # Yaz
        if align == 'right':
            c.drawRightString(x, y, text)
        else:
            c.drawString(x, y, text)
        
        print(f"  {field_name}: ({x}, {y}) = '{text}'")
    
    c.save()
    buf.seek(0)
    
    # Birleştir
    overlay = PdfReader(buf)
    page.merge_page(overlay.pages[0])
    
    writer = PdfWriter()
    writer.add_page(page)
    
    # Kaydet
    output_dir = Path(pdf_settings['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "TEST_koordinat.pdf"
    
    with open(output_path, "wb") as f:
        writer.write(f)
    
    print(f"\n✅ Test PDF oluşturuldu: {output_path}")
    print("\n📋 Sonraki adımlar:")
    print("   1. PDF'i açıp kontrol edin")
    print("   2. Metinler kaymışsa pdf_config.json'u düzenleyin")
    print("   3. Bu script'i tekrar çalıştırın")
    print("\n💡 İpucu: x artır=sağa, y artır=yukarı")

if __name__ == "__main__":
    print("=" * 50)
    print("📄 PDF Koordinat Test Aracı")
    print("=" * 50)
    create_test_pdf()
