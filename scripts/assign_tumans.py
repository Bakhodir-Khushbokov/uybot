"""
Har bir binoga koordinat asosida to'g'ri tuman belgilash.
Tuman chegaralari OSM dan olinadi, shapely bilan point-in-polygon tekshiruvi.
"""
import sys, os, asyncio, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiosqlite
import requests
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import unary_union

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uy_bot.db")

# Toshkent shahri tumanlarining OSM relation ID lari
TUMAN_OSM_IDS = {
    "Bektemir tumani":       1273148,
    "Chilonzor tumani":      1273150,
    "Mirzo Ulug'bek tumani": 1273151,
    "Olmazor tumani":        1273152,
    "Sergeli tumani":        1273153,
    "Shayxontohur tumani":   1273154,
    "Uchtepa tumani":        1273155,
    "Yakkasaroy tumani":     1273156,
    "Yangihayot tumani":     1273157,
    "Yunusobod tumani":      1273158,
}

OVERPASS_MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tuman_polygons.json")


def fetch_tuman_polygon(tuman_name: str, osm_id: int) -> object | None:
    """OSM dan tuman chegarasini polygon sifatida olish."""
    query = f"""
[out:json][timeout:30];
relation({osm_id});
out geom;
"""
    for mirror in OVERPASS_MIRRORS:
        try:
            r = requests.post(mirror, data={"data": query}, timeout=40)
            if r.status_code != 200:
                continue
            data = r.json()
            els = data.get("elements", [])
            if not els:
                continue

            el = els[0]
            polygons = []
            outer_ways = [m for m in el.get("members", []) if m.get("role") == "outer"]

            for way in outer_ways:
                coords = [(g["lon"], g["lat"]) for g in way.get("geometry", []) if "lat" in g]
                if len(coords) >= 3:
                    try:
                        polygons.append(Polygon(coords))
                    except Exception:
                        pass

            if polygons:
                merged = unary_union(polygons)
                print(f"  ✅ {tuman_name}: polygon olindi ({len(polygons)} qism)")
                return merged
        except Exception as e:
            print(f"  ⚠️  {mirror}: {e}")
        time.sleep(1)

    print(f"  ❌ {tuman_name}: polygon olinmadi")
    return None


async def update_buildings(tuman_polygons: dict):
    print(f"\n💾 Binolarga tuman belgilanmoqda...")

    async with aiosqlite.connect(DB_PATH) as db:
        # Barcha binolarni olish
        rows = await (await db.execute(
            "SELECT b.id, b.lat, b.lon, l.tuman FROM buildings b JOIN locations l ON b.location_id=l.id WHERE l.tuman=?",
            ("Noma'lum tuman",)
        )).fetchall()

        print(f"   Tekshiriladigan binolar: {len(rows)}")

        updated = 0
        not_found = 0
        batch = []

        # Tuman location_id larini oldindan yuklash
        loc_cache = {}
        for tuman_name in tuman_polygons.keys():
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

        for bino_id, lat, lon, _ in rows:
            if lat is None or lon is None:
                not_found += 1
                continue

            point = Point(lon, lat)
            found_tuman = None

            for tuman_name, polygon in tuman_polygons.items():
                if polygon and polygon.contains(point):
                    found_tuman = tuman_name
                    break

            if found_tuman and found_tuman in loc_cache:
                batch.append((loc_cache[found_tuman], bino_id))
                updated += 1
            else:
                not_found += 1

            if len(batch) >= 1000:
                await db.executemany(
                    "UPDATE buildings SET location_id=? WHERE id=?", batch
                )
                await db.commit()
                batch.clear()
                print(f"  ... {updated} ta yangilandi", flush=True)

        if batch:
            await db.executemany("UPDATE buildings SET location_id=? WHERE id=?", batch)
            await db.commit()

    print(f"\n✅ Yangilandi: {updated}")
    print(f"❓ Tuman aniqlanmadi: {not_found}")

    # Statistika
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await (await db.execute("""
            SELECT l.tuman, COUNT(b.id) as cnt
            FROM buildings b JOIN locations l ON b.location_id=l.id
            WHERE l.viloyat='Toshkent shahri'
            GROUP BY l.tuman ORDER BY cnt DESC
        """)).fetchall()
        print("\n📊 Tuman bo'yicha:")
        for r in rows:
            print(f"   {r[0]}: {r[1]} ta bino")


def save_cache(raw: dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(raw, f)


def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def coords_to_polygon(coords_list):
    """Koordinatalar ro'yxatidan Polygon yaratish."""
    polygons = []
    for coords in coords_list:
        if len(coords) >= 3:
            try:
                polygons.append(Polygon(coords))
            except Exception:
                pass
    if polygons:
        return unary_union(polygons)
    return None


def main():
    print("🗺  Tuman chegaralari yuklanmoqda (OSM)...\n")

    # Cache dan yuklash
    cache = load_cache()
    tuman_polygons = {}
    raw_cache = dict(cache)

    for tuman_name, osm_id in TUMAN_OSM_IDS.items():
        if tuman_name in cache:
            poly = coords_to_polygon(cache[tuman_name])
            tuman_polygons[tuman_name] = poly
            print(f"  📦 {tuman_name}: cache dan yuklandi")
            continue

        print(f"→ {tuman_name}")
        poly = fetch_tuman_polygon(tuman_name, osm_id)
        tuman_polygons[tuman_name] = poly

        if poly is not None:
            # Cache ga saqlash (koordinatlar sifatida)
            if hasattr(poly, "geoms"):
                raw_cache[tuman_name] = [list(p.exterior.coords) for p in poly.geoms]
            else:
                raw_cache[tuman_name] = [list(poly.exterior.coords)]
            save_cache(raw_cache)

        time.sleep(2)

    found = sum(1 for p in tuman_polygons.values() if p is not None)
    print(f"\n{found}/{len(TUMAN_OSM_IDS)} ta tuman polygon olindi")

    if found == 0:
        print("❌ Hech qanday polygon olinmadi — internet yoki OSM ID tekshiring")
        return

    asyncio.run(update_buildings(tuman_polygons))


if __name__ == "__main__":
    main()
