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
                topic_id BIGINT UNIQUE,
                status_msg_id BIGINT
            )
        """)
        # Migratsiya: avvaldan yaratilgan jadvalga ustun qo'shish
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS status_msg_id BIGINT
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
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_activity (
                user_id BIGINT PRIMARY KEY,
                last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
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
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id BIGINT PRIMARY KEY,
                last_seen TIMESTAMP WITH TIME ZONE,
                state_set_at TIMESTAMP WITH TIME ZONE
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_checks (
                user_id BIGINT PRIMARY KEY,
                requested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_reminders_expiry
            ON reminders(expiry_date) WHERE status = 'confirmed'
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_reminders_request_msg
            ON reminders(request_msg_id) WHERE request_msg_id IS NOT NULL
        """)

    logger.info("POSTGRES READY")


# ---------------- USERS ----------------
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


# ---------------- USER ACTIVITY ----------------
async def update_last_activity(user_id):
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO user_activity (user_id, last_activity)
                VALUES ($1, NOW())
                ON CONFLICT (user_id) DO UPDATE SET last_activity = NOW()
            """, user_id)
    except Exception as e:
        logger.error(f"Update activity error: {e}", exc_info=True)


async def get_last_activity(user_id):
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT last_activity FROM user_activity WHERE user_id=$1", user_id
            )
            return row["last_activity"] if row else None
    except Exception as e:
        logger.error(f"Get activity error: {e}", exc_info=True)
        return None


get_user_by_topic = get_user


# ---------------- TOPIC: ATOMIC GET-OR-CREATE ----------------
async def get_or_create_topic(user_id: int, full_name: str, bot, group_id: int) -> int | None:
    """
    Topic yaratishni atomar qiladi. PostgreSQL advisory lock orqali bir foydalanuvchi
    uchun parallel callbacklarda dublikat topic ochilishini oldini oladi.
    """
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock($1)", user_id)
                row = await conn.fetchrow(
                    "SELECT topic_id FROM users WHERE user_id=$1", user_id
                )
                if row and row["topic_id"]:
                    return row["topic_id"]

                topic = await bot.create_forum_topic(
                    chat_id=group_id,
                    name=f"{full_name} | {user_id}"
                )
                topic_id = topic.message_thread_id

                await conn.execute("""
                    INSERT INTO users (user_id, topic_id)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO UPDATE SET topic_id = EXCLUDED.topic_id
                """, user_id, topic_id)

                logger.info(f"Topic created: user={user_id} → topic={topic_id}")
                return topic_id
    except Exception as e:
        logger.error(f"get_or_create_topic error: {e}", exc_info=True)
        return None


# ---------------- USER STATUS MESSAGE (operator panel) ----------------
async def get_status_msg_id(user_id: int) -> int | None:
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status_msg_id FROM users WHERE user_id=$1", user_id
            )
            return row["status_msg_id"] if row and row["status_msg_id"] else None
    except Exception as e:
        logger.error(f"get_status_msg_id error: {e}", exc_info=True)
        return None


async def set_status_msg_id(user_id: int, msg_id: int | None) -> None:
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET status_msg_id=$1 WHERE user_id=$2",
                msg_id, user_id
            )
    except Exception as e:
        logger.error(f"set_status_msg_id error: {e}", exc_info=True)


# ---------------- PENDING CHECKS ----------------
async def add_pending_check(user_id: int) -> None:
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO pending_checks (user_id, requested_at)
                VALUES ($1, NOW())
                ON CONFLICT (user_id) DO UPDATE SET requested_at = NOW()
            """, user_id)
    except Exception as e:
        logger.error(f"add_pending_check error: {e}", exc_info=True)


async def is_awaiting_check(user_id: int) -> bool:
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM pending_checks WHERE user_id=$1", user_id
            )
            return row is not None
    except Exception as e:
        logger.error(f"is_awaiting_check error: {e}", exc_info=True)
        return False


async def remove_pending_check(user_id: int) -> None:
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM pending_checks WHERE user_id=$1", user_id
            )
    except Exception as e:
        logger.error(f"remove_pending_check error: {e}", exc_info=True)


# ---------------- REMINDERS ----------------
async def save_reminder(user_id, topic_id, phone, expiry_date_text, remind_days):
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
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE reminders SET request_msg_id=$1 WHERE id=$2
            """, msg_id, reminder_id)
    except Exception as e:
        logger.error(f"Attach msg_id error: {e}", exc_info=True)


async def confirm_reminder_by_msg(request_msg_id, expiry_date):
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


# ---------------- STATE TRACKING (Stale Session Detection) ----------------
async def set_user_state_time(user_id: int) -> None:
    """Har state.set_state() dan KEYIN chaqiring."""
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO user_sessions (user_id, state_set_at, last_seen)
                VALUES ($1, NOW(), NOW())
                ON CONFLICT (user_id) DO UPDATE
                    SET state_set_at = NOW(),
                        last_seen    = NOW()
            """, user_id)
    except Exception as e:
        logger.error(f"set_user_state_time error: {e}", exc_info=True)


async def clear_user_state_time(user_id: int) -> None:
    """Har state.clear() dan KEYIN chaqiring."""
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO user_sessions (user_id, state_set_at, last_seen)
                VALUES ($1, NULL, NOW())
                ON CONFLICT (user_id) DO UPDATE
                    SET state_set_at = NULL,
                        last_seen    = NOW()
            """, user_id)
    except Exception as e:
        logger.error(f"clear_user_state_time error: {e}", exc_info=True)