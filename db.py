"""NutriBob — accesso al database SQLite (compatibile con il diary.db della v1)."""

import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = DATA_DIR / "diary.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entries (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                food          TEXT    NOT NULL,
                calories      INTEGER NOT NULL,
                quantity_desc TEXT,
                created_at    TEXT    NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                weight_kg  REAL    NOT NULL,
                goal       TEXT    NOT NULL DEFAULT 'main',
                updated_at TEXT    NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weight_entries (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                weight_kg  REAL    NOT NULL,
                created_at TEXT    NOT NULL
            )
            """
        )
        # migrazioni (colonne aggiunte nel tempo — ignorate se esistono già)
        migrations = [
            ("users", "goal TEXT NOT NULL DEFAULT 'main'"),
            ("entries", "protein_g REAL"),
            ("entries", "carbs_g REAL"),
            ("entries", "fat_g REAL"),
            ("entries", "meal TEXT"),       # v2: colazione/pranzo/spuntino/cena
            ("entries", "grams REAL"),      # v2
            ("entries", "food_key TEXT"),   # v2: chiave in FOODS
        ]
        for table, col in migrations:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_entries_user_day ON entries(user_id, created_at)"
        )


# ── PROFILO ──────────────────────────────────────────────────────────────────


def set_weight(user_id: int, weight_kg: float) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, weight_kg, goal, updated_at)
            VALUES (?, ?, 'main', ?)
            ON CONFLICT(user_id) DO UPDATE SET weight_kg=excluded.weight_kg, updated_at=excluded.updated_at
            """,
            (user_id, weight_kg, now_str()),
        )
        conn.execute(
            "INSERT INTO weight_entries (user_id, weight_kg, created_at) VALUES (?,?,?)",
            (user_id, weight_kg, now_str()),
        )


def set_goal(user_id: int, goal: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE users SET goal=?, updated_at=? WHERE user_id=?", (goal, now_str(), user_id)
        )


def get_profile(user_id: int) -> Optional[tuple[float, str]]:
    """(weight_kg, goal) oppure None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT weight_kg, goal FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return (row["weight_kg"], row["goal"]) if row else None


def get_weight_history(user_id: int, limit: int = 14) -> list[tuple[str, float]]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT created_at, weight_kg FROM weight_entries
            WHERE user_id = ? ORDER BY datetime(created_at) DESC LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [(r["created_at"], r["weight_kg"]) for r in rows]


# ── DIARIO ───────────────────────────────────────────────────────────────────


def add_entry(
    user_id: int,
    food: str,
    calories: int,
    quantity_desc: str,
    created_at: str,
    meal: Optional[str] = None,
    protein_g: Optional[float] = None,
    carbs_g: Optional[float] = None,
    fat_g: Optional[float] = None,
    grams: Optional[float] = None,
    food_key: Optional[str] = None,
) -> int:
    with _conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO entries (user_id, food, calories, quantity_desc, created_at,
                                 protein_g, carbs_g, fat_g, meal, grams, food_key)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (user_id, food, calories, quantity_desc, created_at,
             protein_g, carbs_g, fat_g, meal, grams, food_key),
        )
        return cur.lastrowid


def get_day(user_id: int, day: date) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, food, calories, quantity_desc, created_at, meal,
                   COALESCE(protein_g, 0) AS p, COALESCE(carbs_g, 0) AS c, COALESCE(fat_g, 0) AS f
            FROM entries
            WHERE user_id = ? AND date(created_at) = ?
            ORDER BY created_at, id
            """,
            (user_id, day.isoformat()),
        ).fetchall()
        return [dict(r) for r in rows]


def day_totals(user_id: int, day: date) -> dict:
    rows = get_day(user_id, day)
    return {
        "kcal": sum(r["calories"] for r in rows),
        "p": sum(r["p"] for r in rows),
        "c": sum(r["c"] for r in rows),
        "f": sum(r["f"] for r in rows),
        "n": len(rows),
    }


def delete_entries(user_id: int, ids: list[int]) -> int:
    if not ids:
        return 0
    with _conn() as conn:
        q = ",".join("?" * len(ids))
        cur = conn.execute(
            f"DELETE FROM entries WHERE user_id = ? AND id IN ({q})", (user_id, *ids)
        )
        return cur.rowcount


def delete_last(user_id: int) -> Optional[tuple[str, int]]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, food, calories FROM entries WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row:
            conn.execute("DELETE FROM entries WHERE id = ?", (row["id"],))
            return row["food"], row["calories"]
    return None


def delete_day(user_id: int, day: date) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM entries WHERE user_id = ? AND date(created_at) = ?",
            (user_id, day.isoformat()),
        )
        return cur.rowcount


def weekly(user_id: int, days: int = 7) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT date(created_at) AS day, SUM(calories) AS kcal, COUNT(*) AS n,
                   SUM(COALESCE(protein_g,0)) AS p, SUM(COALESCE(carbs_g,0)) AS c,
                   SUM(COALESCE(fat_g,0)) AS f
            FROM entries
            WHERE user_id = ? AND date(created_at) >= date('now', 'localtime', ?)
            GROUP BY day ORDER BY day
            """,
            (user_id, f"-{days - 1} days"),
        ).fetchall()
        return [dict(r) for r in rows]
