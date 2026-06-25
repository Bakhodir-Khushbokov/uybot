"""
Uzbekiston OSM PBF faylidan Toshkent shahri binolarini ajratib DB ga import qilish.
Ishlatish: python3 scripts/parse_osm.py
"""
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import osmium
import aiosqlite

DB_PATH  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uy_bot.db")
PBF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uzbekistan.osm.pbf")

# Toshkent shahri bounding box
TASHKENT_BBOX = (41.18, 69.10, 41.45, 69.45)   # (min_lat, min_lon, max_lat, max_lon)

TUMANLAR_MAP = {
    "bektemir":      "Bektemir tumani",
    "chilonzor":     "Chilonzor tumani",
    "mirzo":         "Mirzo Ulug'bek tumani",
    "ulugbek":       "Mirzo Ulug'bek tumani",
    "olmazor":       "Olmazor tumani",
    "sergeli":       "Sergeli tumani",
    "shayxontohur":  "Shayxontohur tumani",
    "shaykhantakhur":"Shayxontohur tumani",
    "uchtepa":       "Uchtepa tumani",
    "yakkasaroy":    "Yakkasaroy tumani",
    "yakkasaray":    "Yakkasaroy tumani",
    "yangihayot":    "Yangihayot tumani",
    "yunusobod":     "Yunusobod tumani",
    "yunusabad":     "Yunusobod tumani",
}

def guess_tuman(tags: dict) -> str:
    for field in ["addr:district", "addr:city_district", "is_in:district"]:
        val = tags.get(field, "").lower()
        for key, tuman in TUMANLAR_MAP.items():
            if key in val:
                return tuman
    return "Noma'lum tuman"


class BuildingHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.buildings = []
        self.count = 0

    def _process(self, tags, lat, lon):
        if not tags.get("building"):
            return
        min_lat, min_lon, max_lat, max_lon = TASHKENT_BBOX
        if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            return

        # Faqat Toshkent shahri
        city = tags.get("addr:city", "").lower()
        if city and "toshkent" not in city and "ташкент" not in city and city != "":
            # Ba'zi binolarda city yo'q — koordinat asosida kiritamiz
            pass

        dom_number = (
            tags.get("addr:housenumber") or
            tags.get("addr:unit") or
            tags.get("ref") or
            ""
        )
        mahalla = (
            tags.get("addr:suburb") or
            tags.get("addr:quarter") or
            tags.get("addr:neighbourhood") or
            tags.get("addr:subdistrict") or
            "Noma'lum mahalla"
        )
        street = tags.get("addr:street") or tags.get("addr:place") or ""
        kvartal = tags.get("addr:block") or tags.get("block") or ""
        tuman = guess_tuman(dict(tags))

        # Dom nomi yoki nomi bo'lsa ham qo'shamiz
        name = tags.get("name") or tags.get("name:uz") or ""

        self.buildings.append({
            "dom_number": dom_number or name or f"bino_{len(self.buildings)+1}",
            "mahalla":    mahalla,
            "street":     street,
            "kvartal":    kvartal,
            "tuman":      tuman,
            "lat":        lat,
            "lon":        lon,
        })
        self.count += 1
        if self.count % 1000 == 0:
            print(f"  ... {self.count} ta bino o'qildi", flush=True)

    def node(self, n):
        if n.location.valid():
            self._process(n.tags, n.location.lat, n.location.lon)

    def way(self, w):
        try:
            loc = w.nodes[len(w.nodes)//2].location
            if loc.valid():
                self._process(w.tags, loc.lat, loc.lon)
        except Exception:
            pass


async def import_to_db(buildings: list[dict]):
    print(f"\n💾 DB ga import qilinmoqda: {len(buildings)} ta bino...")

    async with aiosqlite.connect(DB_PATH) as db:
        loc_cache = {}
        inserted = 0
        skipped  = 0

        for b in buildings:
            key = ("Toshkent shahri", b["tuman"], b["mahalla"])
            if key not in loc_cache:
                row = await (await db.execute(
                    "SELECT id FROM locations WHERE viloyat=? AND tuman=? AND mahalla=?", key
                )).fetchone()
                if row:
                    loc_cache[key] = row[0]
                else:
                    cur = await db.execute(
                        "INSERT INTO locations (viloyat, tuman, mahalla) VALUES (?,?,?)", key
                    )
                    loc_cache[key] = cur.lastrowid

            loc_id = loc_cache[key]

            # Takrorni oldini olish (koordinat bo'yicha ~5m radius)
            existing = await (await db.execute(
                "SELECT id FROM buildings WHERE location_id=? AND dom_number=?",
                (loc_id, b["dom_number"])
            )).fetchone()

            if existing:
                skipped += 1
                continue

            await db.execute(
                "INSERT INTO buildings (location_id, kvartal, dom_number, lat, lon) VALUES (?,?,?,?,?)",
                (loc_id, b["kvartal"], b["dom_number"], b["lat"], b["lon"])
            )
            inserted += 1

            if inserted % 500 == 0:
                await db.commit()
                print(f"  ... {inserted} ta qo'shildi", flush=True)

        await db.commit()

    print(f"\n✅ Qo'shildi: {inserted}")
    print(f"⏭  O'tkazildi (takror): {skipped}")

    async with aiosqlite.connect(DB_PATH) as db:
        locs = await (await db.execute("SELECT COUNT(*) FROM locations")).fetchone()
        blds = await (await db.execute("SELECT COUNT(*) FROM buildings")).fetchone()
        print(f"\n📊 Jami DB da:")
        print(f"   Locations: {locs[0]}")
        print(f"   Buildings: {blds[0]}")

        # Tuman bo'yicha statistika
        rows = await (await db.execute("""
            SELECT l.tuman, COUNT(b.id) as cnt
            FROM buildings b JOIN locations l ON b.location_id=l.id
            WHERE l.viloyat='Toshkent shahri'
            GROUP BY l.tuman ORDER BY cnt DESC
        """)).fetchall()
        print("\n   Tuman bo'yicha:")
        for r in rows:
            print(f"     {r[0]}: {r[1]} ta bino")


def main():
    print(f"📂 Fayl: {PBF_FILE}")
    print(f"📦 DB:   {DB_PATH}\n")

    print("🔍 OSM fayldan Toshkent binolari o'qilmoqda...")
    handler = BuildingHandler()
    handler.apply_file(PBF_FILE, locations=True)

    print(f"\n📋 Jami {handler.count} ta bino topildi")

    if not handler.buildings:
        print("❌ Hech narsa topilmadi!")
        return

    asyncio.run(import_to_db(handler.buildings))


if __name__ == "__main__":
    main()
