"""
Rasm va videoga watermark qo'shish.
Bot username avtomatik olinadi — o'zgarganda hamma joyda yangilanadi.
"""
import io
import os
import math
import asyncio
import tempfile
from PIL import Image, ImageDraw, ImageFont

# Bot username main.py da set_watermark_text() orqali o'rnatiladi
_watermark_text = "@uylararzonbot"


def set_watermark_text(text: str):
    global _watermark_text
    _watermark_text = text


def get_watermark_text() -> str:
    return _watermark_text


def add_photo_watermark(image_bytes: bytes) -> bytes:
    """
    Rasmga diagonal takrorlanuvchi watermark qo'shadi.
    Oq, yarim shaffof — ko'zga tashlanmaydi lekin crop qilib bo'lmaydi.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = img.size

    text      = get_watermark_text()
    font_size = max(22, min(w, h) // 14)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except Exception:
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size
            )
        except Exception:
            font = ImageFont.load_default()

    # Matn o'lchamini aniqlash
    tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox  = tmp_draw.textbbox((0, 0), text, font=font)
    txt_w = bbox[2] - bbox[0]
    txt_h = bbox[3] - bbox[1]

    # Markazda bitta watermark
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    x = (w - txt_w) // 2
    y = (h - txt_h) // 2
    # Soya
    od.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 60))
    # Asosiy matn — oq, yarim shaffof
    od.text((x, y), text, font=font, fill=(255, 255, 255, 100))

    result = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


FFMPEG_PATH = "/Applications/Shutter Encoder.app/Contents/Resources/Library/ffmpeg"


async def add_video_watermark(input_bytes: bytes, ext: str = "mp4") -> bytes | None:
    """
    Videoga ffmpeg orqali diagonal watermark qo'shadi.
    ffmpeg topilmasa None qaytaradi.
    """
    import shutil
    ffmpeg = shutil.which("ffmpeg") or (FFMPEG_PATH if os.path.exists(FFMPEG_PATH) else None)
    if not ffmpeg:
        return None

    text = get_watermark_text().replace("'", "\\'").replace(":", "\\:")

    with tempfile.TemporaryDirectory() as tmp:
        inp = os.path.join(tmp, f"in.{ext}")
        out = os.path.join(tmp, "out.mp4")

        with open(inp, "wb") as f:
            f.write(input_bytes)

        # Markazda bitta watermark
        vf = (
            f"drawtext=text='{text}':fontcolor=white@0.40:fontsize=32:"
            f"x='(w-text_w)/2':y='(h-text_h)/2':"
            f"shadowcolor=black@0.25:shadowx=2:shadowy=2"
        )

        cmd = [
            ffmpeg, "-y", "-i", inp,
            "-vf", vf,
            "-codec:a", "copy",
            "-preset", "ultrafast",
            out,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

        if os.path.exists(out):
            with open(out, "rb") as f:
                return f.read()
    return None
