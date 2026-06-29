#!/usr/bin/env python3
"""
Toshkent shahar kvartal CSV fayllaridan buildings jadvaliga kvartal ma'lumotlarini import qiladi.
Mavjud binolarni lat/lon bo'yicha topib yangilaydi, yangilarini qo'shadi.
"""
import csv, os, glob, sqlite3

CSV_DIR = "/root/uybot/scripts/kvartal_csvs/"
DB_PATH = "/root/uybot/uy_bot.db"

def fix(s):
    return s.strip().replace('‘', "'").replace('’', "'")

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode=WAL")
c = conn.cursor()

# location cache
loc_cache = {}

def get_loc_id(viloyat, tuman):
    key = (viloyat, tuman)
    if key in loc_cache:
        return loc_cache[key]
    # Toshkent shahar uchun mahalla = tuman nomi (yoki "Noma'lum")
    c.execute("SELECT id FROM locations WHERE viloyat=? AND tuman=? LIMIT 1", key)
    row = c.fetchone()
    if row:
        loc_cache[key] = row[0]
        return row[0]
    # Yangi location yarat
    c.execute("INSERT INTO locations (viloyat, tuman, mahalla) VALUES (?,?,?)", (viloyat, tuman, tuman))
    lid = c.lastrowid
    loc_cache[key] = lid
    return lid

updated = 0
inserted = 0
skipped = 0

csv_files = sorted(glob.glob(os.path.join(CSV_DIR, "*.csv")))
print(f"{len(csv_files)} ta CSV fayl topildi")

for csv_file in csv_files:
    print(f"\nO'qilmoqda: {os.path.basename(csv_file)}")
    with open(csv_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            viloyat = fix(row.get("Viloyat", ""))
            tuman   = fix(row.get("Tuman", ""))
            kvartal = fix(row.get("Kvartal", ""))
            dom     = fix(row.get("Dom raqami", ""))
            try:
                lat = float(row.get("Lat", "") or 0)
                lon = float(row.get("Lon", "") or 0)
            except ValueError:
                skipped += 1
                continue

            if not viloyat or not tuman or not kvartal or not dom or not lat or not lon:
                skipped += 1
                continue

            # Avval mavjud binoni lat/lon bo'yicha qidir va yanqila
            c.execute(
                "UPDATE buildings SET kvartal=? WHERE ROUND(lat,6)=ROUND(?,6) AND ROUND(lon,6)=ROUND(?,6)",
                (kvartal, lat, lon)
            )
            if c.rowcount > 0:
                updated += c.rowcount
            else:
                # Mavjud emas — yangi qo'sh
                loc_id = get_loc_id(viloyat, tuman)
                c.execute(
                    "INSERT INTO buildings (location_id, kvartal, dom_number, lat, lon) VALUES (?,?,?,?,?)",
                    (loc_id, kvartal, dom, lat, lon)
                )
                inserted += 1

    conn.commit()
    print(f"  Yangilangan: {updated}, Yangi: {inserted}, O'tkazib yuborilgan: {skipped}")

conn.commit()
conn.close()
print(f"\nJami: yangilangan={updated}, yangi={inserted}, o'tkazilgan={skipped}")
