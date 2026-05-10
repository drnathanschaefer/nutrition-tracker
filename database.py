import sqlite3
import os
from contextlib import contextmanager
from datetime import date, timedelta
from zoneinfo import ZoneInfo

BRISBANE = ZoneInfo("Australia/Brisbane")


def today_local():
    from datetime import datetime
    return datetime.now(BRISBANE).date()

DB_PATH = os.environ.get("DB_PATH", "nutrition.db")

# Per 100g/ml for weight/volume foods; per unit for unit-type foods.
# Columns: name, unit_type, unit_label, default_amount,
#          calories, protein, fat, sat_fat, carbs, sugar, fibre, calcium, sodium, notes
INITIAL_FOODS = [
    ("Macro Organic Rolled Oats",               "weight", "g",      80,  377, 12.5, 9.0, 1.5, 55.5,  1.1, 11.0,   0,   5,  ""),
    ("Professional Whey WPC Natural",           "weight", "g",      30,  397, 78.0, 5.1, 3.2,  8.7,  3.5,  0.0,   0, 170,  ""),
    ("Professional Whey WPC Organic Cacao",     "weight", "g",      30,  396, 71.9, 6.5, 3.9, 10.1,  5.0,  0.0,   0, 154,  ""),
    ("Professional Whey NZ WPI Salted Caramel", "weight", "g",      30,  373, 86.1, 0.9, 0.6,  3.4,  3.0,  0.0,   0, 315,  ""),
    ("Kellogg's All-Bran Original",             "weight", "g",      45,  339, 14.1, 4.6, 0.9, 46.0, 18.0, 28.0,   0, 330,  ""),
    ("Ocean Spray Craisins (50% Less Sugar)",   "weight", "g",      40,  287,  0.3, 0.7, 0.1, 58.0, 43.0, 25.0,   0,   6,  ""),
    ("Devondale Extra Light Skim Milk",         "volume", "ml",    250,   34,  3.2, 0.1, 0.1,  4.9,  5.0,  0.0, 120,  45,  ""),
    ("Macro Organic Full Cream Milk",           "volume", "ml",    250,   63,  3.3, 3.4, 2.2,  4.8,  4.8,  0.0, 117,  44,  ""),
    ("Farmers Union Greek Style Yogurt",        "weight", "g",     130,   75,  5.2, 3.3, 2.1,  6.2,  6.2,  0.0, 196,  55,  ""),
    ("Creative Gourmet Frozen Banana Chunks",   "weight", "g",     100,   85,  0.8, 0.0, 0.0, 20.5, 12.2,  1.5,   0,   4,  ""),
    ("Creative Gourmet Frozen Mango Chunks",    "weight", "g",     100,   62,  0.8, 0.3, 0.1, 13.1, 12.5,  1.7,   0,   5,  ""),
    ("Honest to Goodness Psyllium Husks",       "weight", "g",      10,  183,  3.0, 0.7, 0.1,  1.3,  0.0, 71.0,   0, 120,  ""),
    ("The Kimchi Company Vegan Kimchi",         "weight", "g",     100,   33,  2.1, 0.3, 0.0,  5.5,  2.0,  0.0,   0, 870,  "High sodium content"),
    ("McCain Mixed Vegetables",                 "weight", "g",     150,   80,  3.1, 1.0, 0.2, 12.5,  4.5,  4.0,   0,  35,  ""),
    ("Simply Wholesome Couscous Nourish Bowl",  "weight", "g",     220,  158,  4.9, 5.0, 0.8, 22.0,  3.5,  2.6,   0, 520,  "Full pack = 220g"),
    ("Simply Wholesome Quinoa Nourish Bowl",    "weight", "g",     220,  132,  4.7, 3.6, 0.5, 18.0,  3.0,  4.2,   0, 320,  "Full pack = 220g"),
    ("Table of Plenty Mini Rice Cakes",         "unit",   "pack",    1,   70,  0.9, 3.2, 2.9,  9.4,  5.5,  0.2,   0,  11,  "1 pack = 14g. High sat fat from white choc coating."),
    ("Fibre Boost White Choc Protein Bar",      "unit",   "bar",     1,  143, 21.6, 3.1, 0.7,  0.4,  0.1, 26.4,   0,  52,  "1 bar = 60g"),
    ("LMNT Watermelon Salt Electrolyte",        "unit",   "sachet",  1,    5,  0.0, 0.0, 0.0,  1.0,  1.0,  0.0,   0, 1000, "1 sachet = 6g. Very high sodium."),
    ("Maple Movement Energy Gel (Original)",    "unit",   "sachet",  1,  110,  0.0, 0.0, 0.0, 27.0, 27.0,  0.0,   0,   0,  "1 sachet = 30ml"),
    ("Maple Movement Lemon + Salt Gel",         "unit",   "sachet",  1,  104,  0.0, 0.0, 0.0, 26.8, 26.8,  0.0,   0, 105,  "1 sachet = 32ml"),
    ("Nectar Sport Energy Gel (Stim)",          "unit",   "sachet",  1,   95,  0.1, 0.0, 0.0, 23.4, 20.0,  0.0,   0,   4,  "Contains 100mg caffeine per sachet"),
    ("Hemp Seeds (hulled)",                     "weight", "g",        5,  553, 31.6,48.7, 4.6,  8.7,  1.5,  4.0,  70,   5,  ""),
    ("Flax Seeds",                              "weight", "g",        5,  534, 18.3,42.2, 3.7, 28.9,  1.6, 27.3, 255,  30,  ""),
    ("Chia Seeds",                              "weight", "g",        5,  486, 16.5,30.7, 3.3, 42.1,  0.0, 34.4, 631,  16,  ""),
    ("Coconut Flakes (desiccated)",             "weight", "g",        5,  660,  6.9,64.5,57.2, 23.7,  6.4, 15.4,  26,  37,  "High sat fat"),
    ("Chicken Breast (cooked)",                 "weight", "g",      125,  165, 31.0, 3.6, 1.0,  0.0,  0.0,  0.0,  15,  74,  ""),
    ("Apple",                                   "weight", "g",      150,   52,  0.3, 0.2, 0.0, 13.8, 10.4,  2.4,   6,   1,  ""),
    ("Banana",                                  "weight", "g",      120,   89,  1.1, 0.3, 0.1, 23.0, 12.2,  2.6,   5,   1,  ""),
    ("Walnuts",                                 "weight", "g",       30,  654, 15.2,65.2, 6.1, 13.7,  2.6,  6.7,  98,   2,  ""),
    ("Brazil Nuts",                             "unit",   "nut",      1,   33,  0.7, 3.4, 0.8,  0.6,  0.1,  0.4,   8,   0,  "1 nut ≈ 5g"),
    ("Almonds",                                 "weight", "g",       30,  579, 21.2,49.9, 3.8, 21.6,  4.4, 12.5, 264,   1,  ""),
    ("Pecan Nuts",                              "weight", "g",       30,  691,  9.2,72.0, 6.2, 13.9,  4.0,  9.6,  70,   0,  ""),
    ("Cashews",                                 "weight", "g",       30,  553, 18.2,43.8, 7.8, 30.2,  5.9,  3.3,  37,  12,  ""),
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
                sugar REAL DEFAULT 0,
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
                meal_id INTEGER DEFAULT NULL,
                logged_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (food_id) REFERENCES foods(id),
                FOREIGN KEY (meal_id) REFERENCES meals(id)
            )
        """)
        # Migration: add sugar column to foods if missing
        food_cols = [r[1] for r in conn.execute("PRAGMA table_info(foods)").fetchall()]
        if "sugar" not in food_cols:
            conn.execute("ALTER TABLE foods ADD COLUMN sugar REAL DEFAULT 0")
            # Populate sugar for existing foods
            sugar_values = {
                "Macro Organic Rolled Oats": 1.1,
                "Professional Whey WPC Natural": 3.5,
                "Professional Whey WPC Organic Cacao": 5.0,
                "Professional Whey NZ WPI Salted Caramel": 3.0,
                "Kellogg's All-Bran Original": 18.0,
                "Ocean Spray Craisins (50% Less Sugar)": 43.0,
                "Devondale Extra Light Skim Milk": 5.0,
                "Macro Organic Full Cream Milk": 4.8,
                "Farmers Union Greek Style Yogurt": 6.2,
                "Creative Gourmet Frozen Banana Chunks": 12.2,
                "Creative Gourmet Frozen Mango Chunks": 12.5,
                "Honest to Goodness Psyllium Husks": 0.0,
                "The Kimchi Company Vegan Kimchi": 2.0,
                "McCain Mixed Vegetables": 4.5,
                "Simply Wholesome Couscous Nourish Bowl": 3.5,
                "Simply Wholesome Quinoa Nourish Bowl": 3.0,
                "Table of Plenty Mini Rice Cakes": 5.5,
                "Fibre Boost White Choc Protein Bar": 0.1,
                "LMNT Watermelon Salt Electrolyte": 1.0,
                "Maple Movement Energy Gel (Original)": 27.0,
                "Maple Movement Lemon + Salt Gel": 26.8,
                "Nectar Sport Energy Gel (Stim)": 20.0,
                "Hemp Seeds (hulled)": 1.5,
                "Flax Seeds": 1.6,
                "Chia Seeds": 0.0,
                "Coconut Flakes (desiccated)": 6.4,
                "Chicken Breast (cooked)": 0.0,
                "Apple": 10.4,
                "Banana": 12.2,
                "Walnuts": 2.6,
                "Brazil Nuts": 0.1,
                "Almonds": 4.4,
                "Pecan Nuts": 4.0,
                "Cashews": 5.9,
            }
            for name, sugar in sugar_values.items():
                conn.execute("UPDATE foods SET sugar = ? WHERE name = ?", (sugar, name))

        # Migration: add meal_id column if it doesn't exist yet
        cols = [r[1] for r in conn.execute("PRAGMA table_info(log_entries)").fetchall()]
        if "meal_id" not in cols:
            conn.execute("ALTER TABLE log_entries ADD COLUMN meal_id INTEGER DEFAULT NULL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_feedback (
                date TEXT PRIMARY KEY,
                feedback TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 99
            )
        """)
        # Migration: add sort_order column if missing
        cols = [r[1] for r in conn.execute("PRAGMA table_info(meals)").fetchall()]
        if "sort_order" not in cols:
            conn.execute("ALTER TABLE meals ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 99")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meal_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meal_id INTEGER NOT NULL,
                food_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                FOREIGN KEY (meal_id) REFERENCES meals(id),
                FOREIGN KEY (food_id) REFERENCES foods(id)
            )
        """)
        count = conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0]
        if count == 0:
            conn.executemany(
                """INSERT INTO foods
                   (name, unit_type, unit_label, default_amount,
                    calories, protein, fat, sat_fat, carbs, sugar, fibre, calcium, sodium, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                INITIAL_FOODS,
            )

        # Migration: add new foods if they don't exist yet
        new_foods = [
            ("Hemp Seeds (hulled)",          "weight", "g",  5, 553, 31.6, 48.7,  4.6,  8.7,  4.0,  70,  5, ""),
            ("Flax Seeds",                   "weight", "g",  5, 534, 18.3, 42.2,  3.7, 28.9, 27.3, 255, 30, ""),
            ("Chia Seeds",                   "weight", "g",  5, 486, 16.5, 30.7,  3.3, 42.1, 34.4, 631, 16, ""),
            ("Coconut Flakes (desiccated)",  "weight", "g",  5, 660,  6.9, 64.5, 57.2, 23.7, 15.4,  26, 37, "High sat fat"),
        ]
        for food in new_foods:
            exists = conn.execute("SELECT 1 FROM foods WHERE name = ?", (food[0],)).fetchone()
            if not exists:
                conn.execute(
                    """INSERT INTO foods
                       (name, unit_type, unit_label, default_amount,
                        calories, protein, fat, sat_fat, carbs, fibre, calcium, sodium, notes)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    food,
                )

        # Migration: add apple and banana if missing
        for food in [
            ("Apple",  "weight", "g", 150,  52,  0.3, 0.2, 0.0, 13.8, 2.4,  6,  1, ""),
            ("Banana", "weight", "g", 120,  89,  1.1, 0.3, 0.1, 23.0, 2.6,  5,  1, ""),
        ]:
            if not conn.execute("SELECT 1 FROM foods WHERE name = ?", (food[0],)).fetchone():
                conn.execute(
                    """INSERT INTO foods
                       (name, unit_type, unit_label, default_amount,
                        calories, protein, fat, sat_fat, carbs, fibre, calcium, sodium, notes)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    food,
                )

        # Migration: add nuts if missing
        new_nuts = [
            ("Walnuts",      "weight", "g",    30, 654, 15.2, 65.2,  6.1, 13.7,  6.7,  98,  2, ""),
            ("Brazil Nuts",  "unit",   "nut",   1,  33,  0.7,  3.4,  0.8,  0.6,  0.4,   8,  0, "1 nut ≈ 5g"),
            ("Almonds",      "weight", "g",    30, 579, 21.2, 49.9,  3.8, 21.6, 12.5, 264,  1, ""),
            ("Pecan Nuts",   "weight", "g",    30, 691,  9.2, 72.0,  6.2, 13.9,  9.6,  70,  0, ""),
            ("Cashews",      "weight", "g",    30, 553, 18.2, 43.8,  7.8, 30.2,  3.3,  37, 12, ""),
        ]
        for food in new_nuts:
            if not conn.execute("SELECT 1 FROM foods WHERE name = ?", (food[0],)).fetchone():
                conn.execute(
                    """INSERT INTO foods
                       (name, unit_type, unit_label, default_amount,
                        calories, protein, fat, sat_fat, carbs, fibre, calcium, sodium, notes)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    food,
                )

        # Migration: add chicken breast if missing
        if not conn.execute("SELECT 1 FROM foods WHERE name = 'Chicken Breast (cooked)'").fetchone():
            conn.execute(
                """INSERT INTO foods
                   (name, unit_type, unit_label, default_amount,
                    calories, protein, fat, sat_fat, carbs, fibre, calcium, sodium, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("Chicken Breast (cooked)", "weight", "g", 125, 165, 31.0, 3.6, 1.0, 0.0, 0.0, 15, 74, ""),
            )

        # Migration: rename "Lunch" to "Lunch with Couscous" if it exists
        conn.execute("UPDATE meals SET name = 'Lunch with Couscous' WHERE name = 'Lunch'")

        # Migration: rename Walnuts meal
        conn.execute("UPDATE meals SET name = 'Walnuts - 30g + Brazil Nut' WHERE name = 'Walnuts & Brazil Nut'")

        # Migration: set sort orders
        sort_orders = [
            ("Breakfast",                        1),
            ("Lunch with Couscous",              2),
            ("Lunch with Quinoa",                3),
            ("Walnuts - 30g + Brazil Nut",             4),
            ("Almonds",                          5),
            ("Cashews",                          6),
            ("Pecan Nuts",                       7),
            ("Fibre Boost Protein Bar",          8),
            ("LMNT",                             9),
            ("Maple Movement Original Gel",     10),
            ("Maple Movement Lemon + Salt Gel", 11),
            ("Nectar Sport Gel",                12),
            ("WPC Cacao",                       13),
            ("WPI Salted Caramel",              14),
            ("Kimchi",                          15),
        ]
        for name, order in sort_orders:
            conn.execute("UPDATE meals SET sort_order = ? WHERE name = ?", (order, name))

        # Migration: split "Cashews & Pecan Nuts" back into separate meals
        combined = conn.execute("SELECT id FROM meals WHERE name = 'Cashews & Pecan Nuts'").fetchone()
        if combined:
            conn.execute("DELETE FROM meal_items WHERE meal_id = ?", (combined["id"],))
            conn.execute("DELETE FROM meals WHERE id = ?", (combined["id"],))
        for meal_name, food_name, order in [
            ("Cashews",    "Cashews",    6),
            ("Pecan Nuts", "Pecan Nuts", 7),
        ]:
            if not conn.execute("SELECT 1 FROM meals WHERE name = ?", (meal_name,)).fetchone():
                conn.execute("INSERT INTO meals (name, sort_order) VALUES (?, ?)", (meal_name, order))
                mid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                food = conn.execute("SELECT id FROM foods WHERE name = ?", (food_name,)).fetchone()
                if food:
                    conn.execute(
                        "INSERT INTO meal_items (meal_id, food_id, amount) VALUES (?,?,?)",
                        (mid, food["id"], 30),
                    )

        # Migration: add post-pecan meals if missing
        extra_meals = [
            ("Fibre Boost Protein Bar",            8,  [("Fibre Boost White Choc Protein Bar",      1)]),
            ("LMNT",                               9,  [("LMNT Watermelon Salt Electrolyte",         1)]),
            ("Maple Movement Original Gel",       10,  [("Maple Movement Energy Gel (Original)",     1)]),
            ("Maple Movement Lemon + Salt Gel",   11,  [("Maple Movement Lemon + Salt Gel",          1)]),
            ("Nectar Sport Gel",                  12,  [("Nectar Sport Energy Gel (Stim)",           1)]),
            ("WPC Cacao",                         13,  [("Professional Whey WPC Organic Cacao",     50)]),
            ("WPI Salted Caramel",                 14,  [("Professional Whey NZ WPI Salted Caramel", 50)]),
            ("Kimchi",                            15,  [("The Kimchi Company Vegan Kimchi",         30)]),
        ]
        for meal_name, order, items in extra_meals:
            if not conn.execute("SELECT 1 FROM meals WHERE name = ?", (meal_name,)).fetchone():
                conn.execute("INSERT INTO meals (name, sort_order) VALUES (?, ?)", (meal_name, order))
                mid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                for food_name, amount in items:
                    food = conn.execute("SELECT id FROM foods WHERE name = ?", (food_name,)).fetchone()
                    if food:
                        conn.execute(
                            "INSERT INTO meal_items (meal_id, food_id, amount) VALUES (?,?,?)",
                            (mid, food["id"], amount),
                        )

        # Migration: add nut snack meals if missing
        nut_meals = [
            ("Walnuts - 30g + Brazil Nut",  [("Walnuts", 30), ("Brazil Nuts", 1)]),
            ("Almonds",               [("Almonds", 30)]),
            ("Pecan Nuts",            [("Pecan Nuts", 30)]),
            ("Cashews",               [("Cashews", 30)]),
        ]
        for meal_name, items in nut_meals:
            if not conn.execute("SELECT 1 FROM meals WHERE name = ?", (meal_name,)).fetchone():
                conn.execute("INSERT INTO meals (name) VALUES (?)", (meal_name,))
                mid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                for food_name, amount in items:
                    food = conn.execute("SELECT id FROM foods WHERE name = ?", (food_name,)).fetchone()
                    if food:
                        conn.execute(
                            "INSERT INTO meal_items (meal_id, food_id, amount) VALUES (?,?,?)",
                            (mid, food["id"], amount),
                        )

        # Migration: add Lunch with Couscous if missing
        if not conn.execute("SELECT 1 FROM meals WHERE name = 'Lunch with Couscous'").fetchone():
            conn.execute("INSERT INTO meals (name) VALUES (?)", ("Lunch with Couscous",))
            lunch_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            for food_name, amount in [
                ("Simply Wholesome Couscous Nourish Bowl", 100),
                ("McCain Mixed Vegetables",                250),
                ("Chicken Breast (cooked)",                125),
            ]:
                food = conn.execute("SELECT id FROM foods WHERE name = ?", (food_name,)).fetchone()
                if food:
                    conn.execute(
                        "INSERT INTO meal_items (meal_id, food_id, amount) VALUES (?,?,?)",
                        (lunch_id, food["id"], amount),
                    )

        # Migration: add Lunch with Quinoa if missing
        if not conn.execute("SELECT 1 FROM meals WHERE name = 'Lunch with Quinoa'").fetchone():
            conn.execute("INSERT INTO meals (name) VALUES (?)", ("Lunch with Quinoa",))
            quinoa_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            for food_name, amount in [
                ("Simply Wholesome Quinoa Nourish Bowl", 100),
                ("McCain Mixed Vegetables",              250),
                ("Chicken Breast (cooked)",              125),
            ]:
                food = conn.execute("SELECT id FROM foods WHERE name = ?", (food_name,)).fetchone()
                if food:
                    conn.execute(
                        "INSERT INTO meal_items (meal_id, food_id, amount) VALUES (?,?,?)",
                        (quinoa_id, food["id"], amount),
                    )

        # Migration: add seeds/coconut to existing Breakfast meal if missing
        breakfast = conn.execute("SELECT id FROM meals WHERE name = 'Breakfast'").fetchone()
        if breakfast:
            new_breakfast_items = [
                ("Hemp Seeds (hulled)",         5),
                ("Flax Seeds",                  5),
                ("Chia Seeds",                  5),
                ("Coconut Flakes (desiccated)", 5),
            ]
            for food_name, amount in new_breakfast_items:
                food = conn.execute("SELECT id FROM foods WHERE name = ?", (food_name,)).fetchone()
                if food:
                    already = conn.execute(
                        "SELECT 1 FROM meal_items WHERE meal_id = ? AND food_id = ?",
                        (breakfast["id"], food["id"]),
                    ).fetchone()
                    if not already:
                        conn.execute(
                            "INSERT INTO meal_items (meal_id, food_id, amount) VALUES (?,?,?)",
                            (breakfast["id"], food["id"], amount),
                        )

        meal_count = conn.execute("SELECT COUNT(*) FROM meals").fetchone()[0]
        if meal_count == 0:
            conn.execute("INSERT INTO meals (name, sort_order) VALUES (?, ?)", ("Breakfast", 1))
            meal_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            breakfast_items = [
                ("Professional Whey WPC Natural",           50),
                ("Macro Organic Rolled Oats",               100),
                ("Creative Gourmet Frozen Banana Chunks",   100),
                ("Creative Gourmet Frozen Mango Chunks",    100),
                ("Devondale Extra Light Skim Milk",         250),
                ("Honest to Goodness Psyllium Husks",       12),
                ("Kellogg's All-Bran Original",             30),
                ("Ocean Spray Craisins (50% Less Sugar)",   30),
                ("Hemp Seeds (hulled)",                      5),
                ("Flax Seeds",                               5),
                ("Chia Seeds",                               5),
                ("Coconut Flakes (desiccated)",              5),
            ]
            # Seed nut snack meals
            for meal_name, sort_order, items in [
                ("Walnuts - 30g + Brazil Nut",            4,  [("Walnuts", 30), ("Brazil Nuts", 1)]),
                ("Almonds",                         5,  [("Almonds", 30)]),
                ("Cashews",                         6,  [("Cashews", 30)]),
                ("Pecan Nuts",                      7,  [("Pecan Nuts", 30)]),
                ("Fibre Boost Protein Bar",         8,  [("Fibre Boost White Choc Protein Bar",      1)]),
                ("LMNT",                            9,  [("LMNT Watermelon Salt Electrolyte",         1)]),
                ("Maple Movement Original Gel",    10,  [("Maple Movement Energy Gel (Original)",     1)]),
                ("Maple Movement Lemon + Salt Gel",11,  [("Maple Movement Lemon + Salt Gel",          1)]),
                ("Nectar Sport Gel",               12,  [("Nectar Sport Energy Gel (Stim)",           1)]),
                ("WPC Cacao",                      13,  [("Professional Whey WPC Organic Cacao",     50)]),
                ("WPI Salted Caramel",             14,  [("Professional Whey NZ WPI Salted Caramel", 50)]),
                ("Kimchi",                         15,  [("The Kimchi Company Vegan Kimchi",         30)]),
            ]:
                conn.execute("INSERT INTO meals (name, sort_order) VALUES (?, ?)", (meal_name, sort_order))
                mid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                for food_name, amount in items:
                    food = conn.execute("SELECT id FROM foods WHERE name = ?", (food_name,)).fetchone()
                    if food:
                        conn.execute(
                            "INSERT INTO meal_items (meal_id, food_id, amount) VALUES (?,?,?)",
                            (mid, food["id"], amount),
                        )

            # Seed Lunch with Couscous meal
            conn.execute("INSERT INTO meals (name, sort_order) VALUES (?, ?)", ("Lunch with Couscous", 2))
            lunch_couscous_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            for food_name, amount in [
                ("Simply Wholesome Couscous Nourish Bowl", 100),
                ("McCain Mixed Vegetables",                250),
                ("Chicken Breast (cooked)",                125),
            ]:
                food = conn.execute("SELECT id FROM foods WHERE name = ?", (food_name,)).fetchone()
                if food:
                    conn.execute(
                        "INSERT INTO meal_items (meal_id, food_id, amount) VALUES (?,?,?)",
                        (lunch_couscous_id, food["id"], amount),
                    )
            # Seed Lunch with Quinoa meal
            conn.execute("INSERT INTO meals (name, sort_order) VALUES (?, ?)", ("Lunch with Quinoa", 3))
            lunch_quinoa_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            for food_name, amount in [
                ("Simply Wholesome Quinoa Nourish Bowl", 100),
                ("McCain Mixed Vegetables",              250),
                ("Chicken Breast (cooked)",              125),
            ]:
                food = conn.execute("SELECT id FROM foods WHERE name = ?", (food_name,)).fetchone()
                if food:
                    conn.execute(
                        "INSERT INTO meal_items (meal_id, food_id, amount) VALUES (?,?,?)",
                        (lunch_quinoa_id, food["id"], amount),
                    )
            for food_name, amount in breakfast_items:
                food = conn.execute(
                    "SELECT id FROM foods WHERE name = ?", (food_name,)
                ).fetchone()
                if food:
                    conn.execute(
                        "INSERT INTO meal_items (meal_id, food_id, amount) VALUES (?,?,?)",
                        (meal_id, food["id"], amount),
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
    d["total_sugar"]    = round(d.get("sugar", 0) * m, 1)
    d["total_fibre"]    = round(d["fibre"]     * m, 1)
    d["total_calcium"]  = round(d["calcium"]   * m, 1)
    d["total_sodium"]   = round(d["sodium"]    * m, 1)
    return d


def get_day_entries(date_str):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT le.id, le.date, le.food_id, le.amount, le.meal_id,
                   COALESCE(m.name, '') AS meal_name,
                   f.name, f.unit_type, f.unit_label,
                   f.calories, f.protein, f.fat, f.sat_fat,
                   f.carbs, f.fibre, f.calcium, f.sodium
            FROM log_entries le
            JOIN foods f ON le.food_id = f.id
            LEFT JOIN meals m ON le.meal_id = m.id
            WHERE le.date = ?
            ORDER BY le.logged_at
        """, (date_str,)).fetchall()
    return [_compute_entry(r) for r in rows]


def get_day_totals(date_str):
    entries = get_day_entries(date_str)
    keys = ["calories", "protein", "fat", "sat_fat", "carbs", "sugar", "fibre", "calcium", "sodium"]
    totals = {k: 0.0 for k in keys}
    for e in entries:
        for k in keys:
            totals[k] += e[f"total_{k}"]
    return {k: round(v, 1) for k, v in totals.items()}


def get_history(days=30):
    result = []
    today = today_local()
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


def delete_all_log_entries(date_str):
    with get_db() as conn:
        conn.execute("DELETE FROM log_entries WHERE date = ?", (date_str,))


def add_food(name, unit_type, unit_label, default_amount,
             calories, protein, fat, sat_fat, carbs, sugar, fibre, calcium, sodium, notes=""):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO foods
               (name, unit_type, unit_label, default_amount,
                calories, protein, fat, sat_fat, carbs, sugar, fibre, calcium, sodium, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (name, unit_type, unit_label, default_amount,
             calories, protein, fat, sat_fat, carbs, sugar, fibre, calcium, sodium, notes),
        )


def delete_food(food_id):
    with get_db() as conn:
        conn.execute("DELETE FROM log_entries WHERE food_id = ?", (food_id,))
        conn.execute("DELETE FROM meal_items WHERE food_id = ?", (food_id,))
        conn.execute("DELETE FROM foods WHERE id = ?", (food_id,))


# ── Meals ──────────────────────────────────────────────────────────────────

def get_all_meals():
    with get_db() as conn:
        meals = conn.execute("SELECT id, name FROM meals ORDER BY sort_order, name").fetchall()
        result = []
        for meal in meals:
            items = conn.execute("""
                SELECT mi.id, mi.amount,
                       f.name AS food_name, f.unit_label, f.unit_type,
                       f.calories, f.protein, f.fat, f.sat_fat,
                       f.carbs, f.fibre, f.calcium, f.sodium
                FROM meal_items mi
                JOIN foods f ON f.id = mi.food_id
                WHERE mi.meal_id = ?
                ORDER BY f.name
            """, (meal["id"],)).fetchall()
            items_list = [_compute_entry(dict(i) | {"name": i["food_name"], "amount": i["amount"]}) for i in items]
            # sum totals for the whole meal
            totals = {k: round(sum(i[f"total_{k}"] for i in items_list), 1)
                      for k in ["calories", "protein", "fat", "sat_fat", "carbs", "fibre", "calcium", "sodium"]}
            result.append({"id": meal["id"], "name": meal["name"],
                           "foods": items_list, "totals": totals})
        return result


def add_meal(name):
    with get_db() as conn:
        conn.execute("INSERT INTO meals (name) VALUES (?)", (name,))


def delete_meal(meal_id):
    with get_db() as conn:
        conn.execute("DELETE FROM meal_items WHERE meal_id = ?", (meal_id,))
        conn.execute("DELETE FROM meals WHERE id = ?", (meal_id,))


def add_meal_item(meal_id, food_id, amount):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO meal_items (meal_id, food_id, amount) VALUES (?,?,?)",
            (meal_id, food_id, amount),
        )


def remove_meal_item(item_id):
    with get_db() as conn:
        conn.execute("DELETE FROM meal_items WHERE id = ?", (item_id,))


def get_feedback(date_str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT feedback FROM daily_feedback WHERE date = ?", (date_str,)
        ).fetchone()
    return row["feedback"] if row else None


def save_feedback(date_str, feedback):
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO daily_feedback (date, feedback) VALUES (?, ?)",
            (date_str, feedback),
        )


def log_meal(meal_id, date_str):
    with get_db() as conn:
        items = conn.execute(
            "SELECT food_id, amount FROM meal_items WHERE meal_id = ?", (meal_id,)
        ).fetchall()
        for item in items:
            conn.execute(
                "INSERT INTO log_entries (date, food_id, amount, meal_id) VALUES (?,?,?,?)",
                (date_str, item["food_id"], item["amount"], meal_id),
            )
