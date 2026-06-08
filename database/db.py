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
            transaction_type    TEXT DEFAULT 'sotish',
            rent_for            TEXT,
            jihoz               TEXT,
            balkon              TEXT,
            has_commission      INTEGER DEFAULT 0,
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

        CREATE TABLE IF NOT EXISTS reports (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id   INTEGER NOT NULL,
            reporter_id  INTEGER NOT NULL,
            reason       TEXT NOT NULL,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(listing_id, reporter_id)
        );
        CREATE INDEX IF NOT EXISTS idx_rep_listing ON reports(listing_id);

        CREATE TABLE IF NOT EXISTS admins (
            telegram_id  INTEGER PRIMARY KEY,
            full_name    TEXT,
            username     TEXT,
            role         TEXT DEFAULT 'admin',
            added_by     INTEGER,
            added_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS feedbacks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            sender      TEXT,
            label       TEXT,
            text        TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS organizations (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            category     TEXT NOT NULL,
            name         TEXT NOT NULL,
            address      TEXT,
            phone        TEXT,
            work_hours   TEXT,
            lat          REAL,
            lon          REAL,
            photo_id     TEXT,
            description  TEXT,
            active       INTEGER DEFAULT 1,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_org_cat ON organizations(category, active);

        CREATE TABLE IF NOT EXISTS notary_orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            listing_id      INTEGER,
            doc_file_id     TEXT,
            doc_type        TEXT,
            payment_file_id TEXT,
            status          TEXT DEFAULT 'new',
            assigned_to     INTEGER,
            admin_note      TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)     REFERENCES users(telegram_id),
            FOREIGN KEY (listing_id)  REFERENCES listings(id)
        );
        CREATE INDEX IF NOT EXISTS idx_notary_user   ON notary_orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_notary_status ON notary_orders(status);
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
               area, landmark, price_amount, price_currency, price_display, phone,
               transaction_type, rent_for, jihoz, balkon, has_commission)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data["seller_id"], data["property_type"], data.get("dom_type"),
            data.get("location_id"), data.get("building_id"),
            data.get("lat"), data.get("lon"), data.get("video_file_id"),
            data.get("xonalar"), data.get("renovation"),
            data.get("floor"), data.get("total_floors"),
            data.get("area"), data.get("landmark"),
            data.get("price_amount"), data.get("price_currency", "usd"),
            data.get("price_display"), data.get("phone"),
            data.get("transaction_type", "sotish"), data.get("rent_for"),
            data.get("jihoz"), data.get("balkon"),
            1 if data.get("has_commission") else 0,
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
                          renovation: str = None, transaction_type: str = None,
                          limit: int = 10, offset: int = 0) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        conditions = ["status='active'", "property_type=?"]
        params: list = [property_type]
        if location_id:
            conditions.append("location_id=?");       params.append(location_id)
        if xonalar:
            conditions.append("xonalar=?");            params.append(xonalar)
        if dom_type:
            conditions.append("dom_type=?");           params.append(dom_type)
        if renovation:
            conditions.append("renovation=?");         params.append(renovation)
        if transaction_type:
            conditions.append("transaction_type=?");   params.append(transaction_type)
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
        users    = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        listings = (await (await db.execute("SELECT COUNT(*) FROM listings")).fetchone())[0]
        active   = (await (await db.execute("SELECT COUNT(*) FROM listings WHERE status='active'")).fetchone())[0]
        pending  = (await (await db.execute("SELECT COUNT(*) FROM listings WHERE status='pending'")).fetchone())[0]
        locs     = (await (await db.execute("SELECT COUNT(*) FROM locations")).fetchone())[0]
        blds     = (await (await db.execute("SELECT COUNT(*) FROM buildings")).fetchone())[0]
    return {
        "users": users, "listings": listings,
        "active_listings": active, "pending_listings": pending,
        "locations": locs, "buildings": blds,
    }


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


# ─────────────────────────────────────────────────────────────
#  Reports
# ─────────────────────────────────────────────────────────────
async def add_report(listing_id: int, reporter_id: int, reason: str) -> dict:
    """
    Shikoyat qo'shadi.
    Qaytaradi: {"added": bool, "total": int}
    added=False → bu odam allaqachon shikoyat qilgan
    """
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO reports (listing_id, reporter_id, reason) VALUES (?,?,?)",
                (listing_id, reporter_id, reason),
            )
            await db.commit()
        except Exception:
            return {"added": False, "total": await _report_count(db, listing_id)}

        total = await _report_count(db, listing_id)

        # 5 ta yetsa → avtomatik bloklash
        if total >= 5:
            await db.execute(
                "UPDATE listings SET status='blocked' WHERE id=?", (listing_id,)
            )
            await db.commit()

        return {"added": True, "total": total}


async def _report_count(db, listing_id: int) -> int:
    cur = await db.execute(
        "SELECT COUNT(*) FROM reports WHERE listing_id=?", (listing_id,)
    )
    row = await cur.fetchone()
    return row[0] if row else 0


async def get_report_count(listing_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        return await _report_count(db, listing_id)


async def get_reports_for_listing(listing_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM reports WHERE listing_id=? ORDER BY created_at DESC",
            (listing_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_listings_by_status(status: str, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM listings WHERE status=? ORDER BY created_at DESC LIMIT ?",
            (status, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
#  Admins
# ─────────────────────────────────────────────────────────────
async def get_admin_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT telegram_id FROM admins")
        rows = await cur.fetchall()
        return [r[0] for r in rows]

async def get_all_admins() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM admins ORDER BY added_at")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def add_admin(telegram_id: int, full_name: str = "", username: str = "",
                    added_by: int = 0, role: str = "admin"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO admins (telegram_id, full_name, username, role, added_by) VALUES (?,?,?,?,?)",
            (telegram_id, full_name, username, role, added_by),
        )
        await db.commit()


async def get_notary_admin_ids() -> list[int]:
    """Notarius rolidagi adminlar ID lari."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT telegram_id FROM admins WHERE role='notarius'"
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def get_notary_report() -> list[dict]:
    """Har bir notarius bo'yicha zayavkalar hisoboti."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT
                a.telegram_id, a.full_name, a.username,
                COUNT(n.id)                                          AS total,
                SUM(CASE WHEN n.status='done'     THEN 1 ELSE 0 END) AS done,
                SUM(CASE WHEN n.status='rejected' THEN 1 ELSE 0 END) AS rejected,
                SUM(CASE WHEN n.status IN('new','payment_check','processing') THEN 1 ELSE 0 END) AS active
            FROM admins a
            LEFT JOIN notary_orders n ON n.assigned_to = a.telegram_id
            WHERE a.role = 'notarius'
            GROUP BY a.telegram_id
        """)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def remove_admin(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admins WHERE telegram_id=?", (telegram_id,))
        await db.commit()

async def get_feedback_list(limit: int = 20) -> list[dict]:
    """Oxirgi feedback xabarlari (search_history dan emas, alohida jadvaldan agar bo'lsa)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        try:
            cur = await db.execute(
                "SELECT * FROM feedbacks ORDER BY created_at DESC LIMIT ?", (limit,)
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []


# ─────────────────────────────────────────────────────────────
#  Organizations
# ─────────────────────────────────────────────────────────────
async def get_org_categories() -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT DISTINCT category FROM organizations WHERE active=1 ORDER BY category"
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def get_orgs_by_category(category: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM organizations WHERE category=? AND active=1 ORDER BY name",
            (category,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_org(org_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM organizations WHERE id=?", (org_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def add_org(data: dict) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO organizations
               (category, name, address, phone, work_hours, lat, lon, photo_id, description)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (data.get("category"), data.get("name"), data.get("address"),
             data.get("phone"), data.get("work_hours"),
             data.get("lat"), data.get("lon"),
             data.get("photo_id"), data.get("description")),
        )
        await db.commit()
        return cur.lastrowid


async def update_org(org_id: int, data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE organizations SET
               category=COALESCE(?,category), name=COALESCE(?,name),
               address=COALESCE(?,address), phone=COALESCE(?,phone),
               work_hours=COALESCE(?,work_hours), photo_id=COALESCE(?,photo_id),
               description=COALESCE(?,description), active=COALESCE(?,active)
               WHERE id=?""",
            (data.get("category"), data.get("name"), data.get("address"),
             data.get("phone"), data.get("work_hours"),
             data.get("photo_id"), data.get("description"),
             data.get("active"), org_id),
        )
        await db.commit()


async def delete_org(org_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE organizations SET active=0 WHERE id=?", (org_id,))
        await db.commit()


async def get_all_orgs(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM organizations ORDER BY category, name LIMIT ?", (limit,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
#  Notary orders
# ─────────────────────────────────────────────────────────────
async def create_notary_order(user_id: int, listing_id: int | None,
                               doc_file_id: str, doc_type: str,
                               doc_files_json: str = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO notary_orders (user_id, listing_id, doc_file_id, doc_type, doc_files_json) VALUES (?,?,?,?,?)",
            (user_id, listing_id, doc_file_id, doc_type, doc_files_json),
        )
        await db.commit()
        return cur.lastrowid


async def set_notary_payment(order_id: int, payment_file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE notary_orders SET payment_file_id=?, status='payment_check', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (payment_file_id, order_id),
        )
        await db.commit()


async def get_notary_order(order_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM notary_orders WHERE id=?", (order_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_notary_orders(status: str = None, assigned_to: int = None,
                             limit: int = 20) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        clauses, params = [], []
        if status:
            clauses.append("status=?"); params.append(status)
        if assigned_to:
            clauses.append("assigned_to=?"); params.append(assigned_to)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        cur = await db.execute(
            f"SELECT * FROM notary_orders {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def update_notary_order(order_id: int, status: str,
                               assigned_to: int = None, admin_note: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE notary_orders SET status=?,
               assigned_to=COALESCE(?,assigned_to),
               admin_note=COALESCE(?,admin_note),
               updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (status, assigned_to, admin_note, order_id),
        )
        await db.commit()


async def get_notary_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        total   = (await (await db.execute("SELECT COUNT(*) FROM notary_orders")).fetchone())[0]
        new_    = (await (await db.execute("SELECT COUNT(*) FROM notary_orders WHERE status='new'")).fetchone())[0]
        payment = (await (await db.execute("SELECT COUNT(*) FROM notary_orders WHERE status='payment_check'")).fetchone())[0]
        done    = (await (await db.execute("SELECT COUNT(*) FROM notary_orders WHERE status='done'")).fetchone())[0]
        reject  = (await (await db.execute("SELECT COUNT(*) FROM notary_orders WHERE status='rejected'")).fetchone())[0]
    return {"total": total, "new": new_, "payment_check": payment,
            "done": done, "rejected": reject}


async def save_feedback(user_id: int, sender: str, label: str, text: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO feedbacks (user_id, sender, label, text) VALUES (?,?,?,?)",
            (user_id, sender, label, text),
        )
        await db.commit()
