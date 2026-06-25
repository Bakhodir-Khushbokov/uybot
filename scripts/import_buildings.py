"""
Toshkent shahri — OSM dan mahallalar va binolarni import qilish.
Ishlatish: python3 scripts/import_buildings.py
"""
import asyncio
import aiosqlite
import requests
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uy_bot.db")
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

TOSHKENT_TUMANLAR = [
    "Bektemir tumani",
    "Chilonzor tumani",
    "Mirzo Ulug'bek tumani",
    "Olmazor tumani",
    "Sergeli tumani",
    "Shayxontohur tumani",
    "Uchtepa tumani",
    "Yakkasaroy tumani",
    "Yangihayot tumani",
    "Yunusobod tumani",
]

# OSM da ishlatiladigan nomlar (ba'zi tumanlar OSM da boshqacha yozilgan)
OSM_TUMAN_NAMES = {
    "Bektemir tumani":        ["Bektemir", "Бектемир"],
    "Chilonzor tumani":       ["Chilonzor", "Чиланзар"],
    "Mirzo Ulug'bek tumani":  ["Mirzo Ulugbek", "Мирзо Улугбек", "Mirzo-Ulugbek"],
    "Olmazor tumani":         ["Olmazor", "Алмазар"],
    "Sergeli tumani":         ["Sergeli", "Сергели"],
    "Shayxontohur tumani":    ["Shaykhantakhur", "Шайхантахур", "Shayxontohur"],
    "Uchtepa tumani":         ["Uchtepa", "Учтепа"],
    "Yakkasaroy tumani":      ["Yakkasaray", "Яккасарай", "Yakkasaroy"],
    "Yangihayot tumani":      ["Yangihayot", "Янгихаёт"],
    "Yunusobod tumani":       ["Yunusabad", "Юнусабад", "Yunusobod"],
}


def overpass_query(query: str, retries: int = 3) -> dict | None:
    for attempt in range(retries):
        try:
            r = requests.post(OVERPASS_URL, data={"data": query}, timeout=120)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"  ⚠️  Urinish {attempt+1}/{retries}: {e}")
            time.sleep(5 * (attempt + 1))
    return None


def get_center(element: dict) -> tuple[float, float] | None:
    """Element markazini olish."""
    if element.get("type") == "node":
        return element.get("lat"), element.get("lon")
    if "center" in element:
        return element["center"]["lat"], element["center"]["lon"]
    if "geometry" in element:
        geom = element["geometry"]
        if geom:
            lats = [g["lat"] for g in geom if "lat" in g]
            lons = [g["lon"] for g in geom if "lon" in g]
            if lats and lons:
                return sum(lats)/len(lats), sum(lons)/len(lons)
    return None, None


async def get_or_create_location(db, viloyat: str, tuman: str, mahalla: str) -> int:
    row = await (await db.execute(
        "SELECT id FROM locations WHERE viloyat=? AND tuman=? AND mahalla=?",
        (viloyat, tuman, mahalla)
    )).fetchone()
    if row:
        return row[0]
    cur = await db.execute(
        "INSERT INTO locations (viloyat, tuman, mahalla) VALUES (?,?,?)",
        (viloyat, tuman, mahalla)
    )
    return cur.lastrowid


async def building_exists(db, location_id: int, dom_number: str) -> bool:
    row = await (await db.execute(
        "SELECT id FROM buildings WHERE location_id=? AND dom_number=?",
        (location_id, dom_number)
    )).fetchone()
    return row is not None


async def import_tuman(db, tuman_uz: str):
    osm_names = OSM_TUMAN_NAMES.get(tuman_uz, [tuman_uz.replace(" tumani", "")])

    print(f"\n📍 {tuman_uz} ...")

    # 1. Mahallalarni olish
    mahalla_query = f"""
[out:json][timeout:60];
(
  {''.join([f'relation["name"="{n}"]["boundary"="administrative"](41.1,69.1,41.5,69.5);' for n in osm_names])}
  {''.join([f'area["name"="{n}"]["boundary"="administrative"](41.1,69.1,41.5,69.5);' for n in osm_names])}
);
(._;>;);
out body;
"""

    # Soddaroq: to'g'ridan to'g'ri mahallalar
    mahalla_q = f"""
[out:json][timeout:90];
area["name"~"{'|'.join(osm_names)}"]["boundary"="administrative"]->.tuman;
(
  relation["boundary"="administrative"]["admin_level"~"9|10"](area.tuman);
  relation["place"="neighbourhood"](area.tuman);
  relation["place"="suburb"](area.tuman);
);
out tags center;
"""
    data = overpass_query(mahalla_q)
    mahallalar = []
    if data and data.get("elements"):
        for el in data["elements"]:
            name = el.get("tags", {}).get("name:uz") or el.get("tags", {}).get("name")
            if name:
                mahallalar.append(name)

    if not mahallalar:
        print(f"  ⚠️  Mahallalar topilmadi, tuman nomi bilan binolarni qidiramiz")
        mahallalar = ["Umumiy"]

    print(f"  📂 {len(mahallalar)} ta mahalla: {mahallalar[:5]}{'...' if len(mahallalar)>5 else ''}")

    # 2. Har bir mahalla uchun binolarni olish yoki tuman bo'yicha
    bino_query = f"""
[out:json][timeout:120];
area["name"~"{'|'.join(osm_names)}"]["boundary"="administrative"]->.tuman;
(
  way["building"~"apartments|residential|yes"]["addr:housenumber"](area.tuman);
  node["addr:housenumber"]["addr:street"](area.tuman);
);
out center tags;
"""
    bdata = overpass_query(bino_query)
    if not bdata or not bdata.get("elements"):
        print(f"  ℹ️  Binolar topilmadi (addr:housenumber yo'q), koordinatali binolarni olamiz")
        bino_query2 = f"""
[out:json][timeout:120];
area["name"~"{'|'.join(osm_names)}"]["boundary"="administrative"]->.tuman;
(
  way["building"~"apartments|residential"](area.tuman);
);
out center tags;
"""
        bdata = overpass_query(bino_query2)

    if not bdata or not bdata.get("elements"):
        print(f"  ❌ Hech narsa topilmadi")
        return 0, 0

    inserted_loc = 0
    inserted_bld = 0

    for el in bdata["elements"]:
        tags = el.get("tags", {})
        lat, lon = get_center(el)
        if not lat or not lon:
            continue

        dom_number = (
            tags.get("addr:housenumber") or
            tags.get("addr:unit") or
            tags.get("name") or
            f"osm_{el['id']}"
        )

        # Mahalla aniqlanishi
        mahalla = (
            tags.get("addr:suburb") or
            tags.get("addr:quarter") or
            tags.get("addr:neighbourhood") or
            tags.get("addr:city_district") or
            "Noma'lum mahalla"
        )

        kvartal = tags.get("addr:block") or tags.get("block_number") or ""

        loc_id = await get_or_create_location(db, "Toshkent shahri", tuman_uz, mahalla)
        if not await building_exists(db, loc_id, dom_number):
            await db.execute(
                "INSERT INTO buildings (location_id, kvartal, dom_number, lat, lon) VALUES (?,?,?,?,?)",
                (loc_id, kvartal, dom_number, lat, lon)
            )
            inserted_bld += 1
        inserted_loc = 1

    await db.commit()
    print(f"  ✅ {inserted_bld} ta bino qo'shildi")
    return inserted_loc, inserted_bld


async def main():
    print("🏙  Toshkent shahri binolarini import qilish boshlandi\n")
    print(f"📦 DB: {DB_PATH}\n")

    total_bld = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for tuman in TOSHKENT_TUMANLAR:
            _, blds = await import_tuman(db, tuman)
            total_bld += blds
            time.sleep(3)   # Overpass ga yukni kamaytirish

    print(f"\n🎉 Tugadi! Jami {total_bld} ta bino qo'shildi.")
    print("\nDB holati:")

    async with aiosqlite.connect(DB_PATH) as db:
        locs = await (await db.execute("SELECT COUNT(*) FROM locations")).fetchone()
        blds = await (await db.execute("SELECT COUNT(*) FROM buildings")).fetchone()
        print(f"  Locations: {locs[0]}")
        print(f"  Buildings: {blds[0]}")


if __name__ == "__main__":
    asyncio.run(main())
