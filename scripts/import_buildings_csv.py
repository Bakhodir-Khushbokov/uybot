#!/usr/bin/env python3
"""
toshkent_binolar.csv dan buildings jadvaliga import.
Ishlatish: python3 scripts/import_buildings_csv.py
"""
import csv, os, sys, sqlite3

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "uy_bot.db")
CSV_PATH = os.path.join(BASE, "scripts", "toshkent_binolar.csv")

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode=WAL")
c = conn.cursor()

# Location cache
loc_cache = {}

def get_loc_id(viloyat, tuman, mahalla):
    key = (viloyat, tuman, mahalla)
    if key in loc_cache:
        return loc_cache[key]
    c.execute("SELECT id FROM locations WHERE viloyat=? AND tuman=? AND mahalla=?", key)
    row = c.fetchone()
    if row:
        loc_cache[key] = row[0]
        return row[0]
    c.execute("INSERT INTO locations (viloyat, tuman, mahalla) VALUES (?,?,?)", key)
    lid = c.lastrowid
    loc_cache[key] = lid
    return lid

inserted = 0
skipped = 0

with open(CSV_PATH, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        viloyat   = row.get("Viloyat", "").strip()
        tuman     = row.get("Tuman", "").strip()
        mahalla   = row.get("Mahalla", "").strip()
        kvartal   = row.get("Kvartal", "").strip()
        dom       = row.get("Dom raqami", "").strip()
        try:
            lat = float(row.get("Lat", 0))
            lon = float(row.get("Lon", 0))
        except ValueError:
            skipped += 1
            continue

        if not viloyat or not tuman or not dom or not lat or not lon:
            skipped += 1
            continue

        if not mahalla:
            mahalla = "Noma'lum mahalla"

        loc_id = get_loc_id(viloyat, tuman, mahalla)
        c.execute(
            "INSERT INTO buildings (location_id, kvartal, dom_number, lat, lon) VALUES (?,?,?,?,?)",
            (loc_id, kvartal or None, dom, lat, lon)
        )
        inserted += 1

        if inserted % 10000 == 0:
            conn.commit()
            print(f"  {inserted} ta...")

conn.commit()
conn.close()
print(f"\nDone! Inserted: {inserted}, Skipped: {skipped}")
