import aiosqlite

async def init_db(application):
    async with aiosqlite.connect("bot_history.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                genre TEXT NOT NULL,
                action INTEGER, -- 0: не цікавить, 1: збережено
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    print("База даних успішно ініціалізована")


async def get_favorites(user_id, item_type, genre):
    async with aiosqlite.connect("bot_history.db") as db:
        async with db.execute(
            "select id, item_name from history where user_id = ? and item_type = ? and genre = ? and action = 1",
            (user_id, item_type, genre)
        ) as cursor:
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}


async def get_black_list(user_id, item_type, genre) -> list:
    async with aiosqlite.connect("bot_history.db") as db:
        async with db.execute(
            "select item_name from history where user_id = ? and item_type = ? and genre = ?",
            (user_id, item_type, genre)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def set_user_history(user_id, item_name, item_type, genre, action):
    async with aiosqlite.connect("bot_history.db") as db:
        await db.execute(
            "insert into history (user_id, item_name, item_type, genre, action) values (?, ?, ?, ?, ?)",
            (user_id, item_name, item_type, genre, action)
        )
        await db.commit()


async def get_quantity(user_id, item_type=None, genre=None):
    async with aiosqlite.connect("bot_history.db") as db:
        query = "SELECT COUNT(*) FROM history WHERE user_id = ? AND action = 1"
        params = [user_id]
        if item_type:
            query += " AND item_type = ?"
            params.append(item_type)
        if genre:
            query += " AND genre = ?"
            params.append(genre)
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_quality(user_id, item_type=None):
    async  with aiosqlite.connect("bot_history.db") as db:
        if item_type:
            async with db.execute(
                "select distinct genre from history where user_id = ? and item_type = ? and action = 1",
                (user_id, item_type)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        else:
            async with db.execute(
                "select distinct item_type from history where user_id = ? and action = 1",
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

async def update_action_null(item_id, context):
    context.user_data['total_saved'] -= 1
    async with aiosqlite.connect("bot_history.db") as db:
        await db.execute(
            "update history set action = 0 where id = ?",
            (item_id,)
        )
        await db.commit()
