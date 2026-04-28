from database.redis import r
from database.db import get_topic, save_topic


async def get_or_create_topic(user_id, create_topic_func):

    # 1 oldin tekshir
    topic = await get_topic(user_id)
    if topic:
        return topic

    # 2 lock
    lock = r.lock(
        f"topic_lock:{user_id}",
        timeout=10,
        blocking_timeout=3
    )

    async with lock:

        # 3 qayta tekshir
        topic = await get_topic(user_id)
        if topic:
            return topic

        # 4 yangi topic yarat
        topic_id = await create_topic_func()

        await save_topic(
            user_id,
            topic_id
        )

        return topic_id