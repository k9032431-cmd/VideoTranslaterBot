from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from . import languages
from .i18n import UI_LANGUAGES, t

AUTO = "auto"
MODES = ("subtitles", "voice", "both")


class UiLangCb(CallbackData, prefix="ui"):
    lang: str


class SourceCb(CallbackData, prefix="src"):
    lang: str


class TargetCb(CallbackData, prefix="dst"):
    lang: str


class ModeCb(CallbackData, prefix="mode"):
    mode: str


class UpdateCb(CallbackData, prefix="upd"):
    action: str  # confirm | cancel


class NavCb(CallbackData, prefix="nav"):
    action: str  # back | cancel | start | abort


def main_menu(lang: str, is_admin: bool = False) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text=t(lang, "btn_translate"))
    kb.button(text=t(lang, "btn_language"))
    kb.button(text=t(lang, "btn_help"))
    if is_admin:
        kb.button(text=t(lang, "btn_update"))
    kb.adjust(1, 2, 1)
    return kb.as_markup(resize_keyboard=True, is_persistent=True)


def ui_languages() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code, label in UI_LANGUAGES.items():
        kb.button(text=label, callback_data=UiLangCb(lang=code))
    kb.adjust(1)
    return kb.as_markup()


def _nav_row(kb: InlineKeyboardBuilder, lang: str, back: bool) -> None:
    buttons = []
    if back:
        buttons.append(_button(t(lang, "btn_back"), NavCb(action="back")))
    buttons.append(_button(t(lang, "btn_cancel"), NavCb(action="cancel")))
    kb.row(*buttons)


def _button(text: str, data: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data.pack())


def cancel_only(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    _nav_row(kb, lang, back=False)
    return kb.as_markup()


def source_languages(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for language in languages.LANGUAGES:
        kb.button(text=language.label, callback_data=SourceCb(lang=language.code))
    kb.adjust(2)
    kb.row(_button(t(lang, "btn_auto"), SourceCb(lang=AUTO)))
    _nav_row(kb, lang, back=False)
    return kb.as_markup()


def target_languages(lang: str, exclude: str | None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for language in languages.LANGUAGES:
        if language.code != exclude:
            kb.button(text=language.label, callback_data=TargetCb(lang=language.code))
    kb.adjust(2)
    _nav_row(kb, lang, back=True)
    return kb.as_markup()


def modes(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for mode in MODES:
        kb.button(text=t(lang, f"mode_{mode}"), callback_data=ModeCb(mode=mode))
    kb.adjust(1)
    _nav_row(kb, lang, back=True)
    return kb.as_markup()


def confirm(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_start"), callback_data=NavCb(action="start"))
    kb.adjust(1)
    _nav_row(kb, lang, back=True)
    return kb.as_markup()


def update_confirm(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_update_yes"), callback_data=UpdateCb(action="confirm"))
    kb.button(text=t(lang, "btn_cancel"), callback_data=UpdateCb(action="cancel"))
    kb.adjust(2)
    return kb.as_markup()


def abort_job(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_cancel"), callback_data=NavCb(action="abort"))
    return kb.as_markup()
