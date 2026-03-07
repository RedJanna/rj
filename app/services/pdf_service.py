"""
PDF Service - Restoran Rezervasyon PDF Oluşturma
=================================================
Template PDF üzerine rezervasyon bilgilerini yazar.
Koordinatlar pdf_config.json dosyasından okunur.
"""

import os
from pathlib import Path
from datetime import datetime
from io import BytesIO

from app.services.state_store_service import JsonStateRepository, get_project_root

# Config dosyası
PROJECT_ROOT = get_project_root()
# Empty env value resolves to "." with Path(""), which breaks lock path creation.
# Fall back to project default when env is unset or blank.
_pdf_config_raw = (os.getenv("KASSANDRA_PDF_CONFIG_FILE") or "").strip()
CONFIG_PATH = (
    Path(_pdf_config_raw).expanduser()
    if _pdf_config_raw
    else (PROJECT_ROOT / "pdf_config.json")
)
_CONFIG_STORE = JsonStateRepository(CONFIG_PATH)

DEFAULT_FONT_PATH = (
    "C:/Windows/Fonts/arial.ttf"
    if os.name == "nt"
    else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
)

# Varsayılan ayarlar (config yoksa kullanılır)
DEFAULT_CONFIG = {
    "pdf_settings": {
        "template_path": str(PROJECT_ROOT / "templates" / "reservation_template.pdf"),
        "output_dir": str(PROJECT_ROOT / "reservation_pdfs")
    },
    "font_settings": {
        "font_path": DEFAULT_FONT_PATH,
        "size_normal": 13,
        "size_small": 11,
        "color_r": 0.36,
        "color_g": 0.31,
        "color_b": 0.22
    },
    "coordinates": {
        "reservation_no": {"x": 980, "y": 1400, "align": "right"},
        "created_date": {"x": 920, "y": 1252, "align": "right"},
        "customer_name": {"x": 200, "y": 912, "align": "left"},
        "phone": {"x": 195, "y": 865, "align": "left"},
        "guests": {"x": 310, "y": 815, "align": "left"},
        "special_request": {"x": 285, "y": 765, "align": "left"},
        "meal_type": {"x": 155, "y": 658, "align": "left"},
        "date": {"x": 150, "y": 610, "align": "left"},
        "time": {"x": 145, "y": 563, "align": "left"}
    }
}


def load_config():
    """Config dosyasını yükle"""
    try:
        data = _CONFIG_STORE.load_json(default=DEFAULT_CONFIG)
        return data if isinstance(data, dict) else DEFAULT_CONFIG
    except Exception as e:
        print(f"⚠️ Config okunamadı: {e}, varsayılan kullanılıyor")
        return DEFAULT_CONFIG


def format_phone(phone: str) -> str:
    """Telefon numarasını formatla"""
    if not phone:
        return "-"
    phone = str(phone).strip()
    if phone.startswith("90") and len(phone) >= 12:
        return f"+{phone[:2]} {phone[2:5]} {phone[5:8]} {phone[8:10]} {phone[10:]}"
    return phone if phone.startswith("+") else f"+{phone}"


def generate_reservation_pdf(reservation: dict) -> str:
    """
    Template PDF üzerine rezervasyon bilgilerini yazar.
    Koordinatlar pdf_config.json'dan okunur.
    """
    try:
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError as e:
        print(f"❌ Kütüphane eksik: {e}")
        print("💡 Çözüm: pip install pypdf reportlab")
        return None
    
    # Config yükle
    config = load_config()
    pdf_settings = config['pdf_settings']
    font_settings = config['font_settings']
    coords = config['coordinates']
    
    # Template kontrol
    template_path = Path(pdf_settings['template_path'])
    if not template_path.exists():
        print(f"❌ Template bulunamadı: {template_path}")
        return None
    
    # Font yükle
    font_name = "Helvetica"
    font_path = Path(font_settings['font_path'])
    if font_path.exists():
        try:
            pdfmetrics.registerFont(TTFont('TRFont', str(font_path)))
            font_name = "TRFont"
            print(f"✅ Font: {font_path.name}")
        except:
            pass
    
    # Veri hazırla
    data = {
        "reservation_no": str(reservation.get('id') or '-'),
        "created_date": datetime.now().strftime("%d.%m.%Y / %H:%M"),
        "customer_name": str(reservation.get('customer_name') or '-'),
        "phone": format_phone(reservation.get('customer_phone') or ''),
        "guests": str(reservation.get('guest_count') or reservation.get('guests') or '1'),
        "special_request": str(reservation.get('special_requests') or '-')[:35],
        "meal_type": str(reservation.get('meal_type') or '-'),
        "date": str(reservation.get('date') or '-'),
        "time": str(reservation.get('time') or '-')
    }
    
    # Template oku
    reader = PdfReader(str(template_path))
    page = reader.pages[0]
    w = float(page.mediabox.width)
    h = float(page.mediabox.height)
    
    # Overlay oluştur
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    
    # Renk
    c.setFillColorRGB(
        font_settings['color_r'],
        font_settings['color_g'],
        font_settings['color_b']
    )
    
    # Her alan için metin yaz
    for field_name, text in data.items():
        if field_name not in coords:
            continue
        
        field = coords[field_name]
        x = field['x']
        y = field['y']
        align = field.get('align', 'left')
        
        # Font boyutu
        if field_name in ['reservation_no', 'created_date']:
            c.setFont(font_name, font_settings['size_small'])
        else:
            c.setFont(font_name, font_settings['size_normal'])
        
        # Yaz
        if align == 'right':
            c.drawRightString(x, y, text)
        else:
            c.drawString(x, y, text)
    
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
    
    safe_date = data['date'].replace(" ", "_").replace("/", "-").replace(".", "-")
    pdf_path = output_dir / f"rezervasyon_{data['reservation_no']}_{safe_date}.pdf"
    
    with open(pdf_path, "wb") as f:
        writer.write(f)
    
    print(f"✅ PDF: {pdf_path}")
    return str(pdf_path)
