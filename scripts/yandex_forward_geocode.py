"""
Yandex forward geocoding — kvartal uchun barcha uy raqamlarini olish.
Yandex qanday qaytarsa shundayligicha bazaga yozadi (harf, format o'zgarmaydi).

Ishlatish:
  python3 scripts/yandex_forward_geocode.py --tuman "Chilonzor tumani" --kvartal 1
  python3 scripts/yandex_forward_geocode.py --tuman "Chilonzor tumani"  (barcha kvartallar)
  python3 scripts/yandex_forward_geocode.py --all                        (barcha tumanlar)
"""
import asyncio, aiohttp, aiosqlite, argparse, re, os, datetime

DB_PATH  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uy_bot.db")
BASE_URL = "https://geocode-maps.yandex.ru/1.x/"
HEADERS  = {"Referer": "https://localhost/"}

API_KEYS = [
    "2f67e735-0cf4-44fd-ac6e-dbc4e088bd29",  # Key 1
    "833e8317-5fd1-4797-9540-60fead213fdc",  # Key 2
    "199023fc-9ee0-4d7a-b9b5-d38af07eafc9",  # Key 3
    "e8591410-49fd-4d0a-a353-a9d13be521ed",  # Key 4
    "6cce4640-8dde-4e44-807e-cda5127d4783",  # Key 5
    "ef9f3c17-35a0-4eb6-a4e8-76c605cc2c37",  # Key 6
    "11f28d43-e957-44e2-afc9-22cbb6d0d73b",  # Key 7
    "19a890d7-a11f-43f0-b5fe-a42c32582cad",  # Key 8
    "51e24509-fe25-4ccb-abfb-162ff8302bea",  # Key 9
    "437ee69a-717d-47bc-b6fd-fc15e7cdc880",  # Key 10
    # "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # Key 2 ...
]

# Tuman nomi → Yandex da qanday yoziladi
TUMAN_RU = {
    "Chilonzor tumani":       "Чиланзарский район",
    "Olmazor tumani":         "Алмазарский район",
    "Mirzo Ulug'bek tumani":  "Мирзо-Улугбекский район",
    "Yunusobod tumani":       "Юнусабадский район",
    "Yakkasaroy tumani":      "Яккасарайский район",
    "Uchtepa tumani":         "Учтепинский район",
    "Sergeli tumani":         "Сергелийский район",
    "Bektemir tumani":        "Бектемирский район",
    "Shayxontohur tumani":    "Шайхантахурский район",
    "Yashnobod tumani":       "Яшнободский район",
}

# Kvartal nomi → Yandex formatida
KVARTAL_RU = {
    "Chilonzor tumani": "массив Чиланзар, {n}-й квартал",
    "Olmazor tumani":   "{n}-й квартал",
}

def kvartal_query(tuman: str, kv_n: int, house: str, address_text: str = "") -> str:
    tuman_ru = TUMAN_RU.get(tuman, tuman)
    # Yandex address_text dan massiv nomini ajratib olamiz
    if "массив Чиланзар" in address_text:
        kv = f"массив Чиланзар, {kv_n}-й квартал"
    elif tuman == "Chilonzor tumani":
        kv = f"массив Чиланзар, {kv_n}-й квартал"
    else:
        kv = f"{kv_n}-й квартал"
    return f"Ташкент, {tuman_ru}, {kv}, дом {house}"


async def geocode_one(session: aiohttp.ClientSession, api_key: str, query: str,
                      bbox_lon1: float, bbox_lat1: float,
                      bbox_lon2: float, bbox_lat2: float) -> dict | None:
    params = {
        "apikey":  api_key,
        "geocode": query,
        "format":  "json",
        "lang":    "ru_RU",
        "kind":    "house",
        "results": 1,
        "bbox":    f"{bbox_lon1},{bbox_lat1}~{bbox_lon2},{bbox_lat2}",
        "rspn":    1,
    }
    try:
        async with session.get(BASE_URL, params=params, headers=HEADERS,
                               timeout=aiohttp.ClientTimeout(total=8), ssl=False) as r:
            if r.status == 403:
                return {"error": "403"}
            if r.status != 200:
                return None
            data  = await r.json(content_type=None)
            items = data["response"]["GeoObjectCollection"]["featureMember"]
            if not items:
                return None
            geo  = items[0]["GeoObject"]
            meta = geo["metaDataProperty"]["GeocoderMetaData"]
            comp = {c["kind"]: c["name"] for c in meta.get("Address", {}).get("Components", [])}
            pos  = geo["Point"]["pos"].split()
            house = comp.get("house", "")
            if not house:
                return None
            return {
                "house": house,
                "lon":   float(pos[0]),
                "lat":   float(pos[1]),
                "text":  meta.get("text", ""),
            }
    except Exception:
        return None


async def geocode_kvartal(tuman: str, kv_id: int, kv_n: int,
                          bbox_lon1: float, bbox_lat1: float,
                          bbox_lon2: float, bbox_lat2: float,
                          location_id: int,
                          api_keys: list, max_house: int = 200,
                          address_text: str = ""):
    results = []
    key_cycle = 0

    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        # 1-200 raqamlari + A1-A9
        # Har raqam topilsa, harfli variantlar ham so'raladi (geocode_kvartal ichida)
        suffixes = ["А", "Б", "В", "а", "б", "/1", "/2"]
        candidates = [str(i) for i in range(1, max_house + 1)] + [f"A{i}" for i in range(1, 10)]

        async def query_one(house_input):
            nonlocal key_cycle
            api_key = api_keys[key_cycle % len(api_keys)]
            query = kvartal_query(tuman, kv_n, house_input, address_text)
            res = await geocode_one(session, api_key, query,
                                    bbox_lon1, bbox_lat1, bbox_lon2, bbox_lat2)
            key_cycle += 1
            await asyncio.sleep(0.12)
            return res

        consecutive_misses = 0
        for house_input in candidates:
            res = await query_one(house_input)

            if res and res.get("error") == "403":
                if key_cycle >= len(api_keys):
                    print(f"  ⚠️  Barcha keylar tugadi!")
                    break
                await asyncio.sleep(0.1)
                continue

            if res:
                results.append({"house": res["house"], "lat": res["lat"], "lon": res["lon"]})
                consecutive_misses = 0

                # Topilgan raqam uchun harfli variantlarni ham tekshir
                if house_input.isdigit():
                    for s in suffixes:
                        r2 = await query_one(f"{house_input}{s}")
                        if r2 and not r2.get("error"):
                            results.append({"house": r2["house"], "lat": r2["lat"], "lon": r2["lon"]})
            else:
                consecutive_misses += 1
                if consecutive_misses >= 15 and house_input.isdigit() and int(house_input) > 30:
                    break

    return results


async def main(tuman_filter: str | None, kvartal_filter: int | None, all_tumans: bool):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"{'='*55}")
    print(f"🗺  Yandex Forward Geocoder — {now}")
    print(f"{'='*55}\n")

    async with aiosqlite.connect(DB_PATH) as db:
        # locations dan tuman → location_id olish
        loc_rows = await (await db.execute(
            "SELECT id, tuman FROM locations WHERE viloyat='Toshkent shahri'"
        )).fetchall()
        loc_map = {r[1]: r[0] for r in loc_rows}

        # kvartals dan keraklilarini olish
        if kvartal_filter and tuman_filter:
            kvartals = await (await db.execute(
                "SELECT id, tuman, kvartal_n, lon, bbox_lower_lon, bbox_lower_lat, bbox_upper_lon, bbox_upper_lat, address_text "
                "FROM kvartals WHERE tuman=? AND kvartal_n=?",
                (tuman_filter, kvartal_filter)
            )).fetchall()
        elif tuman_filter:
            kvartals = await (await db.execute(
                "SELECT id, tuman, kvartal_n, lon, bbox_lower_lon, bbox_lower_lat, bbox_upper_lon, bbox_upper_lat, address_text "
                "FROM kvartals WHERE tuman=? ORDER BY kvartal_n",
                (tuman_filter,)
            )).fetchall()
        else:
            kvartals = await (await db.execute(
                "SELECT id, tuman, kvartal_n, lon, bbox_lower_lon, bbox_lower_lat, bbox_upper_lon, bbox_upper_lat, address_text "
                "FROM kvartals ORDER BY tuman, kvartal_n"
            )).fetchall()

    print(f"📍 {len(kvartals)} ta kvartal ishlanadi\n")

    total_added = 0

    for kv in kvartals:
        kv_id, tuman, kv_n, _, bbox_lon1, bbox_lat1, bbox_lon2, bbox_lat2, addr_text = kv
        location_id = loc_map.get(tuman)
        if not location_id:
            continue

        kvartal_str = f"{kv_n}-kvartal"
        print(f"📦 {tuman} — {kvartal_str} ...", end=" ", flush=True)

        results = await geocode_kvartal(
            tuman, kv_id, kv_n,
            bbox_lon1, bbox_lat1, bbox_lon2, bbox_lat2,
            location_id, API_KEYS, address_text=addr_text or ""
        )

        # Takrorlanganlarni olib tashlash (bir xil house raqami)
        seen = {}
        for r in results:
            h = r["house"]
            if h not in seen:
                seen[h] = r

        unique = list(seen.values())

        # Bazaga yozish
        async with aiosqlite.connect(DB_PATH) as db:
            # Avval bu kvartalning eski ma'lumotlarini o'chirish
            await db.execute(
                "DELETE FROM buildings WHERE location_id=? AND kvartal=?",
                (location_id, kvartal_str)
            )
            if unique:
                await db.executemany(
                    "INSERT INTO buildings (location_id, kvartal, dom_number, lat, lon) VALUES (?,?,?,?,?)",
                    [(location_id, kvartal_str, r["house"], r["lat"], r["lon"]) for r in unique]
                )
            await db.commit()

        print(f"{len(unique)} ta bino")
        total_added += len(unique)

        await asyncio.sleep(0.5)

    print(f"\n{'='*55}")
    print(f"✅ Jami qo'shildi: {total_added:,} ta bino")
    print(f"{'='*55}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tuman",   type=str, default=None)
    parser.add_argument("--kvartal", type=int, default=None)
    parser.add_argument("--all",     action="store_true")
    args = parser.parse_args()

    if not args.tuman and not args.all:
        print("Ishlatish:")
        print("  python3 scripts/yandex_forward_geocode.py --tuman 'Chilonzor tumani' --kvartal 1")
        print("  python3 scripts/yandex_forward_geocode.py --tuman 'Chilonzor tumani'")
        print("  python3 scripts/yandex_forward_geocode.py --all")
    else:
        asyncio.run(main(args.tuman, args.kvartal, args.all))
