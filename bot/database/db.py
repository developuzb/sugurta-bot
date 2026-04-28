import aiosqlite
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_NAME = "db.sqlite"


async def init_db():
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                topic_id INTEGER
            )
            """)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                user_id INTEGER,
                topic_id INTEGER,
                amount TEXT,
                status TEXT,
                deadline TEXT
            )
            """)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS temp_orders (
                user_id INTEGER PRIMARY KEY,
                vehicle TEXT,
                region TEXT,
                insurance_type TEXT,
                price INTEGER,
                bonus INTEGER,
                created_at TIMESTAMP
            )
            """)
            await db.commit()

        logger.info("Database initialized")

    except Exception as e:
        logger.error(f"DB init error: {e}", exc_info=True)


# ---------------- TEMP ORDER ----------------
async def save_temp_order(user_id, data):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT OR REPLACE INTO temp_orders 
                (user_id, vehicle, region, insurance_type, price, bonus, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                data['vehicle'],
                data['region'],
                data['insurance_type'],
                data['price'],
                data['bonus'],
                datetime.now()
            ))
            await db.commit()

        logger.info(f"Temp order saved: {user_id}")

    except Exception as e:
        logger.error(f"Save temp order error: {e}", exc_info=True)


async def get_temp_order(user_id):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("""
                SELECT vehicle, region, insurance_type, price, bonus
                FROM temp_orders WHERE user_id=?
            """, (user_id,)) as cursor:

                row = await cursor.fetchone()
                if not row:
                    return None

                return {
                    "vehicle": row[0],
                    "region": row[1],
                    "insurance_type": row[2],
                    "price": row[3],
                    "bonus": row[4]
                }

    except Exception as e:
        logger.error(f"Get temp order error: {e}", exc_info=True)
        return None


# ---------------- USERS ----------------

async def save_user(user_id, topic_id):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT OR IGNORE INTO users (user_id, topic_id)
                VALUES (?, ?)
            """, (user_id, topic_id))

            await db.commit()

        logger.info(f"User saved: {user_id}")

    except Exception as e:
        logger.error(
            f"Save user error: {e}",
            exc_info=True
        )
        
async def get_topic(user_id):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("""
                SELECT topic_id FROM users WHERE user_id=?
            """, (user_id,)) as cursor:

                row = await cursor.fetchone()
                return row[0] if row else None

    except Exception as e:
        logger.error(f"Get topic error: {e}", exc_info=True)
        return None


async def get_user(topic_id):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("""
                SELECT user_id FROM users WHERE topic_id=?
            """, (topic_id,)) as cursor:

                row = await cursor.fetchone()
                return row[0] if row else None

    except Exception as e:
        logger.error(f"Get user error: {e}", exc_info=True)
        return None

# FILE: database/db.py
# FUNCTION: get_user_by_topic (FIXED)

async def get_user_by_topic(topic_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT user_id FROM users WHERE topic_id = ?",
            (topic_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None