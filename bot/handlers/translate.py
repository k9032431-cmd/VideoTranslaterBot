import html
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import keyboards, languages
from ..config import Config
from ..i18n import all_variants, t
from ..jobs import JobManager, JobRequest

router = Router(name="translate")

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".wmv", ".ts", ".mts", ".3gp", ".mpg", ".mpeg"}


class Flow(StatesGroup):
    waiting_video = State()
    source = State()
    target = State()
    mode = State()
    confirm = State()


def _video_info(message: Message) -> tuple[str, str, int | None, int | None] | None:
    """(file_id, file_name, size, duration) if the message carries a video."""
    if message.video:
        v = message.video
        return v.file_id, v.file_name or "video.mp4", v.file_size, v.duration
    if message.video_note:
        v = message.video_note
        return v.file_id, "video_note.mp4", v.file_size, v.duration
    if message.document:
        d = message.document
        name = d.file_name or "video"
        if (d.mime_type or "").startswith("video/") or Path(name).suffix.lower() in VIDEO_EXTENSIONS:
            return d.file_id, name, d.file_size, None
    return None


def _source_label(lang: str, code: str) -> str:
    return t(lang, "auto_detect") if code == keyboards.AUTO else languages.get(code).label


@router.message(Command("translate"))
@router.message(F.text.in_(all_variants("btn_translate")))
async def start_flow(message: Message, state: FSMContext, lang: str, jobs: JobManager) -> None:
    if jobs.is_busy(message.from_user.id):
        await message.answer(t(lang, "busy"), reply_markup=keyboards.abort_job(lang))
        return
    await state.clear()
    await state.set_state(Flow.waiting_video)
    await message.answer(t(lang, "send_video"), reply_markup=keyboards.cancel_only(lang))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, lang: str, jobs: JobManager) -> None:
    had_state = await state.get_state() is not None
    await state.clear()
    if jobs.cancel(message.from_user.id) or had_state:
        await message.answer(t(lang, "cancelled"), reply_markup=keyboards.main_menu(lang))
    else:
        await message.answer(t(lang, "nothing_to_cancel"), reply_markup=keyboards.main_menu(lang))


@router.message(F.video | F.video_note | F.document)
async def on_video(message: Message, state: FSMContext, lang: str, config: Config, jobs: JobManager) -> None:
    info = _video_info(message)
    if info is None:
        await message.answer(t(lang, "not_a_video"))
        return
    if jobs.is_busy(message.from_user.id):
        await message.answer(t(lang, "busy"), reply_markup=keyboards.abort_job(lang))
        return
    file_id, name, size, duration = info

    max_bytes = config.max_download_bytes
    if size and size > max_bytes:
        await message.answer(t(
            lang, "too_big", size_mb=round(size / 1024 / 1024, 1), max_mb=max_bytes // (1024 * 1024)
        ))
        return
    if duration and duration // 60 >= config.max_video_minutes:
        await message.answer(t(lang, "too_long", minutes=duration // 60, max_min=config.max_video_minutes))
        return

    await state.clear()
    await state.set_state(Flow.source)
    await state.update_data(file_id=file_id, file_name=name)

    duration_text = f" ({duration // 60}:{duration % 60:02d})" if duration else ""
    await message.reply(t(lang, "video_received", name=html.escape(name), duration=duration_text))
    await message.answer(t(lang, "choose_source"), reply_markup=keyboards.source_languages(lang))


@router.message(Flow.waiting_video)
async def on_not_video(message: Message, lang: str) -> None:
    await message.answer(t(lang, "not_a_video"), reply_markup=keyboards.cancel_only(lang))


# --- steps --------------------------------------------------------------------------------------


async def _show_source(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.set_state(Flow.source)
    await callback.message.edit_text(t(lang, "choose_source"), reply_markup=keyboards.source_languages(lang))


async def _show_target(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    await state.set_state(Flow.target)
    await callback.message.edit_text(
        t(lang, "choose_target"), reply_markup=keyboards.target_languages(lang, exclude=data["source"])
    )


async def _show_mode(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.set_state(Flow.mode)
    await callback.message.edit_text(t(lang, "choose_mode"), reply_markup=keyboards.modes(lang))


async def _show_confirm(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    await state.set_state(Flow.confirm)
    await callback.message.edit_text(
        t(
            lang, "summary",
            name=html.escape(data["file_name"]),
            source=_source_label(lang, data["source"]),
            target=languages.get(data["target"]).label,
            mode=t(lang, f"mode_{data['mode']}"),
        ),
        reply_markup=keyboards.confirm(lang),
    )


@router.callback_query(Flow.source, keyboards.SourceCb.filter())
async def on_source(callback: CallbackQuery, callback_data: keyboards.SourceCb, state: FSMContext, lang: str) -> None:
    if callback_data.lang != keyboards.AUTO and callback_data.lang not in languages.BY_CODE:
        await callback.answer()
        return
    await state.update_data(source=callback_data.lang)
    await callback.answer()
    await _show_target(callback, state, lang)


@router.callback_query(Flow.target, keyboards.TargetCb.filter())
async def on_target(callback: CallbackQuery, callback_data: keyboards.TargetCb, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    if callback_data.lang not in languages.BY_CODE or callback_data.lang == data.get("source"):
        await callback.answer()
        return
    await state.update_data(target=callback_data.lang)
    await callback.answer()
    await _show_mode(callback, state, lang)


@router.callback_query(Flow.mode, keyboards.ModeCb.filter(F.mode.in_(keyboards.MODES)))
async def on_mode(callback: CallbackQuery, callback_data: keyboards.ModeCb, state: FSMContext, lang: str) -> None:
    await state.update_data(mode=callback_data.mode)
    await callback.answer()
    await _show_confirm(callback, state, lang)


@router.callback_query(keyboards.NavCb.filter(F.action == "back"), StateFilter(Flow.target, Flow.mode, Flow.confirm))
async def on_back(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    current = await state.get_state()
    await callback.answer()
    if current == Flow.target.state:
        await _show_source(callback, state, lang)
    elif current == Flow.mode.state:
        await _show_target(callback, state, lang)
    else:
        await _show_mode(callback, state, lang)


@router.callback_query(keyboards.NavCb.filter(F.action == "cancel"))
async def on_cancel(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(t(lang, "cancelled"))


@router.callback_query(Flow.confirm, keyboards.NavCb.filter(F.action == "start"))
async def on_start(callback: CallbackQuery, state: FSMContext, lang: str, jobs: JobManager) -> None:
    user_id = callback.from_user.id
    if jobs.is_busy(user_id):
        await callback.answer(t(lang, "busy"), show_alert=True)
        return
    data = await state.get_data()
    await state.clear()
    await callback.answer()
    message = await callback.message.edit_text(t(lang, "stage_download"), reply_markup=keyboards.abort_job(lang))
    jobs.start(JobRequest(
        user_id=user_id,
        chat_id=callback.message.chat.id,
        status_message_id=message.message_id if isinstance(message, Message) else callback.message.message_id,
        lang=lang,
        file_id=data["file_id"],
        file_name=data["file_name"],
        source=data["source"],
        target=data["target"],
        mode=data["mode"],
    ))


@router.callback_query(keyboards.NavCb.filter(F.action == "abort"))
async def on_abort(callback: CallbackQuery, lang: str, jobs: JobManager) -> None:
    if jobs.cancel(callback.from_user.id):
        await callback.answer(t(lang, "cancelled"))
    else:
        await callback.answer(t(lang, "nothing_to_cancel"))


@router.callback_query()
async def on_stale(callback: CallbackQuery, lang: str) -> None:
    """Buttons from an old step (or from before a restart)."""
    await callback.answer(t(lang, "session_expired"), show_alert=True)


@router.message()
async def on_other(message: Message, lang: str) -> None:
    await message.answer(t(lang, "menu"), reply_markup=keyboards.main_menu(lang))
