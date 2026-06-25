"""
Chilonzor 1, 2, 3-kvartal binolarini Yandex Geocoder bilan test qilish.
Nima qaytarishini ko'ramiz.
"""
import asyncio, aiohttp, aiosqlite, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uy_bot.db")
API_KEY = "2f67e735-0cf4-44fd-ac6e-dbc4e088bd29"
BASE_URL = "https://geocode-maps.yandex.ru/1.x/"
HEADERS = {"Referer": "https://localhost/"}


async def reverse_geocode(session, lat, lon) -> dict | None:
    params = {
        "apikey": API_KEY,
        "geocode": f"{lon},{lat}",
        "format": "json",
        "lang": "ru_RU",
        "kind": "house",
        "results": 1,
    }
    try:
        async with session.get(BASE_URL, params=params, headers=HEADERS,
                               timeout=aiohttp.ClientTimeout(total=10), ssl=False) as r:
            if r.status != 200:
                return None
            data = await r.json(content_type=None)
            features = data["response"]["GeoObjectCollection"]["featureMember"]
            if not features:
                return None
            geo = features[0]["GeoObject"]
            meta = geo["metaDataProperty"]["GeocoderMetaData"]
            components = meta.get("Address", {}).get("Components", [])
            result = {"text": meta.get("text", ""), "components": {}}
            for c in components:
                result["components"][c["kind"]] = c["name"]
            return result
    except Exception as e:
        return None


async def main():
    async with aiosqlite.connect(DB_PATH) as db:
        # Chilonzor 1, 2, 3-kvartal binolari
        rows = await (await db.execute("""
            SELECT b.id, b.lat, b.lon, b.dom_number, b.kvartal
            FROM buildings b
            JOIN locations l ON b.location_id = l.id
            WHERE l.tuman = 'Chilonzor tumani'
              AND b.kvartal IN ('1-kvartal', '2-kvartal', '3-kvartal')
              AND b.lat IS NOT NULL
            ORDER BY b.kvartal, b.id
            LIMIT 50
        """)).fetchall()

    print(f"Jami {len(rows)} ta bino topildi\n")
    print(f"{'Kvartal':<12} {'Dom (eski)':<20} {'Yandex natija'}")
    print("-" * 90)

    updated = 0
    async with aiohttp.ClientSession() as session:
        async with aiosqlite.connect(DB_PATH) as db:
            for bino_id, lat, lon, old_dom, kvartal in rows:
                result = await reverse_geocode(session, lat, lon)
                if result:
                    c = result["components"]
                    house = c.get("house", "")
                    street = c.get("street", "")
                    district = c.get("district", "")
                    text_short = result["text"].replace("Узбекистан, Ташкент, ", "")[:60]
                    print(f"{kvartal:<12} {old_dom:<20} {text_short}")

                    # Yangi dom raqamini saqlash
                    if house and house != old_dom:
                        new_dom = house
                        await db.execute(
                            "UPDATE buildings SET dom_number=? WHERE id=?",
                            (new_dom, bino_id)
                        )
                        updated += 1
                else:
                    print(f"{kvartal:<12} {old_dom:<20} ❌ topilmadi")

                await asyncio.sleep(0.15)  # rate limit: ~6/sec

            await db.commit()

    print(f"\n✅ Yangilandi: {updated} ta bino")
    print(f"📊 1000 bepul limitdan {len(rows)} ta ishlatildi")


if __name__ == "__main__":
    asyncio.run(main())
