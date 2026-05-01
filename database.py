import sqlite3
import os
from contextlib import contextmanager
from datetime import date, timedelta

DB_PATH = os.environ.get("DB_PATH", "nutrition.db")

# Per 100g/ml for weight/volume foods; per unit for unit-type foods.
# Columns: name, unit_type, unit_label, default_amount,
#          calories, protein, fat, sat_fat, carbs, fibre, calcium, sodium, notes
INITIAL_FOODS = [
    ("Macro Organic Rolled Oats",               "weight", "g",      80,  377, 12.5, 9.0, 1.5, 55.5, 11.0,   0,   5,  ""),
    ("Professional Whey WPC Natural",           "weight", "g",      30,  397, 78.0, 5.1, 3.2,  8.7,  0.0,   0, 170,  ""),
    ("Professional Whey WPC Organic Cacao",     "weight", "g",      30,  396, 71.9, 6.5, 3.9, 10.1,  0.0,   0, 154,  ""),
    ("Professional Whey NZ WPI Salted Caramel", "weight", "g",      30,  373, 86.1, 0.9, 0.6,  3.4,  0.0,   0, 315,  ""),
    ("Kellogg's All-Bran Original",             "weight", "g",      45,  339, 14.1, 4.6, 0.9, 46.0, 28.0,   0, 330,  ""),
    ("Ocean Spray Craisins (50% Less Sugar)",   "weight", "g",      40,  287,  0.3, 0.7, 0.1, 58.0, 25.0,   0,   6,  ""),
    ("Devondale Extra Light Skim Milk",         "volume", "ml",    250,   34,  3.2, 0.1, 0.1,  4.9,  0.0, 120,  45,  ""),
    ("Macro Organic Full Cream Milk",           "volume", "ml",    250,   63,  3.3, 3.4, 2.2,  4.8,  0.0, 117,  44,  ""),
    ("Farmers Union Greek Style Yogurt",        "weight", "g",     130,   75,  5.2, 3.3, 2.1,  6.2,  0.0, 196,  55,  ""),
    ("Creative Gourmet Frozen Banana Chunks",   "weight", "g",     100,   85,  0.8, 0.0, 0.0, 20.5,  1.5,   0,   4,  ""),
    ("Creative Gourmet Frozen Mango Chunks",    "weight", "g",     100,   62,  0.8, 0.3, 0.1, 13.1,  1.7,   0,   5,  ""),
    ("Honest to Goodness Psyllium Husks",       "weight", "g",      10,  183,  3.0, 0.7, 0.1,  1.3, 71.0,   0, 120,  ""),
    ("The Kimchi Company Vegan Kimchi",         "weight", "g",     100,   33,  2.1, 0.3, 0.0,  5.5,  0.0,   0, 870,  "High sodium content"),
    ("McCain Mixed Vegetables",                 "weight", "g",     150,   80,  3.1, 1.0, 0.2, 12.5,  4.0,   0,  35,  ""),
    ("Simply Wholesome Couscous Nourish Bowl",  "weight", "g",     220,  158,  4.9, 5.0, 0.8, 22.0,  2.6,   0, 520,  "Full pack = 220g"),
    ("Simply Wholesome Quinoa Nourish Bowl",    "weight", "g",     220,  132,  4.7, 3.6, 0.5, 18.0,  4.2,   0, 320,  "Full pack = 220g"),
    ("Table of Plenty Mini Rice Cakes",         "unit",   "pack",    1,   70,  0.9, 3.2, 2.9,  9.4,  0.2,   0,  11,  "1 pack = 14g. High sat fat from white choc coating."),
    ("Fibre Boost White Choc Protein Bar",      "unit",   "bar",     1,  143, 21.6, 3.1, 0.7,  0.4, 26.4,   0,  52,  "1 bar = 60g"),
    ("LMNT Watermelon Salt Electrolyte",        "unit",   "sachet",  1,    5,  0.0, 0.0, 0.0,  1.0,  0.0,   0, 1000, "1 sachet = 6g. Very high sodium."),
    ("Maple Movement Energy Gel (Original)",    "unit",   "sachet",  1,  110,  0.0, 0.0, 0.0, 27.0,  0.0,   0,   0,  "1 sachet = 30ml"),
    ("Maple Movement Lemon + Salt Gel",         "unit",   "sachet",  1,  104,  0.0, 0.0, 0.0, 26.8,  0.0,   0, 105,  "1 sachet = 32ml"),
    ("Nectar Sport Energy Gel (Stim)",          "unit",   "sachet",  1,   95,  0.1, 0.0, 0.0, 23.4,  0.0,   0,   4,  "Contains 100mg caffeine per sachet"),
]


@contextmanager
def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) if os.path.dirname(DB_PATH) else None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                unit_type TEXT NOT NULL DEFAULT 'weight',
                unit_label TEXT DEFAULT 'g',
                default_amount REAL DEFAULT 100,
                calories REAL DEFAULT 0,
                protein REAL DEFAULT 0,
                fat REAL DEFAULT 0,
                sat_fat REAL DEFAULT 0,
                carbs REAL DEFAULT 0,
                fibre REAL DEFAULT 0,
                calcium REAL DEFAULT 0,
                sodium REAL DEFAULT 0,
                notes TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS log_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                food_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                logged_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (food_id) REFERENCES foods(id)
            )
        """)
        count = conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0]
        if count == 0:
            conn.executemany(
                """INSERT INTO foods
                   (name, unit_type, unit_label, default_amount,
                    calories, protein, fat, sat_fat, carbs, fibre, calcium, sodium, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                INITIAL_FOODS,
            )


def get_all_foods():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM foods ORDER BY name").fetchall()]


def _compute_entry(row):
    d = dict(row)
    m = d["amount"] if d["unit_type"] == "unit" else d["amount"] / 100.0
    d["total_calories"] = round(d["calories"] * m, 1)
    d["total_protein"]  = round(d["protein"]  * m, 1)
    d["total_fat"]      = round(d["fat"]       * m, 1)
    d["total_sat_fat"]  = round(d["sat_fat"]   * m, 1)
    d["total_carbs"]    = round(d["carbs"]     * m, 1)
    d["total_fibre"]    = round(d["fibre"]     * m, 1)
    d["total_calcium"]  = round(d["calcium"]   * m, 1)
    d["total_sodium"]   = round(d["sodium"]    * m, 1)
    return d


def get_day_entries(date_str):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT le.id, le.date, le.food_id, le.amount,
                   f.name, f.unit_type, f.unit_label,
                   f.calories, f.protein, f.fat, f.sat_fat,
                   f.carbs, f.fibre, f.calcium, f.sodium
            FROM log_entries le
            JOIN foods f ON le.food_id = f.id
            WHERE le.date = ?
            ORDER BY le.logged_at
        """, (date_str,)).fetchall()
    return [_compute_entry(r) for r in rows]


def get_day_totals(date_str):
    entries = get_day_entries(date_str)
    keys = ["calories", "protein", "fat", "sat_fat", "carbs", "fibre", "calcium", "sodium"]
    totals = {k: 0.0 for k in keys}
    for e in entries:
        for k in keys:
            totals[k] += e[f"total_{k}"]
    return {k: round(v, 1) for k, v in totals.items()}


def get_history(days=30):
    result = []
    today = date.today()
    for i in range(days):
        d = (today - timedelta(days=i)).isoformat()
        totals = get_day_totals(d)
        if any(v > 0 for v in totals.values()):
            totals["date"] = d
            result.append(totals)
    return result


def add_log_entry(date_str, food_id, amount):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO log_entries (date, food_id, amount) VALUES (?,?,?)",
            (date_str, food_id, amount),
        )


def delete_log_entry(entry_id):
    with get_db() as conn:
        conn.execute("DELETE FROM log_entries WHERE id = ?", (entry_id,))


def add_food(name, unit_type, unit_label, default_amount,
             calories, protein, fat, sat_fat, carbs, fibre, calcium, sodium, notes=""):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO foods
               (name, unit_type, unit_label, default_amount,
                calories, protein, fat, sat_fat, carbs, fibre, calcium, sodium, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (name, unit_type, unit_label, default_amount,
             calories, protein, fat, sat_fat, carbs, fibre, calcium, sodium, notes),
        )


def delete_food(food_id):
    with get_db() as conn:
        conn.execute("DELETE FROM log_entries WHERE food_id = ?", (food_id,))
        conn.execute("DELETE FROM foods WHERE id = ?", (food_id,))
