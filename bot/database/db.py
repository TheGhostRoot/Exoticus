
from __future__ import annotations

import asyncio
import functools
import typing as t

import asyncpg
import aiofiles
from apscheduler.triggers.cron import CronTrigger

from bot.config import Config
class Database:
    def __init__(self, bot) -> None:
        self.bot = bot
        self.host = self.bot.config.PG_HOST
        self.user = self.bot.config.PG_USER
        self.password = self.bot.config.PG_PASS
        self.port = self.bot.config.PG_PORT
        self.schema = self.bot.config.PG_DB
        self.build = self.bot._static + "/build.sql"
        self._calls = 0


    pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            user=self.user,
            host=self.host,
            port=self.port,
            database=self.schema,
            password=self.password,
            loop=asyncio.get_running_loop(),
        )

        await self.executescript(self.build)
        await self.commit()

    async def close(self) -> None:
        await self.commit()
        if self.pool is not None:
            await self.pool.close()

    async def sync(self) -> None:
            # Insert.
            my_guilds = await self.bot.rest.fetch_my_guilds()

            await self.execute(f"CREATE TABLE IF NOT EXISTS {self.schema}.system (GUILD_ID BIGINT PRIMARY KEY)")
            await self.executemany(f"INSERT INTO {self.schema}.system (GUILD_ID) VALUES ($1) ON CONFLICT DO NOTHING", [(g.id,) for g in my_guilds])

            # Remove.
            stored = await self.column(f"SELECT GUILD_ID FROM {self.schema}.system")
            member_of = [g.id for g in my_guilds]
            removals = [(g_id,) for g_id in set(stored) - set(member_of)]
            await self.executemany(f"DELETE FROM {self.schema}.system WHERE GUILD_ID = $1", removals)

            # Commit.
            await self.commit()

    @staticmethod
    def with_connection(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:

        @functools.wraps(func)
        async def wrapper(self: Database, *args: t.Any) -> t.Any:
            if self.pool is None:
                raise ValueError("Database connection pool is not initialized.")
            async with self.pool.acquire() as conn:
                self._calls += 1
                return await func(self, *args, conn=conn)

        return wrapper

    @with_connection
    async def commit(self, conn: asyncpg.Connection) -> None:
        if hasattr(self.bot, 'ready') and self.bot.ready.ok:
            async with conn.transaction() as tr:
                await self.execute("UPDATE bot SET Value = CURRENT_TIMESTAMP WHERE Key = 'last commit'")

    @with_connection
    async def field(
        self, sql: str, *values: tuple[t.Any], conn: asyncpg.Connection
    ) -> t.Any | None:
        query = await conn.prepare(sql)
        return await query.fetchval(*values)

    @with_connection
    async def record(
        self, sql: str, *values: t.Any, conn: asyncpg.Connection
    ) -> t.Optional[t.List[t.Any]]:
        query = await conn.prepare(sql)
        if data := await query.fetchrow(*values):
            return [r for r in data]

        return None

    @with_connection
    async def records(
        self, sql: str, *values: t.Any, conn: asyncpg.Connection
    ) -> t.Optional[t.List[t.Iterable[t.Any]]]:
        query = await conn.prepare(sql)
        if data := await query.fetch(*values):
            return [*map(lambda r: tuple(r.values()), data)]

        return None

    @with_connection
    async def column(
        self, sql: str, *values: t.Any, conn: asyncpg.Connection
    ) -> t.List[t.Any]:
        query = await conn.prepare(sql)
        return [r[0] for r in await query.fetch(*values)]

    @with_connection
    async def execute(self, sql: str, *values: t.Any, conn: asyncpg.Connection) -> None:
        query = await conn.prepare(sql)
        await query.fetch(*values)

    @with_connection
    async def executemany(
        self, sql: str, values: t.List[t.Iterable[t.Any]], conn: asyncpg.Connection
    ) -> None:
        query = await conn.prepare(sql)
        await query.executemany(values)

    @with_connection
    async def executescript(self, path: str, conn: asyncpg.Connection) -> None:
        async with aiofiles.open(path, "r", encoding="utf-8") as script:
            await conn.execute((await script.read()))


# Example of how to update a record in the database
"""
from pypika import Query, Table

    if bot_obj:
        sector = Schema(bot_obj.db.schema)
        query = Query.update(sector.system).set(sector.system.log_channel_id, '12321313').where(sector.system.guild_id == guild_id)
        await bot_obj.db.execute(query.get_sql())  
"""
# Example of how to get a record from the database
"""
    if bot_obj:
        sector = Schema(bot_obj.db.schema)
        query = Query.from_(sector.system).select(sector.system.log_channel_id).where(sector.system.guild_id == guild_id)
        test = await bot_obj.db.field(query.get_sql())
"""