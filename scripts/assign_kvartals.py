"""
Kvartals jadvalidagi bbox yordamida binolarga kvartal belgilash.
API kerak emas — faqat koordinat solishtirish.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import aiosqlite

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uy_bot.db")


async def main():
    async with aiosqlite.connect(DB_PATH) as db:
        # Barcha kvartallar bbox bilan
        kvartals = await (await db.execute("""
            SELECT id, tuman, kvartal_n,
                   bbox_lower_lat, bbox_lower_lon,
                   bbox_upper_lat, bbox_upper_lon,
                   lat, lon
            FROM kvartals
        """)).fetchall()
        print(f"✅ {len(kvartals)} ta kvartal yuklandi")

        # Toshkent shahridagi barcha binolar
        buildings = await (await db.execute("""
            SELECT b.id, b.lat, b.lon, l.tuman
            FROM buildings b
            JOIN locations l ON b.location_id = l.id
            WHERE l.viloyat = 'Toshkent shahri'
              AND l.tuman != 'Noma''lum tuman'
              AND (b.kvartal IS NULL OR b.kvartal = '')
        """)).fetchall()
        print(f"📦 {len(buildings)} ta bino kvartal belgilanmagan")

        # tuman -> kvartal list
        tuman_kvartals = {}
        for kv in kvartals:
            kv_id, tuman, n, bll, blo, bul, buo, lat, lon = kv
            if tuman not in tuman_kvartals:
                tuman_kvartals[tuman] = []
            tuman_kvartals[tuman].append({
                "n": n,
                "bll": bll, "blo": blo,  # lower lat, lower lon
                "bul": bul, "buo": buo,  # upper lat, upper lon
                "lat": lat, "lon": lon,
            })

        updated = 0
        not_found = 0
        batch = []

        for bino_id, lat, lon, tuman in buildings:
            if lat is None or lon is None:
                not_found += 1
                continue

            kvs = tuman_kvartals.get(tuman, [])
            found_kv = None
            min_dist = float("inf")

            for kv in kvs:
                # Bbox ichida ekanligini tekshir
                if (kv["bll"] <= lat <= kv["bul"] and
                        kv["blo"] <= lon <= kv["buo"]):
                    found_kv = kv["n"]
                    break
                # Bbox mos kelmasa — eng yaqin markazni topamiz (fallback)
                dist = (lat - kv["lat"]) ** 2 + (lon - kv["lon"]) ** 2
                if dist < min_dist:
                    min_dist = dist
                    found_kv = kv["n"]

            if found_kv:
                batch.append((f"{found_kv}-kvartal", bino_id))
                updated += 1
            else:
                not_found += 1

            if len(batch) >= 5000:
                await db.executemany(
                    "UPDATE buildings SET kvartal=? WHERE id=?", batch
                )
                await db.commit()
                batch.clear()
                print(f"  ... {updated} ta yangilandi")

        if batch:
            await db.executemany(
                "UPDATE buildings SET kvartal=? WHERE id=?", batch
            )
            await db.commit()

        print(f"\n✅ Kvartal belgilandi: {updated}")
        print(f"❓ Topilmadi: {not_found}")

        # Statistika
        rows = await (await db.execute("""
            SELECT l.tuman, COUNT(DISTINCT b.kvartal) as kv_cnt, COUNT(b.id) as b_cnt
            FROM buildings b JOIN locations l ON b.location_id=l.id
            WHERE l.viloyat='Toshkent shahri' AND l.tuman!='Noma''lum tuman'
            GROUP BY l.tuman ORDER BY l.tuman
        """)).fetchall()
        print("\n📊 Natija:")
        for r in rows:
            print(f"   {r[0]}: {r[1]} kvartal, {r[2]} bino")


if __name__ == "__main__":
    asyncio.run(main())
