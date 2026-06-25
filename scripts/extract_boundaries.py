"""
PBF fayldan Toshkent tumanlari chegaralarini ajratib, binolarga tuman belgilash.
"""
import sys, os, asyncio, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import osmium
import aiosqlite
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

DB_PATH  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uy_bot.db")
PBF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uzbekistan.osm.pbf")

TUMAN_KEYWORDS = {
    "Bektemir":       "Bektemir tumani",
    "Chilonzor":      "Chilonzor tumani",
    "Чиланзар":       "Chilonzor tumani",
    "Mirzo Ulugbek":   "Mirzo Ulug'bek tumani",
    "Mirzo Ulug'bek":  "Mirzo Ulug'bek tumani",
    "Mirzo Ulug‘bek": "Mirzo Ulug'bek tumani",
    "Mirzo Ulugʻbek":  "Mirzo Ulug'bek tumani",
    "Mirzo-Ulugbek":   "Mirzo Ulug'bek tumani",
    "Мирзо Улугбек":   "Mirzo Ulug'bek tumani",
    "Olmazor":        "Olmazor tumani",
    "Алмазар":        "Olmazor tumani",
    "Sergeli":        "Sergeli tumani",
    "Сергели":        "Sergeli tumani",
    "Shaykhantakhur": "Shayxontohur tumani",
    "Shayxontohur":   "Shayxontohur tumani",
    "Шайхантахур":    "Shayxontohur tumani",
    "Uchtepa":        "Uchtepa tumani",
    "Учтепа":         "Uchtepa tumani",
    "Yakkasaray":     "Yakkasaroy tumani",
    "Yakkasaroy":     "Yakkasaroy tumani",
    "Яккасарай":      "Yakkasaroy tumani",
    "Yangihayot":     "Yangihayot tumani",
    "Янгихаёт":       "Yangihayot tumani",
    "Yunusabad":      "Yunusobod tumani",
    "Yunusobod":      "Yunusobod tumani",
    "Юнусабад":       "Yunusobod tumani",
}

# Toshkent shahri bbox
BBOX = (41.18, 69.10, 41.45, 69.45)


class BoundaryHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.tuman_ways = {}   # tuman_name -> list of way node coords

    def area(self, a):
        tags = dict(a.tags)
        if tags.get("boundary") != "administrative":
            return
        admin_level = tags.get("admin_level", "")
        if admin_level not in ("6", "7", "8"):
            return

        name = tags.get("name:uz") or tags.get("name") or ""
        tuman = None
        for keyword, tuman_name in TUMAN_KEYWORDS.items():
            if keyword.lower() in name.lower():
                tuman = tuman_name
                break

        if not tuman:
            return

        try:
            rings = []
            for ring in a.outer_rings():
                coords = [(n.lon, n.lat) for n in ring if n.location.valid()]
                if len(coords) >= 3:
                    rings.append(coords)
            if rings:
                if tuman not in self.tuman_ways:
                    self.tuman_ways[tuman] = []
                self.tuman_ways[tuman].extend(rings)
                print(f"  ✅ {tuman}: '{name}' (level {admin_level})")
        except Exception as e:
            pass


def build_polygons(tuman_ways: dict) -> dict:
    result = {}
    for tuman, rings in tuman_ways.items():
        polys = []
        for coords in rings:
            try:
                p = Polygon(coords)
                if p.is_valid and not p.is_empty:
                    polys.append(p)
            except Exception:
                pass
        if polys:
            result[tuman] = unary_union(polys)
    return result


async def assign_tumans(tuman_polygons: dict):
    if not tuman_polygons:
        print("❌ Polygon topilmadi")
        return

    print(f"\n💾 {len(tuman_polygons)} ta tuman polygoni bilan binolarga tuman belgilanmoqda...")

    async with aiosqlite.connect(DB_PATH) as db:
        # location_id cache
        loc_cache = {}
        for tuman_name in tuman_polygons:
            row = await (await db.execute(
                "SELECT id FROM locations WHERE viloyat='Toshkent shahri' AND tuman=? LIMIT 1",
                (tuman_name,)
            )).fetchone()
            if row:
                loc_cache[tuman_name] = row[0]
            else:
                cur = await db.execute(
                    "INSERT INTO locations (viloyat, tuman, mahalla) VALUES (?,?,?)",
                    ("Toshkent shahri", tuman_name, "Noma'lum mahalla")
                )
                loc_cache[tuman_name] = cur.lastrowid
        await db.commit()

        # Barcha "Noma'lum tuman" binolari
        rows = await (await db.execute(
            """SELECT b.id, b.lat, b.lon FROM buildings b
               JOIN locations l ON b.location_id=l.id
               WHERE l.tuman=?""",
            ("Noma'lum tuman",)
        )).fetchall()

        print(f"   Binolar soni: {len(rows)}")

        updated = 0
        not_found = 0
        batch = []

        for bino_id, lat, lon in rows:
            if lat is None or lon is None:
                not_found += 1
                continue

            point = Point(lon, lat)
            found = None
            for tuman_name, poly in tuman_polygons.items():
                try:
                    if poly.contains(point):
                        found = tuman_name
                        break
                except Exception:
                    pass

            if found:
                batch.append((loc_cache[found], bino_id))
                updated += 1
            else:
                not_found += 1

            if len(batch) >= 2000:
                await db.executemany("UPDATE buildings SET location_id=? WHERE id=?", batch)
                await db.commit()
                batch.clear()
                print(f"  ... {updated} ta yangilandi", flush=True)

        if batch:
            await db.executemany("UPDATE buildings SET location_id=? WHERE id=?", batch)
            await db.commit()

    print(f"\n✅ Yangilandi: {updated}")
    print(f"❓ Tuman aniqlanmadi: {not_found}")

    async with aiosqlite.connect(DB_PATH) as db:
        rows = await (await db.execute("""
            SELECT l.tuman, COUNT(b.id) as cnt
            FROM buildings b JOIN locations l ON b.location_id=l.id
            WHERE l.viloyat='Toshkent shahri'
            GROUP BY l.tuman ORDER BY cnt DESC
        """)).fetchall()
        print("\n📊 Tuman bo'yicha natija:")
        for r in rows:
            print(f"   {r[0]}: {r[1]} ta bino")


def main():
    print("🔍 PBF fayldan tuman chegaralari o'qilmoqda...\n")
    handler = BoundaryHandler()
    handler.apply_file(PBF_FILE, locations=True)

    print(f"\n🗺  Topilgan tumanlar: {list(handler.tuman_ways.keys())}")

    tuman_polygons = build_polygons(handler.tuman_ways)
    print(f"✅ Polygon yaratildi: {list(tuman_polygons.keys())}")

    asyncio.run(assign_tumans(tuman_polygons))


if __name__ == "__main__":
    main()
