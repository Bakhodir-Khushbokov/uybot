"""
Rasm va videoga watermark qo'shish.
"""
import io
import os
import asyncio
import tempfile
from PIL import Image, ImageDraw, ImageFont


WATERMARK_TEXT = "@UyJoy_bot"   # ← bot username


def add_photo_watermark(image_bytes: bytes) -> bytes:
    """Rasmga watermark qo'shib, bytes qaytaradi."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = img.size

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    font_size = max(24, w // 16)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    bbox  = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
    txt_w = bbox[2] - bbox[0]
    txt_h = bbox[3] - bbox[1]

    # O'ng pastki burchak
    x = w - txt_w - 20
    y = h - txt_h - 20

    # Soya
    draw.text((x + 2, y + 2), WATERMARK_TEXT, font=font, fill=(0, 0, 0, 140))
    # Asosiy matn
    draw.text((x, y), WATERMARK_TEXT, font=font, fill=(255, 255, 255, 200))

    result = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


FFMPEG_PATH = (
    "/Applications/Shutter Encoder.app/Contents/Resources/Library/ffmpeg"
)


async def add_video_watermark(input_bytes: bytes, ext: str = "mp4") -> bytes | None:
    """
    Videoga ffmpeg orqali watermark qo'shadi.
    ffmpeg topilmasa None qaytaradi (asl video ishlatiladi).
    """
    import shutil
    ffmpeg = shutil.which("ffmpeg") or (FFMPEG_PATH if os.path.exists(FFMPEG_PATH) else None)
    if not ffmpeg:
        return None

    with tempfile.TemporaryDirectory() as tmp:
        inp  = os.path.join(tmp, f"in.{ext}")
        out  = os.path.join(tmp, "out.mp4")

        with open(inp, "wb") as f:
            f.write(input_bytes)

        cmd = [
            ffmpeg, "-y", "-i", inp,
            "-vf",
            f"drawtext=text='{WATERMARK_TEXT}':fontcolor=white:fontsize=36:"
            f"box=1:boxcolor=black@0.4:boxborderw=6:"
            f"x=w-tw-20:y=h-th-20",
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
