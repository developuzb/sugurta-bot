import logging
from datetime import datetime
import asyncpg
from config import DATABASE_URL

logger = logging.getLogger(__name__)

pool = None


# ---------------- INIT ----------------
async def init_postgres():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                topic_id BIGINT UNIQUE
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                topic_id BIGINT,
                amount BIGINT,
                status TEXT,
                deadline TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS temp_orders (
                user_id BIGINT PRIMARY KEY,
                vehicle TEXT,
                region TEXT,
                insurance_type TEXT,
                price BIGINT,
                bonus BIGINT,
                created_at TIMESTAMP
            )
        """)

    logger.info("POSTGRES READY")


# init_db endi init_postgres bilan bir xil — eski importlarni buzmaslik uchun
async def init_db():
    await init_postgres()


# ---------------- USERS ----------------
async def save_user(user_id, topic_id):
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, topic_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET topic_id = EXCLUDED.topic_id
            """, user_id, topic_id)
        logger.info(f"User saved: {user_id} → topic {topic_id}")
    except Exception as e:
        logger.error(f"Save user error: {e}", exc_info=True)


async def get_topic(user_id):
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT topic_id FROM users WHERE user_id=$1", user_id
            )
            return row["topic_id"] if row else None
    except Exception as e:
        logger.error(f"Get topic error: {e}", exc_info=True)
        return None


async def get_user(topic_id):
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT user_id FROM users WHERE topic_id=$1", topic_id
            )
            return row["user_id"] if row else None
    except Exception as e:
        logger.error(f"Get user error: {e}", exc_info=True)
        return None


# ---------------- TEMP ORDER ----------------
async def save_temp_order(user_id, data):
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO temp_orders 
                (user_id, vehicle, region, insurance_type, price, bonus, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (user_id) DO UPDATE SET
                    vehicle = EXCLUDED.vehicle,
                    region = EXCLUDED.region,
                    insurance_type = EXCLUDED.insurance_type,
                    price = EXCLUDED.price,
                    bonus = EXCLUDED.bonus,
                    created_at = EXCLUDED.created_at
            """,
                user_id,
                data['vehicle'],
                data['region'],
                data['insurance_type'],
                data['price'],
                data['bonus'],
                datetime.now()
            )
        logger.info(f"Temp order saved: {user_id}")
    except Exception as e:
        logger.error(f"Save temp order error: {e}", exc_info=True)


async def get_temp_order(user_id):
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT vehicle, region, insurance_type, price, bonus
                FROM temp_orders WHERE user_id=$1
            """, user_id)
            if not row:
                return None
            return {
                "vehicle": row["vehicle"],
                "region": row["region"],
                "insurance_type": row["insurance_type"],
                "price": row["price"],
                "bonus": row["bonus"]
            }
    except Exception as e:
        logger.error(f"Get temp order error: {e}", exc_info=True)
        return None


# ---------------- ORDERS ----------------
async def save_order(user_id, topic_id, amount, status, deadline):
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO orders (user_id, topic_id, amount, status, deadline)
                VALUES ($1, $2, $3, $4, $5)
            """, user_id, topic_id, amount, status, deadline)
        logger.info(f"Order saved: {user_id}")
    except Exception as e:
        logger.error(f"Save order error: {e}", exc_info=True)


async def update_order_status(user_id, status):
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE orders SET status=$1
                WHERE id = (
                    SELECT id FROM orders WHERE user_id=$2
                    ORDER BY id DESC LIMIT 1
                )
            """, status, user_id)
        logger.info(f"Order status updated: {user_id} → {status}")
    except Exception as e:
        logger.error(f"Update order error: {e}", exc_info=True)
        
        
# Eski nom uchun alias
get_user_by_topic = get_user        
        