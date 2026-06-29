import sqlite3
import json
from config import DATABASE_PATH


def conn():
    c = sqlite3.connect(DATABASE_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    db = conn()
    cur = db.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY,
            viloyat TEXT NOT NULL,
            tuman TEXT NOT NULL,
            mahalla TEXT NOT NULL,
            postal_code TEXT
        );

        CREATE TABLE IF NOT EXISTS buildings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            dom_nomeri TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            FOREIGN KEY (location_id) REFERENCES locations(id)
        );
        CREATE INDEX IF NOT EXISTS idx_buildings_loc ON buildings(location_id);
        CREATE INDEX IF NOT EXISTS idx_buildings_nom ON buildings(dom_nomeri);

        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            seller_username TEXT,
            seller_phone TEXT,
            video_file_id TEXT NOT NULL,
            xonalar INTEGER NOT NULL,
            sotix TEXT NOT NULL,
            etaj INTEGER NOT NULL,
            etajlilik INTEGER NOT NULL,
            kvadrat REAL NOT NULL,
            nima_qoladi TEXT,
            dom_nomeri TEXT,
            location_id INTEGER NOT NULL,
            narx TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (location_id) REFERENCES locations(id)
        );

        CREATE TABLE IF NOT EXISTS buyer_prefs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id INTEGER NOT NULL UNIQUE,
            buyer_username TEXT,
            location_ids TEXT DEFAULT '[]',
            xonalar TEXT DEFAULT 'hammasi',
            sotix TEXT DEFAULT 'hammasi',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS notified (
            buyer_id INTEGER,
            listing_id INTEGER,
            PRIMARY KEY (buyer_id, listing_id)
        );
    """)
    db.commit()
    db.close()


# ─── Buildings ────────────────────────────────────────────────────────────────

def find_building(location_id: int, dom_nomeri: str):
    """Dom nomeri bo'yicha bazadan bino qidirish. Bir nechta topilishi mumkin."""
    db = conn()
    rows = db.execute(
        """SELECT b.*, l.viloyat, l.tuman, l.mahalla
           FROM buildings b JOIN locations l ON b.location_id = l.id
           WHERE b.location_id = ? AND b.dom_nomeri LIKE ?
           LIMIT 5""",
        (location_id, f"%{dom_nomeri}%"),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def add_building(location_id: int, dom_nomeri: str, lat: float, lon: float) -> int:
    db = conn()
    cur = db.execute(
        "INSERT INTO buildings (location_id, dom_nomeri, lat, lon) VALUES (?,?,?,?)",
        (location_id, dom_nomeri, lat, lon),
    )
    bid = cur.lastrowid
    db.commit()
    db.close()
    return bid


# ─── Locations ────────────────────────────────────────────────────────────────

def get_viloyatlar():
    db = conn()
    rows = db.execute("SELECT DISTINCT viloyat FROM locations ORDER BY viloyat").fetchall()
    db.close()
    return [r["viloyat"] for r in rows]


def get_tumanlar(viloyat: str):
    db = conn()
    rows = db.execute(
        "SELECT DISTINCT tuman FROM locations WHERE viloyat=? ORDER BY tuman", (viloyat,)
    ).fetchall()
    db.close()
    return [r["tuman"] for r in rows]


def get_mahalla_letters(viloyat: str, tuman: str) -> list[str]:
    db = conn()
    rows = db.execute(
        """SELECT DISTINCT UPPER(SUBSTR(mahalla, 1, 1)) as letter
           FROM locations WHERE viloyat=? AND tuman=? AND mahalla != ''
           ORDER BY letter""",
        (viloyat, tuman),
    ).fetchall()
    db.close()
    return [r["letter"] for r in rows]


def search_mahallalar(viloyat: str, tuman: str, query: str = "",
                      limit: int = 8, offset: int = 0, letter: str = ""):
    db = conn()
    params = [viloyat, tuman]
    where = "viloyat=? AND tuman=? AND mahalla != ''"
    if query:
        where += " AND mahalla LIKE ?"
        params.append(f"%{query}%")
    elif letter:
        where += " AND UPPER(SUBSTR(mahalla, 1, 1))=?"
        params.append(letter.upper())
    params += [limit, offset]
    rows = db.execute(
        f"SELECT * FROM locations WHERE {where} ORDER BY mahalla LIMIT ? OFFSET ?",
        params,
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def count_mahallalar(viloyat: str, tuman: str, query: str = "", letter: str = "") -> int:
    db = conn()
    params = [viloyat, tuman]
    where = "viloyat=? AND tuman=? AND mahalla != ''"
    if query:
        where += " AND mahalla LIKE ?"
        params.append(f"%{query}%")
    elif letter:
        where += " AND UPPER(SUBSTR(mahalla, 1, 1))=?"
        params.append(letter.upper())
    row = db.execute(f"SELECT COUNT(*) FROM locations WHERE {where}", params).fetchone()
    db.close()
    return row[0] if row else 0


def get_location(location_id: int):
    db = conn()
    row = db.execute("SELECT * FROM locations WHERE id=?", (location_id,)).fetchone()
    db.close()
    return dict(row) if row else None


# ─── Listings ─────────────────────────────────────────────────────────────────

def add_listing(data: dict) -> int:
    db = conn()
    cur = db.execute(
        """INSERT INTO listings
           (seller_id, seller_username, seller_phone, video_file_id,
            xonalar, sotix, etaj, etajlilik, kvadrat,
            nima_qoladi, dom_nomeri, location_id, narx)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            data["seller_id"], data.get("seller_username"), data["seller_phone"],
            data["video_file_id"], data["xonalar"], data["sotix"],
            data["etaj"], data["etajlilik"], data["kvadrat"],
            data.get("nima_qoladi"), data.get("dom_nomeri"),
            data["location_id"], data["narx"],
        ),
    )
    listing_id = cur.lastrowid
    db.commit()
    db.close()
    return listing_id


def get_listing(listing_id: int):
    db = conn()
    row = db.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
    db.close()
    return dict(row) if row else None


def get_seller_listings(seller_id: int):
    db = conn()
    rows = db.execute(
        "SELECT * FROM listings WHERE seller_id=? ORDER BY created_at DESC", (seller_id,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def deactivate_listing(listing_id: int, seller_id: int):
    db = conn()
    db.execute(
        "UPDATE listings SET status='inactive' WHERE id=? AND seller_id=?",
        (listing_id, seller_id),
    )
    db.commit()
    db.close()


# ─── Buyer prefs ──────────────────────────────────────────────────────────────

def save_buyer_prefs(buyer_id: int, username: str, location_ids: list, xonalar: str, sotix: str):
    db = conn()
    db.execute(
        """INSERT INTO buyer_prefs (buyer_id, buyer_username, location_ids, xonalar, sotix)
           VALUES (?,?,?,?,?)
           ON CONFLICT(buyer_id) DO UPDATE SET
               buyer_username=excluded.buyer_username,
               location_ids=excluded.location_ids,
               xonalar=excluded.xonalar,
               sotix=excluded.sotix,
               updated_at=CURRENT_TIMESTAMP""",
        (buyer_id, username, json.dumps(location_ids), xonalar, sotix),
    )
    db.commit()
    db.close()


def get_buyer_prefs(buyer_id: int):
    db = conn()
    row = db.execute("SELECT * FROM buyer_prefs WHERE buyer_id=?", (buyer_id,)).fetchone()
    db.close()
    if not row:
        return None
    r = dict(row)
    r["location_ids"] = json.loads(r["location_ids"])
    return r


def find_matching_buyers(listing: dict) -> list:
    """Return buyer_id list that match a new listing."""
    db = conn()
    rows = db.execute("SELECT * FROM buyer_prefs").fetchall()
    db.close()

    matches = []
    for row in rows:
        prefs = dict(row)
        prefs["location_ids"] = json.loads(prefs["location_ids"])

        # Location match
        if prefs["location_ids"] and listing["location_id"] not in prefs["location_ids"]:
            continue

        # Xonalar match
        if prefs["xonalar"] != "hammasi":
            wanted = json.loads(prefs["xonalar"])
            if str(listing["xonalar"]) not in wanted:
                continue

        # Sotix match
        if prefs["sotix"] != "hammasi":
            wanted = json.loads(prefs["sotix"])
            if listing["sotix"] not in wanted:
                continue

        matches.append(prefs["buyer_id"])
    return matches


def mark_notified(buyer_id: int, listing_id: int):
    db = conn()
    db.execute(
        "INSERT OR IGNORE INTO notified (buyer_id, listing_id) VALUES (?,?)",
        (buyer_id, listing_id),
    )
    db.commit()
    db.close()
