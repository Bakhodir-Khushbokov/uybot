import aiosqlite
import json
from config import DB_PATH


# ─────────────────────────────────────────────────────────────
#  Init
# ─────────────────────────────────────────────────────────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS users (
            telegram_id   INTEGER PRIMARY KEY,
            phone         TEXT,
            language      TEXT DEFAULT 'uz',
            role          TEXT DEFAULT 'buyer',
            full_name     TEXT,
            username      TEXT,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS locations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            viloyat     TEXT NOT NULL,
            tuman       TEXT NOT NULL,
            mahalla     TEXT NOT NULL,
            postal_code TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_loc_vt ON locations(viloyat, tuman);

        CREATE TABLE IF NOT EXISTS buildings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            kvartal     TEXT,
            dom_number  TEXT NOT NULL,
            lat         REAL NOT NULL,
            lon         REAL NOT NULL,
            FOREIGN KEY (location_id) REFERENCES locations(id)
        );
        CREATE INDEX IF NOT EXISTS idx_bld_loc ON buildings(location_id);

        CREATE TABLE IF NOT EXISTS listings (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id           INTEGER NOT NULL,
            property_type       TEXT NOT NULL,
            dom_type            TEXT,
            location_id         INTEGER,
            building_id         INTEGER,
            lat                 REAL,
            lon                 REAL,
            video_file_id       TEXT,
            xonalar             INTEGER,
            renovation          TEXT,
            floor               INTEGER,
            total_floors        INTEGER,
            area                REAL,
            landmark            TEXT,
            price_amount        REAL,
            price_currency      TEXT DEFAULT 'usd',
            price_display       TEXT,
            phone               TEXT,
            status              TEXT DEFAULT 'pending',
            views_count         INTEGER DEFAULT 0,
            contact_count       INTEGER DEFAULT 0,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (seller_id)   REFERENCES users(telegram_id),
            FOREIGN KEY (location_id) REFERENCES locations(id),
            FOREIGN KEY (building_id) REFERENCES buildings(id)
        );

        CREATE TABLE IF NOT EXISTS favorites (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            listing_id INTEGER NOT NULL,
            saved_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, listing_id)
        );

        CREATE TABLE IF NOT EXISTS search_history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            filter_params TEXT NOT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            filter_params TEXT NOT NULL,
            active        INTEGER DEFAULT 1,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, filter_params)
        );

        CREATE TABLE IF NOT EXISTS price_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id  INTEGER NOT NULL,
            old_price   REAL,
            new_price   REAL,
            currency    TEXT,
            changed_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_counts (
            user_id   INTEGER NOT NULL,
            date      TEXT NOT NULL,
            count     INTEGER DEFAULT 0,
            PRIMARY KEY(user_id, date)
        );
        """)
        await db.commit()


# ─────────────────────────────────────────────────────────────
#  Users
# ─────────────────────────────────────────────────────────────
async def upsert_user(telegram_id: int, phone: str = None,
                      language: str = None, role: str = None,
                      full_name: str = None, username: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (telegram_id, phone, language, role, full_name, username)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                phone     = COALESCE(excluded.phone,     phone),
                language  = COALESCE(excluded.language,  language),
                role      = COALESCE(excluded.role,      role),
                full_name = COALESCE(excluded.full_name, full_name),
                username  = COALESCE(excluded.username,  username)
        """, (telegram_id, phone, language, role, full_name, username))
        await db.commit()


async def get_user(telegram_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


# ─────────────────────────────────────────────────────────────
#  Locations
# ─────────────────────────────────────────────────────────────
async def get_viloyatlar() -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT DISTINCT viloyat FROM locations ORDER BY viloyat")
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def get_tumanlar(viloyat: str) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT DISTINCT tuman FROM locations WHERE viloyat=? ORDER BY tuman", (viloyat,))
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def search_mahallalar(viloyat: str, tuman: str, query: str = "", limit: int = 8, offset: int = 0) -> list[dict]:
    """
    If viloyat/tuman are empty strings, search across all locations by mahalla name.
    Used by admin panel for cross-location search.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if not viloyat and not tuman:
            # Admin-style global search
            pat = f"%{query}%" if query else "%"
            cur = await db.execute(
                "SELECT * FROM locations WHERE mahalla LIKE ? OR viloyat LIKE ? OR tuman LIKE ? ORDER BY viloyat,tuman,mahalla LIMIT ? OFFSET ?",
                (pat, pat, pat, limit, offset))
        elif query:
            cur = await db.execute(
                "SELECT * FROM locations WHERE viloyat=? AND tuman=? AND mahalla LIKE ? ORDER BY mahalla LIMIT ? OFFSET ?",
                (viloyat, tuman, f"%{query}%", limit, offset))
        else:
            cur = await db.execute(
                "SELECT * FROM locations WHERE viloyat=? AND tuman=? ORDER BY mahalla LIMIT ? OFFSET ?",
                (viloyat, tuman, limit, offset))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def count_mahallalar(viloyat: str, tuman: str, query: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        if not viloyat and not tuman:
            pat = f"%{query}%" if query else "%"
            cur = await db.execute(
                "SELECT COUNT(*) FROM locations WHERE mahalla LIKE ? OR viloyat LIKE ? OR tuman LIKE ?",
                (pat, pat, pat))
        elif query:
            cur = await db.execute(
                "SELECT COUNT(*) FROM locations WHERE viloyat=? AND tuman=? AND mahalla LIKE ?",
                (viloyat, tuman, f"%{query}%"))
        else:
            cur = await db.execute(
                "SELECT COUNT(*) FROM locations WHERE viloyat=? AND tuman=?",
                (viloyat, tuman))
        row = await cur.fetchone()
        return row[0] if row else 0


async def get_location(location_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM locations WHERE id=?", (location_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def add_location(viloyat: str, tuman: str = "", mahalla: str = "", postal_code: str = "") -> int:
    """
    Add a location record.  tuman/mahalla may be empty when adding
    just a viloyat placeholder — use empty string, not NULL,
    so existing UNIQUE / LIKE queries stay consistent.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO locations (viloyat,tuman,mahalla,postal_code) VALUES (?,?,?,?)",
            (viloyat, tuman, mahalla, postal_code))
        await db.commit()
        return cur.lastrowid


async def delete_location(location_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM locations WHERE id=?", (location_id,))
        await db.commit()


# ─────────────────────────────────────────────────────────────
#  Buildings
# ─────────────────────────────────────────────────────────────
async def find_buildings(location_id: int | None, query: str = "", limit: int = 8) -> list[dict]:
    """location_id=None means search across all buildings (admin use)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if location_id is None:
            pat = f"%{query}%" if query else "%"
            cur = await db.execute(
                "SELECT * FROM buildings WHERE dom_number LIKE ? LIMIT ?",
                (pat, limit))
        elif query:
            cur = await db.execute(
                "SELECT * FROM buildings WHERE location_id=? AND dom_number LIKE ? LIMIT ?",
                (location_id, f"%{query}%", limit))
        else:
            cur = await db.execute(
                "SELECT * FROM buildings WHERE location_id=? ORDER BY dom_number LIMIT ?",
                (location_id, limit))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_building(building_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM buildings WHERE id=?", (building_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def add_building(location_id: int, dom_number: str,
                       lat: float, lon: float, kvartal: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO buildings (location_id,kvartal,dom_number,lat,lon) VALUES (?,?,?,?,?)",
            (location_id, kvartal, dom_number, lat, lon))
        await db.commit()
        return cur.lastrowid


async def delete_building(building_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM buildings WHERE id=?", (building_id,))
        await db.commit()


# ─────────────────────────────────────────────────────────────
#  Listings
# ─────────────────────────────────────────────────────────────
async def add_listing(data: dict) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO listings
              (seller_id, property_type, dom_type, location_id, building_id,
               lat, lon, video_file_id, xonalar, renovation, floor, total_floors,
               area, landmark, price_amount, price_currency, price_display, phone)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data["seller_id"], data["property_type"], data.get("dom_type"),
            data.get("location_id"), data.get("building_id"),
            data.get("lat"), data.get("lon"), data.get("video_file_id"),
            data.get("xonalar"), data.get("renovation"),
            data.get("floor"), data.get("total_floors"),
            data.get("area"), data.get("landmark"),
            data.get("price_amount"), data.get("price_currency", "usd"),
            data.get("price_display"), data.get("phone"),
        ))
        await db.commit()
        return cur.lastrowid


async def get_listing(listing_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM listings WHERE id=?", (listing_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_seller_listings(seller_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM listings WHERE seller_id=? ORDER BY created_at DESC LIMIT 10",
            (seller_id,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def update_listing_status(listing_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE listings SET status=? WHERE id=?", (status, listing_id))
        await db.commit()


async def search_listings(property_type: str, location_id: int = None,
                          xonalar: int = None, dom_type: str = None,
                          renovation: str = None, limit: int = 10, offset: int = 0) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        conditions = ["status='active'", "property_type=?"]
        params: list = [property_type]
        if location_id:
            conditions.append("location_id=?");  params.append(location_id)
        if xonalar:
            conditions.append("xonalar=?");       params.append(xonalar)
        if dom_type:
            conditions.append("dom_type=?");      params.append(dom_type)
        if renovation:
            conditions.append("renovation=?");    params.append(renovation)
        where = " AND ".join(conditions)
        params += [limit, offset]
        cur = await db.execute(
            f"SELECT * FROM listings WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def increment_views(listing_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE listings SET views_count=views_count+1 WHERE id=?", (listing_id,))
        await db.commit()


async def increment_contacts(listing_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE listings SET contact_count=contact_count+1 WHERE id=?", (listing_id,))
        await db.commit()


# ─────────────────────────────────────────────────────────────
#  Daily listing count (spam limit)
# ─────────────────────────────────────────────────────────────
async def get_daily_count(user_id: int) -> int:
    from datetime import date
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT count FROM daily_counts WHERE user_id=? AND date=?", (user_id, today))
        row = await cur.fetchone()
        return row[0] if row else 0


async def increment_daily_count(user_id: int):
    from datetime import date
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO daily_counts (user_id,date,count) VALUES (?,?,1)
            ON CONFLICT(user_id,date) DO UPDATE SET count=count+1
        """, (user_id, today))
        await db.commit()


# ─────────────────────────────────────────────────────────────
#  Favorites
# ─────────────────────────────────────────────────────────────
async def add_favorite(user_id: int, listing_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO favorites (user_id,listing_id) VALUES (?,?)",
            (user_id, listing_id))
        await db.commit()


async def remove_favorite(user_id: int, listing_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM favorites WHERE user_id=? AND listing_id=?",
            (user_id, listing_id))
        await db.commit()


async def get_favorites(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT l.* FROM listings l
            JOIN favorites f ON f.listing_id=l.id
            WHERE f.user_id=? ORDER BY f.saved_at DESC LIMIT 20
        """, (user_id,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
#  Search history
# ─────────────────────────────────────────────────────────────
async def save_search(user_id: int, filter_params: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO search_history (user_id,filter_params) VALUES (?,?)",
            (user_id, json.dumps(filter_params, ensure_ascii=False)))
        # Keep last 50
        await db.execute("""
            DELETE FROM search_history WHERE id NOT IN (
                SELECT id FROM search_history WHERE user_id=?
                ORDER BY created_at DESC LIMIT 50
            ) AND user_id=?
        """, (user_id, user_id))
        await db.commit()


async def get_search_history(user_id: int, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM search_history WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit))
        rows = await cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            parsed = json.loads(d["filter_params"])
            d["filter_params"] = parsed
            d["filters"] = parsed   # alias used in buyer.py history display
            result.append(d)
        return result


# ─────────────────────────────────────────────────────────────
#  Subscriptions
# ─────────────────────────────────────────────────────────────
async def save_subscription(user_id: int, filter_params: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        key = json.dumps(filter_params, ensure_ascii=False, sort_keys=True)
        await db.execute("""
            INSERT INTO subscriptions (user_id,filter_params) VALUES (?,?)
            ON CONFLICT(user_id,filter_params) DO UPDATE SET active=1
        """, (user_id, key))
        await db.commit()


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        users     = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        listings  = (await (await db.execute("SELECT COUNT(*) FROM listings")).fetchone())[0]
        locations = (await (await db.execute("SELECT COUNT(*) FROM locations")).fetchone())[0]
        buildings = (await (await db.execute("SELECT COUNT(*) FROM buildings")).fetchone())[0]
    return {"users": users, "listings": listings, "locations": locations, "buildings": buildings}


async def get_matching_subscribers(listing: dict) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, filter_params FROM subscriptions WHERE active=1")
        rows = await cur.fetchall()
    matches = []
    for user_id, fp_str in rows:
        try:
            fp = json.loads(fp_str)
        except Exception:
            continue
        if fp.get("property_type") and fp["property_type"] != listing.get("property_type"):
            continue
        if fp.get("location_id") and fp["location_id"] != listing.get("location_id"):
            continue
        if fp.get("xonalar") and fp["xonalar"] != listing.get("xonalar"):
            continue
        matches.append(user_id)
    return matches
