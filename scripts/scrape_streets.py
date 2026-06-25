"""
Toshkent ko'chalari va binolarini OSM Overpass API orqali bir marta yuklab,
o'z bazamizga saqlash. Keyin Yandex API kerak emas.

Natija: streets va buildings jadvallarida to'liq manzil ma'lumotlari.
"""
import asyncio, aiohttp, aiosqlite, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uy_bot.db")

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# Toshkent shahri bbox
BBOX = "41.18,69.10,41.45,69.45"

# Tuman nomi → OSM admin nomi
TUMANLAR = {
    "Chilonzor tumani":      "Chilonzor",
    "Yunusobod tumani":      "Yunusobod",
    "Mirzo Ulug'bek tumani": "Mirzo Ulugbek",
    "Olmazor tumani":        "Olmazor",
    "Uchtepa tumani":        "Uchtepa",
    "Yakkasaroy tumani":     "Yakkasaroy",
    "Shayxontohur tumani":   "Shaykhantakhur",
    "Sergeli tumani":        "Sergeli",
    "Bektemir tumani":       "Bektemir",
    "Yangihayot tumani":     "Yangihayot",
}


async def overpass_query(session: aiohttp.ClientSession, query: str) -> dict | None:
    for url in OVERPASS_URLS:
        try:
            async with session.post(
                url,
                data={"data": query},
                timeout=aiohttp.ClientTimeout(total=120),
                ssl=False,
            ) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
        except Exception as e:
            print(f"  ⚠️  {url}: {e}")
    return None


async def create_tables(db: aiosqlite.Connection):
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS streets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tuman TEXT,
            kvartal TEXT,
            name_uz TEXT,
            name_ru TEXT,
            lat REAL,
            lon REAL,
            osm_id INTEGER UNIQUE
        );

        CREATE TABLE IF NOT EXISTS addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tuman TEXT,
            kvartal TEXT,
            street TEXT,
            house_number TEXT,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            full_address TEXT,
            osm_id INTEGER UNIQUE
        );

        CREATE INDEX IF NOT EXISTS idx_streets_tuman ON streets(tuman);
        CREATE INDEX IF NOT EXISTS idx_streets_kvartal ON streets(tuman, kvartal);
        CREATE INDEX IF NOT EXISTS idx_addresses_tuman ON addresses(tuman);
        CREATE INDEX IF NOT EXISTS idx_addresses_kvartal ON addresses(tuman, kvartal);
        CREATE INDEX IF NOT EXISTS idx_addresses_street ON addresses(tuman, street);
    """)
    await db.commit()
    print("✅ Jadvallar yaratildi")


async def fetch_streets(session: aiohttp.ClientSession, db: aiosqlite.Connection):
    """Toshkent shahridagi barcha ko'chalarni yuklash."""
    print("\n🛣  Ko'chalar yuklanmoqda...")

    query = f"""
    [out:json][timeout:120];
    (
      way["highway"]["name"]({BBOX});
    );
    out center tags;
    """

    data = await overpass_query(session, query)
    if not data:
        print("❌ Ko'chalar olishda xato")
        return 0

    elements = data.get("elements", [])
    print(f"   {len(elements)} ta ko'cha topildi")

    batch = []
    for el in elements:
        tags = el.get("tags", {})
        name_uz = tags.get("name:uz") or tags.get("name") or ""
        name_ru = tags.get("name:ru") or ""
        highway = tags.get("highway", "")

        # Faqat asosiy ko'chalar
        if highway in ("footway", "path", "steps", "cycleway", "service"):
            continue
        if not name_uz and not name_ru:
            continue

        center = el.get("center", {})
        lat = center.get("lat") or el.get("lat")
        lon = center.get("lon") or el.get("lon")
        if not lat or not lon:
            continue

        osm_id = el.get("id")
        batch.append((None, None, name_uz, name_ru, lat, lon, osm_id))

    await db.executemany("""
        INSERT OR IGNORE INTO streets (tuman, kvartal, name_uz, name_ru, lat, lon, osm_id)
        VALUES (?,?,?,?,?,?,?)
    """, batch)
    await db.commit()
    print(f"   ✅ {len(batch)} ta ko'cha saqlandi")
    return len(batch)


async def fetch_buildings_with_addresses(
    session: aiohttp.ClientSession, db: aiosqlite.Connection
):
    """Manzili bor binolarni yuklash (addr:housenumber tegli)."""
    print("\n🏠 Manzilli binolar yuklanmoqda...")

    query = f"""
    [out:json][timeout:180];
    (
      way["building"]["addr:housenumber"]({BBOX});
      node["addr:housenumber"]({BBOX});
    );
    out center tags;
    """

    data = await overpass_query(session, query)
    if not data:
        print("❌ Binolar olishda xato")
        return 0

    elements = data.get("elements", [])
    print(f"   {len(elements)} ta manzilli bino topildi")

    batch = []
    for el in elements:
        tags = el.get("tags", {})
        house_number = tags.get("addr:housenumber", "").strip()
        street_uz = tags.get("addr:street:uz") or tags.get("addr:street") or ""
        street_ru = tags.get("addr:street:ru") or ""
        street = street_uz or street_ru

        # Kvartal ma'lumoti
        kvartal_tag = (
            tags.get("addr:quarter")
            or tags.get("addr:subdistrict")
            or tags.get("addr:neighbourhood")
            or ""
        )

        if not house_number:
            continue

        center = el.get("center", {})
        lat = center.get("lat") or el.get("lat")
        lon = center.get("lon") or el.get("lon")
        if not lat or not lon:
            continue

        full_address = " ".join(filter(None, [street, house_number]))
        osm_id = el.get("id")

        batch.append((None, kvartal_tag or None, street, house_number, lat, lon, full_address, osm_id))

    await db.executemany("""
        INSERT OR IGNORE INTO addresses
        (tuman, kvartal, street, house_number, lat, lon, full_address, osm_id)
        VALUES (?,?,?,?,?,?,?,?)
    """, batch)
    await db.commit()
    print(f"   ✅ {len(batch)} ta manzilli bino saqlandi")
    return len(batch)


async def assign_tuman_to_streets(db: aiosqlite.Connection):
    """Ko'chalarga koordinat bo'yicha tuman belgilash (kvartals bbox)."""
    print("\n📍 Ko'chalarga tuman belgilanmoqda...")

    kvartals = await (await db.execute(
        "SELECT tuman, kvartal_n, bbox_lower_lat, bbox_lower_lon, bbox_upper_lat, bbox_upper_lon, lat, lon FROM kvartals"
    )).fetchall()

    streets = await (await db.execute(
        "SELECT id, lat, lon FROM streets WHERE tuman IS NULL OR tuman = ''"
    )).fetchall()

    print(f"   {len(streets)} ta ko'cha tuman belgilanmagan")

    # tuman polygonlari (bbox)
    tuman_boxes = {}
    for kv in kvartals:
        tuman, n, bll, blo, bul, buo, klat, klon = kv
        if tuman not in tuman_boxes:
            tuman_boxes[tuman] = []
        tuman_boxes[tuman].append((bll, blo, bul, buo, klat, klon, n))

    batch = []
    for s_id, lat, lon in streets:
        bbox_tuman = None
        bbox_kvartal = None
        min_dist = float("inf")
        nearest_tuman = None
        nearest_kvartal = None

        for tuman, boxes in tuman_boxes.items():
            for bll, blo, bul, buo, klat, klon, n in boxes:
                # Bbox tekshiruvi
                if bll and blo and bul and buo:
                    if bll <= lat <= bul and blo <= lon <= buo:
                        bbox_tuman = tuman
                        bbox_kvartal = f"{n}-kvartal"
                        break
                # Eng yaqin markaz (fallback)
                if klat and klon:
                    dist = (lat - klat) ** 2 + (lon - klon) ** 2
                    if dist < min_dist:
                        min_dist = dist
                        nearest_tuman = tuman
                        nearest_kvartal = f"{n}-kvartal"
            if bbox_tuman:
                break

        found_tuman = bbox_tuman or nearest_tuman
        found_kvartal = bbox_kvartal or nearest_kvartal

        if found_tuman:
            batch.append((found_tuman, found_kvartal, s_id))

    if batch:
        await db.executemany(
            "UPDATE streets SET tuman=?, kvartal=? WHERE id=?", batch
        )
        await db.commit()
    print(f"   ✅ {len(batch)} ta ko'chaga tuman belgilandi")


async def assign_tuman_to_addresses(db: aiosqlite.Connection):
    """Manzilli binolarga tuman belgilash."""
    print("\n📍 Manzilli binolarga tuman belgilanmoqda...")

    kvartals = await (await db.execute(
        "SELECT tuman, kvartal_n, bbox_lower_lat, bbox_lower_lon, bbox_upper_lat, bbox_upper_lon, lat, lon FROM kvartals"
    )).fetchall()

    addrs = await (await db.execute(
        "SELECT id, lat, lon FROM addresses WHERE tuman IS NULL OR tuman = ''"
    )).fetchall()

    tuman_boxes = {}
    for kv in kvartals:
        tuman, n, bll, blo, bul, buo, klat, klon = kv
        if tuman not in tuman_boxes:
            tuman_boxes[tuman] = []
        tuman_boxes[tuman].append((bll, blo, bul, buo, klat, klon, n))

    batch = []
    for a_id, lat, lon in addrs:
        bbox_tuman = None
        bbox_kvartal = None
        min_dist = float("inf")
        nearest_tuman = None
        nearest_kvartal = None

        for tuman, boxes in tuman_boxes.items():
            for bll, blo, bul, buo, klat, klon, n in boxes:
                if bll and blo and bul and buo:
                    if bll <= lat <= bul and blo <= lon <= buo:
                        bbox_tuman = tuman
                        bbox_kvartal = f"{n}-kvartal"
                        break
                if klat and klon:
                    dist = (lat - klat) ** 2 + (lon - klon) ** 2
                    if dist < min_dist:
                        min_dist = dist
                        nearest_tuman = tuman
                        nearest_kvartal = f"{n}-kvartal"
            if bbox_tuman:
                break

        found_tuman = bbox_tuman or nearest_tuman
        found_kvartal = bbox_kvartal or nearest_kvartal

        if found_tuman:
            batch.append((found_tuman, found_kvartal, a_id))

    if batch:
        await db.executemany(
            "UPDATE addresses SET tuman=?, kvartal=? WHERE id=?", batch
        )
        await db.commit()
    print(f"   ✅ {len(batch)} ta manzilga tuman belgilandi")


async def print_stats(db: aiosqlite.Connection):
    print("\n📊 Statistika:")

    rows = await (await db.execute("""
        SELECT tuman, COUNT(*) FROM streets
        WHERE tuman IS NOT NULL AND tuman != ''
        GROUP BY tuman ORDER BY tuman
    """)).fetchall()
    print("\n🛣  Ko'chalar tumani bo'yicha:")
    for r in rows:
        print(f"   {r[0]}: {r[1]} ta")

    rows2 = await (await db.execute("""
        SELECT tuman, COUNT(*) FROM addresses
        WHERE tuman IS NOT NULL AND tuman != ''
        GROUP BY tuman ORDER BY tuman
    """)).fetchall()
    print("\n🏠 Manzilli binolar tumani bo'yicha:")
    for r in rows2:
        print(f"   {r[0]}: {r[1]} ta")

    total_s = await (await db.execute("SELECT COUNT(*) FROM streets")).fetchone()
    total_a = await (await db.execute("SELECT COUNT(*) FROM addresses")).fetchone()
    print(f"\n✅ Jami: {total_s[0]} ko'cha, {total_a[0]} manzilli bino")


async def main():
    print("🗺  Toshkent ko'chalari va binolari yuklanmoqda...\n")
    print("ℹ️  Bu bir martalik jarayon. Keyin Yandex API kerak emas.\n")

    async with aiosqlite.connect(DB_PATH) as db:
        await create_tables(db)

        async with aiohttp.ClientSession() as session:
            await fetch_streets(session, db)
            await fetch_buildings_with_addresses(session, db)

        await assign_tuman_to_streets(db)
        await assign_tuman_to_addresses(db)
        await print_stats(db)

    print("\n🎉 Tayyor! Endi bot o'z bazasidan ishlaydi.")


if __name__ == "__main__":
    asyncio.run(main())
