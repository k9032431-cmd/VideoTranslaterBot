import html

from aiogram import F, Router
import io

from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import keyboards, sources
from ..config import Config
from ..i18n import UI_LANGUAGES, all_variants, t
from ..storage import UserStorage
from ..updater import Updater

router = Router(name="common")


class CookiesFlow(StatesGroup):
    waiting = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, lang: str, has_lang: bool, is_admin: bool) -> None:
    await state.clear()
    if not has_lang:
        await message.answer(t(lang, "choose_ui_language"), reply_markup=keyboards.ui_languages())
        return
    await message.answer(t(lang, "welcome"), reply_markup=keyboards.main_menu(lang, is_admin))


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, lang: str, is_admin: bool) -> None:
    await state.clear()
    await message.answer(t(lang, "menu"), reply_markup=keyboards.main_menu(lang, is_admin))


@router.message(Command("language"))
@router.message(F.text.in_(all_variants("btn_language")))
async def cmd_language(message: Message, lang: str) -> None:
    await message.answer(t(lang, "choose_ui_language"), reply_markup=keyboards.ui_languages())


@router.callback_query(keyboards.UiLangCb.filter(F.lang.in_(UI_LANGUAGES)))
async def on_ui_language(
    callback: CallbackQuery, callback_data: keyboards.UiLangCb, user_storage: UserStorage, has_lang: bool,
    is_admin: bool,
) -> None:
    new_lang = callback_data.lang
    await user_storage.set_language(callback.from_user.id, new_lang)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(t(new_lang, "ui_language_set"))
        text = t(new_lang, "menu") if has_lang else t(new_lang, "welcome")
        await callback.message.answer(text, reply_markup=keyboards.main_menu(new_lang, is_admin))


@router.message(Command("help"))
@router.message(F.text.in_(all_variants("btn_help")))
async def cmd_help(message: Message, lang: str, config: Config) -> None:
    await message.answer(t(
        lang, "help",
        max_mb=config.max_download_bytes // (1024 * 1024),
        max_min=config.max_video_minutes,
    ))


@router.message(F.text.in_(all_variants("btn_update")))
async def cmd_update(message: Message, lang: str, is_admin: bool, updater: Updater) -> None:
    if not is_admin:
        return
    if updater.running:
        await message.answer(t(lang, "update_in_progress"))
        return
    await message.answer(
        t(lang, "update_confirm", version=html.escape(updater.version())),
        reply_markup=keyboards.update_confirm(lang),
    )


@router.callback_query(keyboards.UpdateCb.filter())
async def on_update(
    callback: CallbackQuery, callback_data: keyboards.UpdateCb, lang: str, is_admin: bool, updater: Updater
) -> None:
    await callback.answer()
    if not is_admin:
        return
    if callback_data.action != "confirm":
        await callback.message.edit_text(t(lang, "cancelled"))
        return
    if updater.running:
        await callback.message.edit_text(t(lang, "update_in_progress"))
        return
    updater.start(callback.message.chat.id, lang)
    await callback.message.edit_text(t(lang, "update_started"))


@router.message(Command("cookies"))
async def cmd_cookies(
    message: Message, command: CommandObject, state: FSMContext, lang: str, is_admin: bool, config: Config,
) -> None:
    """YouTube refuses servers without a signed-in account: the admin can hand over its cookies."""
    if not is_admin:
        return
    if (command.args or "").strip().lower() in ("delete", "off", "удалить"):
        config.cookies_path.unlink(missing_ok=True)
        await message.answer(t(lang, "cookies_deleted"))
        return
    await state.set_state(CookiesFlow.waiting)
    has = config.cookies_path.exists()
    await message.answer(t(lang, "cookies_prompt", status=t(lang, "cookies_on" if has else "cookies_off")))


@router.message(CookiesFlow.waiting, F.document)
async def on_cookies_file(message: Message, state: FSMContext, lang: str, is_admin: bool, config: Config) -> None:
    if not is_admin:
        return
    if (message.document.file_size or 0) > 1024 * 1024:
        await message.answer(t(lang, "cookies_invalid"))
        return
    buffer = io.BytesIO()
    await message.bot.download(message.document, destination=buffer)
    text = buffer.getvalue().decode("utf-8", errors="replace")
    if not sources.looks_like_cookies(text):
        await message.answer(t(lang, "cookies_invalid"))
        return
    config.cookies_path.write_text(text, encoding="utf-8")
    config.cookies_path.chmod(0o600)
    await state.clear()
    await message.delete()  # the file is a login to the account: don't keep it in the chat
    await message.answer(t(lang, "cookies_saved"))
