from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import keyboards
from ..config import Config
from ..i18n import UI_LANGUAGES, all_variants, t
from ..storage import UserStorage

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, lang: str, has_lang: bool) -> None:
    await state.clear()
    if not has_lang:
        await message.answer(t(lang, "choose_ui_language"), reply_markup=keyboards.ui_languages())
        return
    await message.answer(t(lang, "welcome"), reply_markup=keyboards.main_menu(lang))


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await message.answer(t(lang, "menu"), reply_markup=keyboards.main_menu(lang))


@router.message(Command("language"))
@router.message(F.text.in_(all_variants("btn_language")))
async def cmd_language(message: Message, lang: str) -> None:
    await message.answer(t(lang, "choose_ui_language"), reply_markup=keyboards.ui_languages())


@router.callback_query(keyboards.UiLangCb.filter(F.lang.in_(UI_LANGUAGES)))
async def on_ui_language(
    callback: CallbackQuery, callback_data: keyboards.UiLangCb, user_storage: UserStorage, has_lang: bool
) -> None:
    new_lang = callback_data.lang
    await user_storage.set_language(callback.from_user.id, new_lang)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(t(new_lang, "ui_language_set"))
        text = t(new_lang, "menu") if has_lang else t(new_lang, "welcome")
        await callback.message.answer(text, reply_markup=keyboards.main_menu(new_lang))


@router.message(Command("help"))
@router.message(F.text.in_(all_variants("btn_help")))
async def cmd_help(message: Message, lang: str, config: Config) -> None:
    await message.answer(t(
        lang, "help",
        max_mb=config.max_download_bytes // (1024 * 1024),
        max_min=config.max_video_minutes,
    ))
