"""
15 ta Yandex API key bilan parallel reverse geocoding.
15,000 so'rov/kun = ~7 kunda barcha Toshkent tugaydi.

Ishlatish:
  1. API_KEYS ro'yxatini to'ldiring
  2. python3 scripts/yandex_multi_key.py
  3. python3 scripts/yandex_multi_key.py --limit 15000 --tuman "Chilonzor tumani"

Cron (har kecha 02:00):
  0 2 * * * cd /Users/boxodir/it/uy_bot && python3 scripts/yandex_multi_key.py >> /tmp/yandex.log 2>&1
"""
import asyncio, aiohttp, aiosqlite, os, sys, argparse, datetime, re, json
from itertools import cycle

DB_PATH  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uy_bot.db")
BASE_URL = "https://geocode-maps.yandex.ru/1.x/"
HEADERS  = {"Referer": "https://localhost/"}

# ── API kalitlarini shu yerga qo'shing ──────────────────────────────────────
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
    # ...
]
# ────────────────────────────────────────────────────────────────────────────

PER_KEY_LIMIT = 980   # Har bir key uchun kunlik limit (20 zaxira)
KV_RE = re.compile(r"(\d+)[- ]й\s+кварт", re.IGNORECASE)


async def geocode_one(session: aiohttp.ClientSession, api_key: str,
                      lat: float, lon: float) -> dict | None:
    params = {
        "apikey":  api_key,
        "geocode": f"{lon},{lat}",
        "format":  "json",
        "lang":    "ru_RU",
        "kind":    "house",
        "results": 1,
    }
    try:
        async with session.get(
            BASE_URL, params=params, headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=8), ssl=False
        ) as r:
            if r.status == 403:
                return {"error": "403"}
            if r.status != 200:
                return None
            data  = await r.json(content_type=None)
            items = data["response"]["GeoObjectCollection"]["featureMember"]
            if not items:
                return None
            geo   = items[0]["GeoObject"]
            meta  = geo["metaDataProperty"]["GeocoderMetaData"]
            comp  = {c["kind"]: c["name"] for c in meta.get("Address", {}).get("Components", [])}
            text  = meta.get("text", "")
            m     = KV_RE.search(text)
            return {
                "house":   comp.get("house", ""),
                "street":  comp.get("street", ""),
                "kvartal": f"{m.group(1)}-kvartal" if m else None,
                "text":    text,
            }
    except Exception:
        return None


async def worker(worker_id: int, api_key: str, rows: list,
                 results: dict, semaphore: asyncio.Semaphore):
    """Har bir worker o'z API key bilan ishlaydi."""
    connector = aiohttp.TCPConnector(limit=3)
    async with aiohttp.ClientSession(connector=connector) as session:
        done = 0
        for bino_id, lat, lon, old_dom, old_kv in rows:
            async with semaphore:
                res = await geocode_one(session, api_key, lat, lon)
                if res and res.get("error") == "403":
                    print(f"  ⚠️  Key {worker_id+1} — 403 xatosi (limit tugagan bo'lishi mumkin)")
                    break
                if res and res.get("house"):
                    results[bino_id] = {
                        "dom":     res["house"],
                        "kvartal": res["kvartal"] or old_kv,
                    }
                    done += 1
                await asyncio.sleep(0.18)  # ~5.5 req/sec per key

        print(f"  ✅ Worker {worker_id+1} (Key ...{api_key[-8:]}): {done} ta yangiladi")


async def main(total_limit: int, tuman_filter: str | None):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    n_keys = len(API_KEYS)
    effective_limit = min(total_limit, n_keys * PER_KEY_LIMIT)

    print(f"{'='*55}")
    print(f"🌙 Yandex Multi-Key Geocoder — {now}")
    print(f"   Kalitlar: {n_keys} ta | Limit: {effective_limit} ta")
    print(f"   Tuman: {tuman_filter or 'barchasi'}")
    print(f"{'='*55}\n")

    # Binolarni yuklash
    async with aiosqlite.connect(DB_PATH) as db:
        if tuman_filter:
            rows = await (await db.execute("""
                SELECT b.id, b.lat, b.lon, b.dom_number, b.kvartal
                FROM buildings b
                JOIN locations l ON b.location_id=l.id
                WHERE b.dom_number LIKE 'bino_%'
                  AND b.lat IS NOT NULL
                  AND l.tuman = ?
                ORDER BY b.kvartal, b.id
                LIMIT ?
            """, (tuman_filter, effective_limit))).fetchall()
        else:
            rows = await (await db.execute("""
                SELECT b.id, b.lat, b.lon, b.dom_number, b.kvartal
                FROM buildings b
                JOIN locations l ON b.location_id=l.id
                WHERE b.dom_number LIKE 'bino_%'
                  AND b.lat IS NOT NULL
                  AND l.viloyat = 'Toshkent shahri'
                  AND l.tuman != 'Noma''lum tuman'
                ORDER BY l.tuman, b.kvartal, b.id
                LIMIT ?
            """, (effective_limit,))).fetchall()

        total_remaining = await (await db.execute(
            "SELECT COUNT(*) FROM buildings WHERE dom_number LIKE 'bino_%'"
        )).fetchone()

    print(f"📦 Bazada qolgan: {total_remaining[0]:,} ta bino_X")
    print(f"📡 Bugun ishlanadi: {len(rows):,} ta\n")

    if not rows:
        print("✅ Hamma bino tayyor!")
        return

    # Rowlarni keylar bo'yicha taqsimlash
    chunks = [[] for _ in range(n_keys)]
    for i, row in enumerate(rows):
        chunks[i % n_keys].append(row)

    print("🔀 Rowlar taqsimlandi:")
    for i, chunk in enumerate(chunks):
        print(f"   Key {i+1}: {len(chunk)} ta")
    print()

    # Parallel ishlatish
    results = {}
    semaphore = asyncio.Semaphore(n_keys * 3)

    tasks = [
        asyncio.create_task(
            worker(i, API_KEYS[i], chunks[i], results, semaphore)
        )
        for i in range(n_keys)
    ]
    await asyncio.gather(*tasks)

    # Bazaga yozish
    print(f"\n💾 {len(results):,} ta natij bazaga yozilmoqda...")
    async with aiosqlite.connect(DB_PATH) as db:
        batch = [(v["dom"], v["kvartal"], k) for k, v in results.items()]
        if batch:
            await db.executemany(
                "UPDATE buildings SET dom_number=?, kvartal=? WHERE id=?",
                batch
            )
            await db.commit()

    # Yakuniy statistika
    kv_fixed = sum(1 for k, v in results.items()
                   if v["kvartal"] != next((r[4] for r in rows if r[0] == k), None))

    print(f"\n{'='*55}")
    print(f"✅ Yangilandi:        {len(results):,} ta")
    print(f"🔄 Kvartal to'g'irl.: {kv_fixed:,} ta")
    print(f"❌ Topilmadi:         {len(rows)-len(results):,} ta")
    remaining_after = total_remaining[0] - len(results)
    days_left = remaining_after // effective_limit if effective_limit > 0 else 0
    print(f"📅 Taxminan {days_left} kun qoldi")
    print(f"{'='*55}")

    # Tuman progress
    async with aiosqlite.connect(DB_PATH) as db:
        stats = await (await db.execute("""
            SELECT l.tuman,
                   SUM(CASE WHEN b.dom_number NOT LIKE 'bino_%' THEN 1 ELSE 0 END) as done,
                   COUNT(b.id) as total
            FROM buildings b JOIN locations l ON b.location_id=l.id
            WHERE l.viloyat='Toshkent shahri' AND l.tuman!='Noma''lum tuman'
            GROUP BY l.tuman ORDER BY done*100/total DESC
        """)).fetchall()
        print("\n📊 Progress:")
        for r in stats:
            done, total = r[1], r[2]
            pct = done * 100 // total if total else 0
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            print(f"  {r[0]:<26} {bar} {pct}% ({done:,}/{total:,})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",  type=int,  default=len(API_KEYS) * PER_KEY_LIMIT)
    parser.add_argument("--tuman",  type=str,  default=None)
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.tuman))
