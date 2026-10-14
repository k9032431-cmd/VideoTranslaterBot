from pathlib import Path

import aiosqlite


class UserStorage:
    """Persists each user's interface language between restarts."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._db: aiosqlite.Connection | None = None
        self._cache: dict[int, str] = {}

    async def open(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._path)
        await self._db.execute(
            "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, ui_lang TEXT NOT NULL)"
        )
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def get_language(self, user_id: int) -> str | None:
        if user_id in self._cache:
            return self._cache[user_id]
        assert self._db
        async with self._db.execute("SELECT ui_lang FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
        if row:
            self._cache[user_id] = row[0]
            return row[0]
        return None

    async def set_language(self, user_id: int, lang: str) -> None:
        assert self._db
        await self._db.execute(
            "INSERT INTO users (user_id, ui_lang) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET ui_lang = excluded.ui_lang",
            (user_id, lang),
        )
        await self._db.commit()
        self._cache[user_id] = lang
