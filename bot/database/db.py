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

        # ⬇⬇⬇ YANGI JADVAL — STALE SESSION DETECTION ⬇⬇⬇
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_activity (
                user_id BIGINT PRIMARY KEY,
                last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)

        # ⬇⬇⬇ YANGI JADVAL — REMINDERS ⬇⬇⬇
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                topic_id BIGINT,
                phone TEXT,
                expiry_date_text TEXT,
                expiry_date DATE,
                remind_days INT DEFAULT 7,
                status TEXT DEFAULT 'pending',
                request_msg_id BIGINT,
                last_notified_date DATE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        # status: pending | confirmed | notified | done | cancelled
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_reminders_expiry
            ON reminders(expiry_date) WHERE status = 'confirmed'
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_reminders_request_msg
            ON reminders(request_msg_id) WHERE request_msg_id IS NOT NULL
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


# ---------------- USER ACTIVITY (Stale Session Detection) ----------------
async def update_last_activity(user_id):
    """Foydalanuvchining oxirgi faolligini yangilaydi."""
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO user_activity (user_id, last_activity)
                VALUES ($1, NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET last_activity = NOW()
            """, user_id)
    except Exception as e:
        logger.error(f"Update activity error: {e}", exc_info=True)


async def get_last_activity(user_id):
    """Foydalanuvchining oxirgi faollik vaqtini qaytaradi."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT last_activity FROM user_activity WHERE user_id=$1",
                user_id
            )
            return row["last_activity"] if row else None
    except Exception as e:
        logger.error(f"Get activity error: {e}", exc_info=True)
        return None


# Eski nom uchun alias
get_user_by_topic = get_user


# ---------------- REMINDERS ----------------
async def save_reminder(user_id, topic_id, phone, expiry_date_text, remind_days):
    """So'rovnoma to'ldirilganda — pending eslatma yaratiladi."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO reminders (user_id, topic_id, phone, expiry_date_text, remind_days, status)
                VALUES ($1, $2, $3, $4, $5, 'pending')
                RETURNING id
            """, user_id, topic_id, phone, expiry_date_text, remind_days)
        logger.info(f"Reminder created: user={user_id}, id={row['id']}")
        return row["id"]
    except Exception as e:
        logger.error(f"Save reminder error: {e}", exc_info=True)
        return None


async def attach_request_msg_id(reminder_id, msg_id):
    """Topic'dagi xabar ID sini eslatmaga bog'laydi (reply uchun)."""
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE reminders SET request_msg_id=$1 WHERE id=$2
            """, msg_id, reminder_id)
    except Exception as e:
        logger.error(f"Attach msg_id error: {e}", exc_info=True)


async def confirm_reminder_by_msg(request_msg_id, expiry_date):
    """Operator reply qilib sanani yozdi — eslatmani tasdiqlaymiz."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE reminders
                SET expiry_date=$1, status='confirmed'
                WHERE request_msg_id=$2 AND status='pending'
                RETURNING id, user_id, topic_id, phone, remind_days
            """, expiry_date, request_msg_id)
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Confirm reminder error: {e}", exc_info=True)
        return None


async def get_due_reminders(today):
    """Bugun eslatish kerak bo'lgan eslatmalarni qaytaradi.
    today: date object. Eslatma sanasi = expiry_date - remind_days <= today < expiry_date."""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, user_id, topic_id, phone, expiry_date, remind_days
                FROM reminders
                WHERE status = 'confirmed'
                  AND (expiry_date - remind_days) <= $1
                  AND expiry_date >= $1
                  AND (last_notified_date IS NULL OR last_notified_date < $1)
            """, today)
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Get due reminders error: {e}", exc_info=True)
        return []


async def mark_notified(reminder_id, today):
    """Eslatma bugun yuborildi — qayta yubormaslik uchun belgi."""
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE reminders SET last_notified_date=$1 WHERE id=$2
            """, today, reminder_id)
    except Exception as e:
        logger.error(f"Mark notified error: {e}", exc_info=True)


async def get_reminder(reminder_id):
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, user_id, topic_id, phone, expiry_date, remind_days, status
                FROM reminders WHERE id=$1
            """, reminder_id)
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Get reminder error: {e}", exc_info=True)
        return None