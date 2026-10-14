from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from .config import Config
from .i18n import DEFAULT_UI_LANGUAGE, t
from .storage import UserStorage


class UserContextMiddleware(BaseMiddleware):
    """Rejects users outside ALLOWED_USER_IDS and injects `lang` / `has_lang` into handlers."""

    def __init__(self, config: Config, storage: UserStorage) -> None:
        self.config = config
        self.storage = storage

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return None

        stored = await self.storage.get_language(user.id)
        lang = stored or (user.language_code if user.language_code in ("ru", "en", "uk") else DEFAULT_UI_LANGUAGE)

        if self.config.allowed_user_ids and user.id not in self.config.allowed_user_ids:
            if isinstance(event, Message):
                await event.answer(t(lang, "access_denied"))
            elif isinstance(event, CallbackQuery):
                await event.answer(t(lang, "access_denied"), show_alert=True)
            return None

        data["lang"] = lang
        data["has_lang"] = stored is not None
        return await handler(event, data)
