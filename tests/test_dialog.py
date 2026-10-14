"""Drives the bot's button dialog through aiogram with a fake Telegram API."""

import datetime
from pathlib import Path

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, Update, User, Video

from bot import keyboards
from bot.config import Config
from bot.handlers import common, translate
from bot.i18n import t
from bot.middlewares import UserContextMiddleware
from bot.storage import UserStorage

USER = User(id=42, is_bot=False, first_name="Test", language_code="ru")
CHAT = Chat(id=42, type="private")


class FakeSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod] = []
        self._next_id = 100

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        if isinstance(method, (SendMessage, EditMessageText)):
            self._next_id += 1
            return Message(
                message_id=self._next_id, date=datetime.datetime.now(), chat=CHAT,
                text=method.text, from_user=User(id=1, is_bot=True, first_name="bot"),
            )
        return True

    async def stream_content(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def close(self):
        pass

    def texts(self) -> list[str]:
        return [r.text for r in self.requests if isinstance(r, (SendMessage, EditMessageText))]

    def last_markup_data(self) -> list[str]:
        for r in reversed(self.requests):
            if isinstance(r, (SendMessage, EditMessageText)) and r.reply_markup is not None:
                rows = getattr(r.reply_markup, "inline_keyboard", None) or []
                return [b.callback_data for row in rows for b in row]
        return []


class FakeJobs:
    def __init__(self) -> None:
        self.started = []

    def is_busy(self, user_id):
        return False

    def start(self, request):
        self.started.append(request)

    def cancel(self, user_id):
        return False


@pytest.fixture
async def env(tmp_path: Path):
    config = Config(
        bot_token="42:TEST", provider="openai", ai_api_key="x", ai_base_url=None, telegram_api_url=None,
        telegram_api_local=True, transcribe_model="w", translate_model="m", translate_reasoning_effort="", tts_engine="openai", tts_model="t", tts_voice="v", tts_gender="male",
        allowed_user_ids=frozenset(), max_video_minutes=180, max_concurrent_jobs=1, original_volume=0.2,
        data_dir=tmp_path,
    )
    storage = UserStorage(config.db_path)
    await storage.open()
    session = FakeSession()
    bot = Bot("42:TEST", session=session)
    jobs = FakeJobs()
    dp = Dispatcher(storage=MemoryStorage(), config=config, user_storage=storage, jobs=jobs)
    middleware = UserContextMiddleware(config, storage)
    dp.message.outer_middleware(middleware)
    dp.callback_query.outer_middleware(middleware)
    dp.include_routers(common.router, translate.router)
    yield dp, bot, session, jobs, config
    await storage.close()
    # Routers are module-level singletons: detach so the next test can attach them again.
    for router in (common.router, translate.router):
        router._parent_router = None


_update_id = 0


def _message(**kwargs) -> Update:
    global _update_id
    _update_id += 1
    return Update(update_id=_update_id, message=Message(
        message_id=_update_id, date=datetime.datetime.now(), chat=CHAT, from_user=USER, **kwargs
    ))


def _callback(data: str) -> Update:
    global _update_id
    _update_id += 1
    msg = Message(message_id=7, date=datetime.datetime.now(), chat=CHAT, text="…",
                  from_user=User(id=1, is_bot=True, first_name="bot"))
    return Update(update_id=_update_id, callback_query=CallbackQuery(
        id=str(_update_id), from_user=USER, chat_instance="1", data=data, message=msg
    ))


async def test_full_dialog(env):
    dp, bot, session, jobs, _ = env

    await dp.feed_update(bot, _message(text="/start"))
    assert session.texts()[-1] == t("ru", "choose_ui_language")
    assert keyboards.UiLangCb(lang="en").pack() in session.last_markup_data()

    await dp.feed_update(bot, _callback(keyboards.UiLangCb(lang="ru").pack()))
    assert t("ru", "welcome") in session.texts()

    await dp.feed_update(bot, _message(text=t("ru", "btn_translate")))
    assert session.texts()[-1] == t("ru", "send_video")

    await dp.feed_update(bot, _message(text="hello"))
    assert session.texts()[-1] == t("ru", "not_a_video")

    video = Video(file_id="FILE", file_unique_id="U", width=640, height=360, duration=125,
                  file_name="film.mp4", file_size=5_000_000)
    await dp.feed_update(bot, _message(video=video))
    assert session.texts()[-1] == t("ru", "choose_source")
    assert "film.mp4" in session.texts()[-2] and "(2:05)" in session.texts()[-2]

    await dp.feed_update(bot, _callback(keyboards.SourceCb(lang="ru").pack()))
    assert session.texts()[-1] == t("ru", "choose_target")
    assert keyboards.TargetCb(lang="ru").pack() not in session.last_markup_data()

    # back to source and forward again
    await dp.feed_update(bot, _callback(keyboards.NavCb(action="back").pack()))
    assert session.texts()[-1] == t("ru", "choose_source")
    await dp.feed_update(bot, _callback(keyboards.SourceCb(lang="ru").pack()))

    await dp.feed_update(bot, _callback(keyboards.TargetCb(lang="en").pack()))
    assert session.texts()[-1] == t("ru", "choose_mode")

    await dp.feed_update(bot, _callback(keyboards.ModeCb(mode="both").pack()))
    summary = session.texts()[-1]
    assert "film.mp4" in summary and "Русский" in summary and "English" in summary

    await dp.feed_update(bot, _callback(keyboards.NavCb(action="start").pack()))
    assert len(jobs.started) == 1
    req = jobs.started[0]
    assert (req.file_id, req.source, req.target, req.mode, req.lang) == ("FILE", "ru", "en", "both", "ru")

    # pressing an old button after the job started is handled gracefully
    await dp.feed_update(bot, _callback(keyboards.ModeCb(mode="voice").pack()))
    answers = [r for r in session.requests if isinstance(r, AnswerCallbackQuery)]
    assert answers[-1].text == t("ru", "session_expired")


async def test_change_language_from_menu(env):
    dp, bot, session, _, _ = env
    await dp.feed_update(bot, _message(text="/start"))
    await dp.feed_update(bot, _callback(keyboards.UiLangCb(lang="ru").pack()))
    await dp.feed_update(bot, _message(text=t("ru", "btn_language")))
    await dp.feed_update(bot, _callback(keyboards.UiLangCb(lang="en").pack()))
    assert session.texts()[-1] == t("en", "menu")
    await dp.feed_update(bot, _message(text=t("en", "btn_translate")))
    assert session.texts()[-1] == t("en", "send_video")


async def test_too_big_file_rejected(env):
    dp, bot, session, jobs, _ = env
    video = Video(file_id="F", file_unique_id="U", width=1, height=1, duration=60,
                  file_name="big.mp4", file_size=30 * 1024 * 1024)
    await dp.feed_update(bot, _message(video=video))
    assert "30.0" in session.texts()[-1] and "20" in session.texts()[-1]
    assert not jobs.started


async def test_access_restricted(env, tmp_path):
    dp, bot, session, _, config = env
    object.__setattr__(config, "allowed_user_ids", frozenset({1}))
    await dp.feed_update(bot, _message(text="/start"))
    assert session.texts()[-1] == t("ru", "access_denied")
