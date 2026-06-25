"""
Kechasi ishlaydigan Yandex Geocoder skripti.
Har kuni 1000 ta bino reverse geocode qilinadi (bepul limit).
Kvartal va dom raqamini Yandex dan olib bazaga yozadi.

Ishga tushirish:
  python3 scripts/yandex_geocode_nightly.py
  python3 scripts/yandex_geocode_nightly.py --limit 500
  python3 scripts/yandex_geocode_nightly.py --tuman "Chilonzor tumani"
"""
import asyncio, aiohttp, aiosqlite, os, sys, argparse, datetime, re

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uy_bot.db")
API_KEY  = "2f67e735-0cf4-44fd-ac6e-dbc4e088bd29"
BASE_URL = "https://geocode-maps.yandex.ru/1.x/"
HEADERS  = {"Referer": "https://localhost/"}

# Yandex kvartal nomi → bizning formatimiz
KV_RE = re.compile(r"(\d+)[- ]й\s+кварт", re.IGNORECASE)


async def reverse_geocode(session: aiohttp.ClientSession, lat: float, lon: float) -> dict | None:
    params = {
        "apikey": API_KEY,
        "geocode": f"{lon},{lat}",
        "format":  "json",
        "lang":    "ru_RU",
        "kind":    "house",
        "results": 1,
    }
    try:
        async with session.get(
            BASE_URL, params=params, headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=10), ssl=False
        ) as r:
            if r.status != 200:
                return None
            data = await r.json(content_type=None)
            items = data["response"]["GeoObjectCollection"]["featureMember"]
            if not items:
                return None
            geo  = items[0]["GeoObject"]
            meta = geo["metaDataProperty"]["GeocoderMetaData"]
            comp = {c["kind"]: c["name"] for c in meta.get("Address", {}).get("Components", [])}
            text = meta.get("text", "")

            # Kvartal raqamini textdan ajratib olish
            kv_match = KV_RE.search(text)
            kvartal = f"{kv_match.group(1)}-kvartal" if kv_match else None

            return {
                "text":    text,
                "house":   comp.get("house", ""),
                "street":  comp.get("street", ""),
                "kvartal": kvartal,
            }
    except Exception:
        return None


async def main(limit: int, tuman_filter: str | None):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"🌙 Yandex nightly geocoder — {now}")
    print(f"   Limit: {limit} ta so'rov | Tuman: {tuman_filter or 'barchasi'}\n")

    async with aiosqlite.connect(DB_PATH) as db:
        # Qayta ishlanmagan bino_X binolar
        if tuman_filter:
            query = """
                SELECT b.id, b.lat, b.lon, b.dom_number, b.kvartal, l.tuman
                FROM buildings b
                JOIN locations l ON b.location_id = l.id
                WHERE b.dom_number LIKE 'bino_%'
                  AND b.lat IS NOT NULL
                  AND l.tuman = ?
                ORDER BY l.tuman, b.kvartal, b.id
                LIMIT ?
            """
            rows = await (await db.execute(query, (tuman_filter, limit))).fetchall()
        else:
            query = """
                SELECT b.id, b.lat, b.lon, b.dom_number, b.kvartal, l.tuman
                FROM buildings b
                JOIN locations l ON b.location_id = l.id
                WHERE b.dom_number LIKE 'bino_%'
                  AND b.lat IS NOT NULL
                  AND l.viloyat = 'Toshkent shahri'
                  AND l.tuman != 'Noma''lum tuman'
                ORDER BY l.tuman, b.kvartal, b.id
                LIMIT ?
            """
            rows = await (await db.execute(query, (limit,))).fetchall()

        total_in_db = await (await db.execute(
            "SELECT COUNT(*) FROM buildings WHERE dom_number LIKE 'bino_%'"
        )).fetchone()
        remaining = total_in_db[0]

    print(f"📦 Bazada {remaining} ta bino hali noma'lum")
    print(f"📡 Bugun {len(rows)} ta so'rov yuboriladi\n")

    updated = 0
    not_found = 0
    kv_fixed = 0

    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with aiosqlite.connect(DB_PATH) as db:
            batch = []
            for i, (bino_id, lat, lon, old_dom, old_kvartal, tuman) in enumerate(rows, 1):
                result = await reverse_geocode(session, lat, lon)

                if result and result["house"]:
                    new_dom     = result["house"]
                    new_kvartal = result["kvartal"] or old_kvartal

                    batch.append((new_dom, new_kvartal, bino_id))
                    updated += 1
                    if result["kvartal"] and result["kvartal"] != old_kvartal:
                        kv_fixed += 1
                else:
                    not_found += 1

                # Progress
                if i % 100 == 0:
                    if batch:
                        await db.executemany(
                            "UPDATE buildings SET dom_number=?, kvartal=? WHERE id=?",
                            batch
                        )
                        await db.commit()
                        batch.clear()
                    print(f"  [{i}/{len(rows)}] ✅ {updated} ta yangilandi, ❌ {not_found} topilmadi")

                # Rate limit: ~6 so'rov/soniya
                await asyncio.sleep(0.17)

            # Qolganlarni saqlash
            if batch:
                await db.executemany(
                    "UPDATE buildings SET dom_number=?, kvartal=? WHERE id=?",
                    batch
                )
                await db.commit()

    # Yakuniy statistika
    print(f"\n{'='*50}")
    print(f"✅ Yangilandi:      {updated} ta")
    print(f"🔄 Kvartal to'g'irlandi: {kv_fixed} ta")
    print(f"❌ Topilmadi:       {not_found} ta")
    print(f"📡 Jami so'rov:     {len(rows)} ta")
    print(f"📦 Qolgan (bino_X): {remaining - updated} ta")
    days_left = max(0, (remaining - updated)) // 1000
    print(f"📅 Taxminan {days_left} kun qoldi (1000/kun)")
    print(f"{'='*50}")

    # Tuman bo'yicha progress
    async with aiosqlite.connect(DB_PATH) as db:
        stats = await (await db.execute("""
            SELECT l.tuman,
                   COUNT(CASE WHEN b.dom_number LIKE 'bino_%' THEN 1 END) as remaining,
                   COUNT(b.id) as total
            FROM buildings b
            JOIN locations l ON b.location_id = l.id
            WHERE l.viloyat = 'Toshkent shahri'
              AND l.tuman != 'Noma''lum tuman'
            GROUP BY l.tuman
            ORDER BY remaining DESC
        """)).fetchall()
        print("\n📊 Tuman bo'yicha qolgan bino_X:")
        for r in stats:
            pct = 100 * (r[1] / r[2]) if r[2] > 0 else 0
            bar = "█" * int((100 - pct) / 10) + "░" * int(pct / 10)
            print(f"  {r[0]:<25} {bar} {r[2]-r[1]}/{r[2]} ({100-pct:.0f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1000, help="Kunlik so'rov limiti")
    parser.add_argument("--tuman", type=str, default=None, help="Faqat shu tuman")
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.tuman))
