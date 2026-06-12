"""
Rasm va videoga watermark qo'shish.
"""
import io
from PIL import Image, ImageDraw, ImageFont


WATERMARK_TEXT = "@UyJoy_bot"   # ← shu yerda o'zgartiring


def add_watermark(image_bytes: bytes) -> bytes:
    """Rasmga diagonal watermark qo'shib, bytes qaytaradi."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = img.size

    # Overlay layer
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    # Shrift o'lchami — rasm kengligiga qarab
    font_size = max(20, w // 18)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except Exception:
        font = ImageFont.load_default()

    # Matn o'lchami
    bbox     = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
    txt_w    = bbox[2] - bbox[0]
    txt_h    = bbox[3] - bbox[1]

    # Markazga va pastga — ikki qator
    positions = [
        (w // 2 - txt_w // 2, h // 2 - txt_h // 2),          # markaz
        (w - txt_w - 15,      h - txt_h - 15),                # o'ng pastki burchak
    ]

    for pos in positions:
        # Soya (o'qilishi uchun)
        draw.text((pos[0]+2, pos[1]+2), WATERMARK_TEXT, font=font, fill=(0, 0, 0, 100))
        # Asosiy matn — oq, yarim shaffof
        draw.text(pos, WATERMARK_TEXT, font=font, fill=(255, 255, 255, 180))

    # Birlashtirish
    result = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
