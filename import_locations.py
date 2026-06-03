"""
Lokatsiyalarni import qilish.

Foydalanish:
  python import_locations.py               # namunaviy ma'lumotlar
  python import_locations.py locations.csv # CSV fayldan import

CSV format (vergul bilan ajratilgan, sarlavha qatori kerak):
  viloyat,tuman,mahalla,postal_code
  Toshkent shahri,Yunusobod tumani,Yunusobod 1-mahalla,100084
"""
import sys
import csv
import asyncio
import aiosqlite

from config import DB_PATH
from database import init_db


async def import_csv(filepath: str):
    await init_db()
    count = 0
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM locations")
        with open(filepath, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                await db.execute(
                    "INSERT INTO locations (viloyat,tuman,mahalla,postal_code) VALUES (?,?,?,?)",
                    (
                        row.get("viloyat", "").strip(),
                        row.get("tuman", "").strip(),
                        row.get("mahalla", "").strip(),
                        row.get("postal_code", "").strip(),
                    ),
                )
                count += 1
        await db.commit()
    print(f"✅ {count} ta hudud import qilindi!")


async def load_sample_data():
    """Test uchun namunaviy ma'lumotlar — Toshkent shahar + bir necha viloyat."""
    await init_db()

    sample = [
        # Toshkent shahri
        ("Toshkent shahri", "Yunusobod tumani",       "Yunusobod 1-mahalla",          "100084"),
        ("Toshkent shahri", "Yunusobod tumani",       "Yunusobod 2-mahalla",          "100084"),
        ("Toshkent shahri", "Yunusobod tumani",       "Yunusobod 3-mahalla",          "100084"),
        ("Toshkent shahri", "Yunusobod tumani",       "Yunusobod 4-mahalla",          "100084"),
        ("Toshkent shahri", "Yunusobod tumani",       "Yunusobod 17-mahalla",         "100084"),
        ("Toshkent shahri", "Mirzo Ulug'bek tumani",  "Qaraqamish mahallasi",         "100128"),
        ("Toshkent shahri", "Mirzo Ulug'bek tumani",  "Do'stlik mahallasi",           "100128"),
        ("Toshkent shahri", "Mirzo Ulug'bek tumani",  "Bog'ishamol mahallasi",        "100128"),
        ("Toshkent shahri", "Chilonzor tumani",       "Chilonzor 1-mahalla",          "100115"),
        ("Toshkent shahri", "Chilonzor tumani",       "Chilonzor 5-mahalla",          "100115"),
        ("Toshkent shahri", "Chilonzor tumani",       "Chilonzor 9-mahalla",          "100115"),
        ("Toshkent shahri", "Chilonzor tumani",       "Chilonzor 14-mahalla",         "100115"),
        ("Toshkent shahri", "Shayxontohur tumani",    "Shayxontohur mahallasi",       "100027"),
        ("Toshkent shahri", "Shayxontohur tumani",    "Hamza mahallasi",              "100027"),
        ("Toshkent shahri", "Uchtepa tumani",         "Uchtepa mahallasi",            "100101"),
        ("Toshkent shahri", "Uchtepa tumani",         "Qoratosh mahallasi",           "100101"),
        ("Toshkent shahri", "Yakkasaroy tumani",      "Yakkasaroy mahallasi",         "100070"),
        ("Toshkent shahri", "Yakkasaroy tumani",      "Labzak mahallasi",             "100070"),
        ("Toshkent shahri", "Olmazor tumani",         "Olmazor mahallasi",            "100140"),
        ("Toshkent shahri", "Olmazor tumani",         "Buyuk ipak yo'li mahallasi",   "100140"),
        ("Toshkent shahri", "Bektemir tumani",        "Bektemir mahallasi",           "100200"),
        ("Toshkent shahri", "Sergeli tumani",         "Sergeli mahallasi",            "100210"),
        ("Toshkent shahri", "Yangihayot tumani",      "Yangihayot mahallasi",         "100220"),
        # Toshkent viloyati
        ("Toshkent viloyati", "Toshkent tumani",      "Kibray mahallasi",             "111221"),
        ("Toshkent viloyati", "Toshkent tumani",      "Zangiota mahallasi",           "111221"),
        ("Toshkent viloyati", "Ohangaron tumani",     "Ohangaron mahallasi",          "110900"),
        ("Toshkent viloyati", "Chirchiq shahri",      "Chirchiq markazi",             "111700"),
        # Qolgan viloyatlar
        ("Samarqand viloyati", "Samarqand shahri",    "Registon mahallasi",           "140100"),
        ("Samarqand viloyati", "Samarqand shahri",    "Siyob mahallasi",              "140100"),
        ("Buxoro viloyati",    "Buxoro shahri",       "Buxoro mahallasi",             "200100"),
        ("Farg'ona viloyati",  "Farg'ona shahri",     "Farg'ona mahallasi",           "150100"),
        ("Farg'ona viloyati",  "Marg'ilon shahri",    "Marg'ilon markazi",            "150300"),
        ("Namangan viloyati",  "Namangan shahri",     "Namangan mahallasi",           "160100"),
        ("Andijon viloyati",   "Andijon shahri",      "Andijon mahallasi",            "170100"),
        ("Qashqadaryo viloyati","Qarshi shahri",      "Qarshi mahallasi",             "180100"),
        ("Surxondaryo viloyati","Termiz shahri",      "Termiz markazi",               "190100"),
        ("Navoiy viloyati",    "Navoiy shahri",       "Navoiy markazi",               "210100"),
        ("Xorazm viloyati",    "Urganch shahri",      "Urganch markazi",              "220100"),
        ("Qoraqalpog'iston",   "Nukus shahri",        "Nukus markazi",                "230100"),
        ("Jizzax viloyati",    "Jizzax shahri",       "Jizzax markazi",               "130100"),
        ("Sirdaryo viloyati",  "Guliston shahri",     "Guliston markazi",             "120100"),
    ]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM locations")
        await db.executemany(
            "INSERT INTO locations (viloyat,tuman,mahalla,postal_code) VALUES (?,?,?,?)",
            sample,
        )

        # Namunaviy binolar (haqiqiy GPS koordinatalar — Toshkent)
        # (location_id, kvartal, dom_number, lat, lon)
        buildings = [
            (1,  None, "1-dom",              41.3390, 69.3580),
            (1,  None, "Navruz 14-dom",      41.3401, 69.3592),
            (1,  None, "Istiqbol 22",        41.3415, 69.3601),
            (3,  None, "3/1-dom",            41.3445, 69.3620),
            (3,  None, "3/5-dom",            41.3452, 69.3635),
            (9,  None, "1-dom",              41.2990, 69.2450),
            (9,  None, "Bunyodkor 12",       41.3005, 69.2460),
            (5,  None, "Shota Rustaveli 32", 41.3480, 69.3700),
            (5,  None, "17/3-dom",           41.3491, 69.3715),
        ]
        await db.executemany(
            "INSERT OR IGNORE INTO buildings (location_id,kvartal,dom_number,lat,lon) VALUES (?,?,?,?,?)",
            buildings,
        )
        await db.commit()

    print(f"✅ {len(sample)} ta hudud va {len(buildings)} ta bino yuklandi!")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(import_csv(sys.argv[1]))
    else:
        print("CSV fayl berilmadi — namunaviy ma'lumotlar yuklanmoqda...")
        asyncio.run(load_sample_data())
