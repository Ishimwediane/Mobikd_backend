import sqlite3
import os
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

DB_PATH = Path(__file__).parent / "mobikd.db"
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    if DATABASE_URL and HAS_PSYCOPG2:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

def execute_query(cursor, query: str, params=None):
    if DATABASE_URL and HAS_PSYCOPG2:
        query = query.replace('?', '%s')
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)

def is_integrity_error(e: Exception) -> bool:
    if isinstance(e, sqlite3.IntegrityError):
        return True
    if HAS_PSYCOPG2 and isinstance(e, psycopg2.IntegrityError):
        return True
    return False

def is_db_error(e: Exception) -> bool:
    if isinstance(e, sqlite3.Error):
        return True
    if HAS_PSYCOPG2 and isinstance(e, psycopg2.Error):
        return True
    return False

def init_db():
    if not DATABASE_URL:
        os.makedirs(DB_PATH.parent, exist_ok=True)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # In PostgreSQL, we can't use PRAGMA foreign_keys = ON.
    # The foreign key cascade logic works if tables are created.
    
    users_table = """
    CREATE TABLE IF NOT EXISTS users (
        phone TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        password TEXT NOT NULL
    );
    """
    
    scan_history_table = """
    CREATE TABLE IF NOT EXISTS scan_history (
        id TEXT PRIMARY KEY,
        user_phone TEXT NOT NULL,
        image_base64 TEXT NOT NULL,
        stage1_label TEXT NOT NULL,
        stage1_confidence REAL NOT NULL,
        stage2_label TEXT,
        stage2_confidence REAL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (user_phone) REFERENCES users (phone) 
            ON UPDATE CASCADE 
            ON DELETE CASCADE
    );
    """
    execute_query(cursor, users_table)
    execute_query(cursor, scan_history_table)
    
    conn.commit()
    conn.close()

def create_user(phone: str, name: str, password: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        execute_query(
            cursor,
            "INSERT INTO users (phone, name, password) VALUES (?, ?, ?)",
            (phone, name, password)
        )
        conn.commit()
        return True
    except Exception as e:
        if is_integrity_error(e):
            return False
        raise
    finally:
        conn.close()

def get_user(phone: str):
    conn = get_connection()
    cursor = conn.cursor()
    execute_query(cursor, "SELECT phone, name, password FROM users WHERE phone = ?", (phone,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def update_user(old_phone: str, new_phone: str, name: str, password: str = None) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if old_phone != new_phone:
            execute_query(cursor, "SELECT phone FROM users WHERE phone = ?", (new_phone,))
            if cursor.fetchone():
                return False
        if password:
            execute_query(
                cursor,
                "UPDATE users SET phone = ?, name = ?, password = ? WHERE phone = ?",
                (new_phone, name, password, old_phone)
            )
        else:
            execute_query(
                cursor,
                "UPDATE users SET phone = ?, name = ? WHERE phone = ?",
                (new_phone, name, old_phone)
            )
        conn.commit()
        return True
    except Exception as e:
        if is_db_error(e):
            return False
        raise
    finally:
        conn.close()

def add_history_item(
    item_id: str,
    user_phone: str,
    image_base64: str,
    stage1_label: str,
    stage1_confidence: float,
    stage2_label: str,
    stage2_confidence: float,
    timestamp: str
) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        execute_query(
            cursor,
            """
            INSERT INTO scan_history 
            (id, user_phone, image_base64, stage1_label, stage1_confidence, stage2_label, stage2_confidence, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (item_id, user_phone, image_base64, stage1_label, stage1_confidence, stage2_label, stage2_confidence, timestamp)
        )
        conn.commit()
        return True
    except Exception as e:
        if is_db_error(e):
            return False
        raise
    finally:
        conn.close()

def get_history(user_phone: str) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    execute_query(
        cursor,
        "SELECT id, image_base64, stage1_label, stage1_confidence, stage2_label, stage2_confidence, timestamp FROM scan_history WHERE user_phone = ? ORDER BY timestamp DESC",
        (user_phone,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def clear_history(user_phone: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        execute_query(cursor, "DELETE FROM scan_history WHERE user_phone = ?", (user_phone,))
        conn.commit()
        return True
    except Exception as e:
        if is_db_error(e):
            return False
        raise
    finally:
        conn.close()

# ─── Admin Queries ────────────────────────────────────────────────────────────

def admin_get_all_users() -> list:
    """Return all registered users (excluding password)."""
    conn = get_connection()
    cursor = conn.cursor()
    execute_query(cursor, """
        SELECT u.phone, u.name,
               COUNT(s.id)  AS scan_count,
               MAX(s.timestamp) AS last_scan
        FROM users u
        LEFT JOIN scan_history s ON s.user_phone = u.phone
        GROUP BY u.phone
        ORDER BY scan_count DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def admin_get_all_scans(limit: int = 200) -> list:
    """Return recent scan history across all users."""
    conn = get_connection()
    cursor = conn.cursor()
    execute_query(cursor, """
        SELECT s.id, s.user_phone, u.name AS user_name,
               s.stage1_label, s.stage1_confidence,
               s.stage2_label, s.stage2_confidence,
               s.timestamp
        FROM scan_history s
        LEFT JOIN users u ON u.phone = s.user_phone
        ORDER BY s.timestamp DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def admin_get_stats() -> dict:
    """Return aggregate statistics for the admin dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    # Total counts
    execute_query(cursor, "SELECT COUNT(*) FROM users")
    if DATABASE_URL and HAS_PSYCOPG2:
        total_users = cursor.fetchone()['count']
    else:
        total_users = cursor.fetchone()[0]

    execute_query(cursor, "SELECT COUNT(*) FROM scan_history")
    if DATABASE_URL and HAS_PSYCOPG2:
        total_scans = cursor.fetchone()['count']
    else:
        total_scans = cursor.fetchone()[0]

    execute_query(cursor, "SELECT COUNT(*) FROM scan_history WHERE LOWER(stage2_label) != 'healthy' AND stage2_label IS NOT NULL")
    if DATABASE_URL and HAS_PSYCOPG2:
        diseased_count = cursor.fetchone()['count']
    else:
        diseased_count = cursor.fetchone()[0]

    execute_query(cursor, "SELECT COUNT(*) FROM scan_history WHERE LOWER(stage2_label) = 'healthy'")
    if DATABASE_URL and HAS_PSYCOPG2:
        healthy_count = cursor.fetchone()['count']
    else:
        healthy_count = cursor.fetchone()[0]

    # Disease distribution
    execute_query(cursor, """
        SELECT stage2_label AS label, COUNT(*) AS count
        FROM scan_history
        WHERE stage2_label IS NOT NULL
        GROUP BY stage2_label
        ORDER BY count DESC
    """)
    disease_dist = [{"label": r["label"], "count": r["count"]} for r in cursor.fetchall()]

    # Monthly scan trend (last 12 months)
    execute_query(cursor, """
        SELECT substr(timestamp, 1, 7) AS month,
               COUNT(*) AS total,
               SUM(CASE WHEN LOWER(stage2_label) = 'healthy' THEN 1 ELSE 0 END) AS healthy,
               SUM(CASE WHEN LOWER(stage2_label) != 'healthy' AND stage2_label IS NOT NULL THEN 1 ELSE 0 END) AS diseased
        FROM scan_history
        GROUP BY month
        ORDER BY month DESC
        LIMIT 12
    """)
    monthly_trend = list(reversed([dict(r) for r in cursor.fetchall()]))

    # Monthly new users
    execute_query(cursor, """
        SELECT substr(s.timestamp, 1, 7) AS month, COUNT(DISTINCT s.user_phone) AS users
        FROM scan_history s
        GROUP BY month
        ORDER BY month DESC
        LIMIT 12
    """)
    monthly_users = list(reversed([dict(r) for r in cursor.fetchall()]))

    # Average confidence scores
    execute_query(cursor, "SELECT AVG(stage1_confidence) FROM scan_history")
    if DATABASE_URL and HAS_PSYCOPG2:
        avg_s1_conf = cursor.fetchone()['avg'] or 0.0
    else:
        avg_s1_conf = cursor.fetchone()[0] or 0.0

    execute_query(cursor, "SELECT AVG(stage2_confidence) FROM scan_history WHERE stage2_confidence IS NOT NULL")
    if DATABASE_URL and HAS_PSYCOPG2:
        avg_s2_conf = cursor.fetchone()['avg'] or 0.0
    else:
        avg_s2_conf = cursor.fetchone()[0] or 0.0

    conn.close()

    return {
        "total_users": total_users,
        "total_scans": total_scans,
        "diseased_count": diseased_count,
        "healthy_count": healthy_count,
        "disease_distribution": disease_dist,
        "monthly_scan_trend": monthly_trend,
        "monthly_users": monthly_users,
        "avg_stage1_confidence": round(float(avg_s1_conf) * 100, 1),
        "avg_stage2_confidence": round(float(avg_s2_conf) * 100, 1),
    }

def admin_delete_user(phone: str) -> bool:
    """Delete a user (cascades to scan history)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        execute_query(cursor, "DELETE FROM users WHERE phone = ?", (phone,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        if is_db_error(e):
            return False
        raise
    finally:
        conn.close()
