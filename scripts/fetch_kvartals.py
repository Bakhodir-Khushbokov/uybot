"""
Yandex Geocoder API orqali Toshkent tumanlarining kvartallarini olish.
API key: kuniga 1000 so'rov bepul.
"""
import asyncio
import aiohttp
import aiosqlite
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uy_bot.db")
API_KEY  = "2f67e735-0cf4-44fd-ac6e-dbc4e088bd29"
BASE_URL = "https://geocode-maps.yandex.ru/1.x/"

# (uz_nomi, ru_nomi) juftliklari
TUMANLAR = [
    ("Chilonzor tumani",       "Чиланзарский район"),
    ("Yunusobod tumani",       "Юнусабадский район"),
    ("Mirzo Ulug'bek tumani",  "Мирзо-Улугбекский район"),
    ("Olmazor tumani",         "Алмазарский район"),
    ("Uchtepa tumani",         "Учтепинский район"),
    ("Yakkasaroy tumani",      "Яккасарайский район"),
    ("Shayxontohur tumani",    "Шайхантахурский район"),
    ("Sergeli tumani",         "Сергелийский район"),
    ("Bektemir tumani",        "Бектемирский район"),
    ("Yangihayot tumani",      "Янгихаётский район"),
]

# Har bir tuman uchun max kvartal raqami
MAX_KVARTAL = 60


async def geocode(session: aiohttp.ClientSession, query: str) -> dict | None:
    params = {
        "apikey": API_KEY,
        "geocode": query,
        "format": "json",
        "lang": "ru_RU",
        "results": 1,
        "ll": "69.2401,41.2995",  # Toshkent markazi
        "spn": "0.5,0.5",
    }
    try:
        headers = {"Referer": "https://localhost/"}
        async with session.get(BASE_URL, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10), ssl=False) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            features = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
            if not features:
                return None
            geo = features[0]["GeoObject"]
            pos = geo["Point"]["pos"].split()
            lon, lat = float(pos[0]), float(pos[1])
            bbox = geo.get("boundedBy", {}).get("Envelope", {})
            lower = bbox.get("lowerCorner", "").split()
            upper = bbox.get("upperCorner", "").split()

            # Manzil komponentlarini tekshir
            meta = geo.get("metaDataProperty", {}).get("GeocoderMetaData", {})
            kind = meta.get("kind", "")
            text = meta.get("text", "")

            return {
                "lat": lat,
                "lon": lon,
                "text": text,
                "kind": kind,
                "bbox_lower_lon": float(lower[0]) if lower else None,
                "bbox_lower_lat": float(lower[1]) if lower else None,
                "bbox_upper_lon": float(upper[0]) if upper else None,
                "bbox_upper_lat": float(upper[1]) if upper else None,
            }
    except Exception as e:
        print(f"  ⚠️  {query}: {e}")
        return None


def is_valid_kvartal(result: dict, tuman: str, kvartal_n: int) -> bool:
    """Natija haqiqatan ham shu kvartalga tegishli ekanligini tekshir."""
    if not result:
        return False
    text = result["text"].lower()
    # Faqat Toshkent shahri (viloyat emas)
    if "ташкент," not in text and "ташкент " not in text:
        return False
    # Toshkent viloyati emas
    if "ташкентская область" in text:
        return False
    # Koordinatlar Toshkent shahri bbox ichida bo'lishi kerak
    lat, lon = result["lat"], result["lon"]
    if not (41.18 <= lat <= 41.45 and 69.10 <= lon <= 69.45):
        return False
    # kvartal raqami mavjud bo'lishi kerak
    if str(kvartal_n) not in text:
        return False
    return True


async def create_table(db: aiosqlite.Connection):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS kvartals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tuman TEXT NOT NULL,
            kvartal_n INTEGER NOT NULL,
            lat REAL,
            lon REAL,
            bbox_lower_lon REAL,
            bbox_lower_lat REAL,
            bbox_upper_lon REAL,
            bbox_upper_lat REAL,
            address_text TEXT,
            UNIQUE(tuman, kvartal_n)
        )
    """)
    await db.commit()


async def main():
    print("🗺  Yandex Geocoder orqali kvartallar yuklanmoqda...\n")

    async with aiosqlite.connect(DB_PATH) as db:
        await create_table(db)

        # Allaqachon saqlangan kvartallarni tekshir
        existing = set()
        rows = await (await db.execute("SELECT tuman, kvartal_n FROM kvartals")).fetchall()
        for r in rows:
            existing.add((r[0], r[1]))
        print(f"✅ Allaqachon saqlangan: {len(existing)} ta kvartal\n")

        total_saved = 0
        request_count = 0

        async with aiohttp.ClientSession() as session:
            for uz_nom, ru_nom in TUMANLAR:
                tuman = uz_nom
                found_count = 0
                consecutive_misses = 0
                print(f"→ {uz_nom}:")

                for n in range(1, MAX_KVARTAL + 1):
                    if (tuman, n) in existing:
                        found_count += 1
                        consecutive_misses = 0
                        continue

                    # So'rov yuborish
                    query = f"Ташкент, {ru_nom}, {n}-й квартал"
                    result = await geocode(session, query)
                    request_count += 1

                    # Rate limit: 10 so'rov/soniya
                    if request_count % 10 == 0:
                        await asyncio.sleep(1)

                    if result and is_valid_kvartal(result, tuman, n):
                        await db.execute("""
                            INSERT OR REPLACE INTO kvartals
                            (tuman, kvartal_n, lat, lon, bbox_lower_lon, bbox_lower_lat, bbox_upper_lon, bbox_upper_lat, address_text)
                            VALUES (?,?,?,?,?,?,?,?,?)
                        """, (
                            tuman, n,
                            result["lat"], result["lon"],
                            result["bbox_lower_lon"], result["bbox_lower_lat"],
                            result["bbox_upper_lon"], result["bbox_upper_lat"],
                            result["text"],
                        ))
                        await db.commit()
                        print(f"  ✅ {n}-kvartal: {result['lat']:.4f},{result['lon']:.4f} — {result['text'][:60]}")
                        found_count += 1
                        total_saved += 1
                        consecutive_misses = 0
                    else:
                        consecutive_misses += 1
                        # 5 ta ketma-ket topilmasa, bu tuman uchun kvartallar tugagan
                        if consecutive_misses >= 5 and n > 10:
                            print(f"  ⏹  {n-4} dan keyin kvartal topilmadi, to'xtatildi")
                            break

                print(f"  📊 {tuman}: {found_count} ta kvartal topildi\n")

        print(f"\n✅ Jami yangi saqlandi: {total_saved} ta kvartal")
        print(f"📡 Jami so'rovlar: {request_count}")

        # Statistika
        rows = await (await db.execute("""
            SELECT tuman, COUNT(*) as cnt FROM kvartals
            GROUP BY tuman ORDER BY tuman
        """)).fetchall()
        print("\n📊 Tuman bo'yicha kvartallar:")
        for r in rows:
            print(f"   {r[0]}: {r[1]} ta kvartal")


if __name__ == "__main__":
    asyncio.run(main())
