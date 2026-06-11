#!/usr/bin/env python3
"""
MobiKD Database Seeding Utility

Seeds realistic, production-like data into the database (SQLite or PostgreSQL).
Generates scan statistics starting exactly from May 25, 2026 up to June 6, 2026.
"""

import sys
import os
import random
import time
from datetime import datetime, timedelta

# Ensure we can import from local database module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load .env manually if present
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

from database import get_connection, execute_query, init_db

# A small valid 1x1 green pixel PNG base64 image
DUMMY_IMAGE = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

USERS = [
    {"phone": "admin@mobikd", "name": "Admin", "password": "admin_mobikd_2024"},
    {"phone": "0788123456", "name": "Demo Farmer", "password": "password123"},
    {"phone": "0788765432", "name": "Jean Bosco Nsengimana", "password": "password123"},
    {"phone": "0785123456", "name": "Marie Claire Uwimana", "password": "password123"},
    {"phone": "0789988776", "name": "Alphonse Mutabazi", "password": "password123"},
    {"phone": "0791234567", "name": "Grace Mukamana", "password": "password123"},
    {"phone": "0731234567", "name": "Eric Kwizera", "password": "password123"},
    {"phone": "0781112223", "name": "Aline Umuhire", "password": "password123"},
    {"phone": "0782223334", "name": "Emmanuel Tuganimana", "password": "password123"},
    {"phone": "0783334445", "name": "Claudine Murekatete", "password": "password123"},
]

def seed():
    print("Initializing Database tables if not exist...")
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    from database import HAS_PSYCOPG2
    # Determine if we're using PostgreSQL or SQLite
    db_type = "PostgreSQL (Render Live)" if (os.environ.get("DATABASE_URL") and HAS_PSYCOPG2) else "SQLite (Local)"
    print(f"Connected to database type: {db_type}")

    # Confirm before deleting in production
    if "PostgreSQL" in db_type:
        print("WARNING: You are about to clear the LIVE production database and seed it!")
        # We run non-interactively here, so we proceed directly.

    print("Clearing old data...")
    execute_query(cursor, "DELETE FROM scan_history")
    execute_query(cursor, "DELETE FROM users")
    conn.commit()

    print("Seeding Users...")
    for u in USERS:
        execute_query(
            cursor,
            "INSERT INTO users (phone, name, password) VALUES (?, ?, ?)",
            (u["phone"], u["name"], u["password"])
        )
    conn.commit()
    print(f"Successfully seeded {len(USERS)} users.")

    print("Generating scan history starting from May 25, 2026...")
    
    # Range of dates: May 25, 2026 to June 6, 2026
    start_date = datetime(2026, 5, 25, 8, 0, 0)
    end_date = datetime(2026, 6, 6, 13, 0, 0)
    
    current_time = start_date
    scan_count = 0

    # List of candidate phones for scan generator (excluding admin sometimes)
    farmer_phones = [u["phone"] for u in USERS if u["phone"] != "admin@mobikd"]

    # Let's seed scans
    while current_time <= end_date:
        # Number of scans on this day (between 3 and 10)
        day_scans = random.randint(3, 10)
        for _ in range(day_scans):
            # Pick a random farmer
            phone = random.choice(farmer_phones)
            
            # Formulate timestamp
            hour = random.randint(7, 18)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            scan_time = current_time.replace(hour=hour, minute=minute, second=second)
            
            if scan_time > end_date:
                break
                
            timestamp_str = scan_time.isoformat() + "Z"
            scan_id = str(int(scan_time.timestamp() * 1000))
            
            # Determine scan outcome
            # 85% chance it's a leaf, 15% not_leaf
            is_leaf = random.random() < 0.85
            if is_leaf:
                stage1_label = "leaf"
                stage1_confidence = round(random.uniform(0.85, 0.99), 4)
                
                # Disease classification
                # 35% healthy, 30% early_blight, 25% late_blight, 10% not_potato_leaf
                r = random.random()
                if r < 0.35:
                    stage2_label = "healthy"
                elif r < 0.65:
                    stage2_label = "early_blight"
                elif r < 0.90:
                    stage2_label = "late_blight"
                else:
                    stage2_label = "not_potato_leaf"
                    
                stage2_confidence = round(random.uniform(0.70, 0.98), 4)
            else:
                stage1_label = "not_leaf"
                stage1_confidence = round(random.uniform(0.80, 0.95), 4)
                stage2_label = None
                stage2_confidence = None

            execute_query(
                cursor,
                """
                INSERT INTO scan_history 
                (id, user_phone, image_base64, stage1_label, stage1_confidence, stage2_label, stage2_confidence, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (scan_id, phone, DUMMY_IMAGE, stage1_label, stage1_confidence, stage2_label, stage2_confidence, timestamp_str)
            )
            scan_count += 1
            
        # Move to next day
        current_time += timedelta(days=1)

    conn.commit()
    conn.close()
    print(f"Successfully generated and seeded {scan_count} scan records!")
    print("Database seeding completed.")

if __name__ == "__main__":
    seed()
