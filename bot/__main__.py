import asyncio
import logging
import shutil

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from openai import AsyncOpenAI

from .config import load_config
from .handlers import common, translate
from .i18n import UI_LANGUAGES
from .jobs import JobManager
from .middlewares import UserContextMiddleware
from .storage import UserStorage
from .updater import Updater

COMMANDS = {
    "ru": [("start", "Запустить бота"), ("translate", "Перевести видео"), ("menu", "Главное меню"),
           ("language", "Язык бота"), ("help", "Помощь"), ("cancel", "Отменить")],
    "en": [("start", "Start the bot"), ("translate", "Translate a video"), ("menu", "Main menu"),
           ("language", "Bot language"), ("help", "Help"), ("cancel", "Cancel")],
    "uk": [("start", "Запустити бота"), ("translate", "Перекласти відео"), ("menu", "Головне меню"),
           ("language", "Мова бота"), ("help", "Допомога"), ("cancel", "Скасувати")],
}


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_config()

    # Leftovers from a previous run that was killed mid-job.
    shutil.rmtree(config.work_dir, ignore_errors=True)
    config.work_dir.mkdir(parents=True, exist_ok=True)

    session = None
    if config.telegram_api_url:
        session = AiohttpSession(
            api=TelegramAPIServer.from_base(config.telegram_api_url, is_local=config.telegram_api_local)
        )
    bot = Bot(config.bot_token, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    storage = UserStorage(config.db_path)
    await storage.open()
    # Groq's free tier answers 429 often (per-minute limits); the client waits and retries.
    client = None
    if config.provider != "local":
        client = AsyncOpenAI(
            api_key=config.ai_api_key, base_url=config.ai_base_url,
            max_retries=10 if config.provider == "free" else 5, timeout=600,
        )
    jobs = JobManager(bot, config, client)

    updater = Updater(bot, config.data_dir)
    updater.resume()  # report an update that restarted the bot
    dp = Dispatcher(storage=MemoryStorage(), config=config, user_storage=storage, jobs=jobs, updater=updater)
    middleware = UserContextMiddleware(config, storage)
    dp.message.outer_middleware(middleware)
    dp.callback_query.outer_middleware(middleware)
    dp.include_routers(common.router, translate.router)

    for code in UI_LANGUAGES:
        await bot.set_my_commands(
            [BotCommand(command=c, description=d) for c, d in COMMANDS[code]],
            language_code=code,
        )
    await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in COMMANDS["en"]])

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await storage.close()
        if client:
            await client.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
