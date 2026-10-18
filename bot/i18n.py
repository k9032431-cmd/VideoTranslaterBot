"""Interface texts. Every key must exist in every language (checked by tests)."""

UI_LANGUAGES: dict[str, str] = {
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "uk": "🇺🇦 Українська",
}
DEFAULT_UI_LANGUAGE = "ru"

TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        "choose_ui_language": "🌐 Выберите язык бота:",
        "ui_language_set": "✅ Язык бота: русский",
        "welcome": (
            "👋 Привет! Я перевожу видео и фильмы на другой язык.\n\n"
            "Как это работает:\n"
            "1️⃣ Нажмите «🎬 Перевести видео»\n"
            "2️⃣ Отправьте видео\n"
            "3️⃣ Выберите язык видео и язык перевода\n"
            "4️⃣ Выберите формат: субтитры или озвучка\n\n"
            "Остальное я сделаю сам 🙂"
        ),
        "menu": "📋 Главное меню",
        "btn_translate": "🎬 Перевести видео",
        "btn_language": "🌐 Язык бота",
        "btn_help": "ℹ️ Помощь",
        "btn_cancel": "❌ Отмена",
        "btn_back": "⬅️ Назад",
        "btn_start": "✅ Начать перевод",
        "btn_auto": "🤖 Определить автоматически",
        "help": (
            "ℹ️ <b>Помощь</b>\n\n"
            "• Отправьте видео как видео или как файл.\n"
            "• Максимальный размер файла: <b>{max_mb} МБ</b>.\n"
            "• Максимальная длительность: <b>{max_min} мин</b>.\n\n"
            "<b>Форматы перевода</b>\n"
            "📝 <b>Субтитры</b> — перевод вшивается в видео, плюс отдельный файл .srt.\n"
            "🎙 <b>Озвучка</b> — закадровый голос на новом языке, оригинал звучит тише.\n"
            "🎙📝 <b>Озвучка + субтитры</b> — и то и другое.\n\n"
            "Команды: /start, /menu, /language, /cancel"
        ),
        "send_video": "📤 Отправьте видео, которое нужно перевести.",
        "not_a_video": "⚠️ Это не похоже на видео. Отправьте видеофайл.",
        "too_big": "⚠️ Файл слишком большой ({size_mb} МБ). Максимум — {max_mb} МБ.",
        "too_long": "⚠️ Видео слишком длинное ({minutes} мин). Максимум — {max_min} мин.",
        "video_received": "✅ Видео получено: <b>{name}</b>{duration}",
        "choose_source": "🗣 На каком языке сейчас говорят в видео?",
        "choose_target": "🌍 На какой язык перевести?",
        "choose_mode": "🎞 Как оформить перевод?",
        "mode_subtitles": "📝 Субтитры",
        "mode_voice": "🎙 Озвучка",
        "mode_both": "🎙📝 Озвучка + субтитры",
        "summary": (
            "📋 <b>Проверьте, всё ли верно:</b>\n\n"
            "🎬 Видео: <b>{name}</b>\n"
            "🗣 Язык видео: <b>{source}</b>\n"
            "🌍 Перевести на: <b>{target}</b>\n"
            "🎞 Формат: <b>{mode}</b>"
        ),
        "auto_detect": "автоопределение",
        "cancelled": "❌ Отменено.",
        "nothing_to_cancel": "Сейчас нечего отменять.",
        "busy": "⏳ У вас уже идёт перевод. Дождитесь окончания или отмените его.",
        "queued": "⏳ Вы в очереди, перевод начнётся, как только освободится место…",
        "access_denied": "⛔ У вас нет доступа к этому боту.",
        "session_expired": "⚠️ Сессия устарела. Нажмите «🎬 Перевести видео» и начните заново.",
        "stage_download": "📥 Скачиваю видео…",
        "stage_audio": "🎧 Извлекаю звук…",
        "stage_transcribe": "📝 Распознаю речь… {progress}",
        "stage_translate": "🌍 Перевожу… {progress}",
        "stage_tts": "🎙 Озвучиваю… {progress}",
        "stage_render": "🎞 Собираю видео… {progress}",
        "stage_upload": "📤 Отправляю результат…",
        "processing_header": "⚙️ <b>Перевод: {source} → {target}</b>\n\n",
        "done": "✅ Готово! Перевод: {source} → {target}",
        "srt_caption": "📝 Субтитры ({target})",
        "result_too_big": (
            "⚠️ Готовое видео весит {size_mb} МБ, а Telegram позволяет боту отправлять "
            "не больше {max_mb} МБ. Отправляю то, что помещается."
        ),
        "audio_caption": "🎙 Дорожка озвучки ({target}) — её можно наложить на видео в любом плеере.",
        "no_speech": "🤷 В видео не найдено речи — переводить нечего.",
        "same_language": "⚠️ Речь в видео уже на языке {target}. Выберите другой язык перевода.",
        "error": "❌ Не получилось перевести видео: {error}\n\nПопробуйте ещё раз чуть позже.",
        "error_generic": "внутренняя ошибка",
        "rate_limited": (
            "⏳ Закончился лимит API: дневной лимит бесплатного тарифа или баланс OpenAI.\n\n"
            "Попробуйте позже — бесплатный лимит обновляется каждый день."
        ),
        "bad_api_key": "ключ API не подходит — владельцу бота нужно выполнить vtbot config",
        "unsupported_language": "⚠️ Не удалось определить язык видео. Выберите его вручную из списка.",
        "btn_update": "🔄 Обновить бота",
        "btn_update_yes": "✅ Обновить",
        "update_confirm": (
            "🔄 Обновить бота до последней версии?\n\n"
            "Сейчас установлена: <code>{version}</code>\n\n"
            "Бот перезапустится на минуту, идущие переводы прервутся."
        ),
        "update_started": "⏳ Обновляю… Это займёт 1–5 минут, я напишу, когда закончу.",
        "update_in_progress": "⏳ Обновление уже идёт, дождитесь сообщения о результате.",
        "update_done": "✅ Бот обновлён!\n\nВерсия: <code>{version}</code>",
        "update_latest": "✔ У вас уже последняя версия: <code>{version}</code>",
        "update_failed": (
            "❌ Обновить не получилось — бот продолжает работать на прежней версии.\n\n"
            "Последние строки журнала:\n<pre>{log}</pre>"
        ),
        "update_unavailable": (
            "⚠️ Кнопка обновления заработает после одного обновления вручную. "
            "Выполните на сервере: <code>vtbot update</code>"
        ),
        "update_timeout": "⚠️ Обновление идёт слишком долго. Проверьте на сервере: <code>vtbot status</code>",
    },
    "en": {
        "choose_ui_language": "🌐 Choose the bot language:",
        "ui_language_set": "✅ Bot language: English",
        "welcome": (
            "👋 Hi! I translate videos and movies into another language.\n\n"
            "How it works:\n"
            "1️⃣ Tap “🎬 Translate video”\n"
            "2️⃣ Send a video\n"
            "3️⃣ Choose the video language and the target language\n"
            "4️⃣ Choose a format: subtitles or voice-over\n\n"
            "I'll take care of the rest 🙂"
        ),
        "menu": "📋 Main menu",
        "btn_translate": "🎬 Translate video",
        "btn_language": "🌐 Bot language",
        "btn_help": "ℹ️ Help",
        "btn_cancel": "❌ Cancel",
        "btn_back": "⬅️ Back",
        "btn_start": "✅ Start translation",
        "btn_auto": "🤖 Detect automatically",
        "help": (
            "ℹ️ <b>Help</b>\n\n"
            "• Send the video as a video or as a file.\n"
            "• Maximum file size: <b>{max_mb} MB</b>.\n"
            "• Maximum length: <b>{max_min} min</b>.\n\n"
            "<b>Translation formats</b>\n"
            "📝 <b>Subtitles</b> — burned into the video, plus a separate .srt file.\n"
            "🎙 <b>Voice-over</b> — a voice in the new language, the original plays quieter.\n"
            "🎙📝 <b>Voice-over + subtitles</b> — both.\n\n"
            "Commands: /start, /menu, /language, /cancel"
        ),
        "send_video": "📤 Send the video you want to translate.",
        "not_a_video": "⚠️ That doesn't look like a video. Please send a video file.",
        "too_big": "⚠️ The file is too large ({size_mb} MB). The limit is {max_mb} MB.",
        "too_long": "⚠️ The video is too long ({minutes} min). The limit is {max_min} min.",
        "video_received": "✅ Video received: <b>{name}</b>{duration}",
        "choose_source": "🗣 What language is spoken in the video?",
        "choose_target": "🌍 Which language should it be translated into?",
        "choose_mode": "🎞 How should the translation be delivered?",
        "mode_subtitles": "📝 Subtitles",
        "mode_voice": "🎙 Voice-over",
        "mode_both": "🎙📝 Voice-over + subtitles",
        "summary": (
            "📋 <b>Please check everything:</b>\n\n"
            "🎬 Video: <b>{name}</b>\n"
            "🗣 Video language: <b>{source}</b>\n"
            "🌍 Translate into: <b>{target}</b>\n"
            "🎞 Format: <b>{mode}</b>"
        ),
        "auto_detect": "auto-detect",
        "cancelled": "❌ Cancelled.",
        "nothing_to_cancel": "There is nothing to cancel.",
        "busy": "⏳ A translation is already running. Wait for it to finish or cancel it.",
        "queued": "⏳ You're in the queue, the translation will start as soon as a slot is free…",
        "access_denied": "⛔ You don't have access to this bot.",
        "session_expired": "⚠️ This session has expired. Tap “🎬 Translate video” to start again.",
        "stage_download": "📥 Downloading the video…",
        "stage_audio": "🎧 Extracting audio…",
        "stage_transcribe": "📝 Recognizing speech… {progress}",
        "stage_translate": "🌍 Translating… {progress}",
        "stage_tts": "🎙 Voicing… {progress}",
        "stage_render": "🎞 Rendering the video… {progress}",
        "stage_upload": "📤 Sending the result…",
        "processing_header": "⚙️ <b>Translation: {source} → {target}</b>\n\n",
        "done": "✅ Done! Translation: {source} → {target}",
        "srt_caption": "📝 Subtitles ({target})",
        "result_too_big": (
            "⚠️ The finished video is {size_mb} MB, but Telegram only lets bots send up to "
            "{max_mb} MB. Sending what fits."
        ),
        "audio_caption": "🎙 Voice-over track ({target}) — you can load it alongside the video in any player.",
        "no_speech": "🤷 No speech was found in the video — nothing to translate.",
        "same_language": "⚠️ The video is already in {target}. Choose a different target language.",
        "error": "❌ Couldn't translate the video: {error}\n\nPlease try again a bit later.",
        "error_generic": "internal error",
        "rate_limited": (
            "⏳ The API limit is used up: the free tier's daily limit or the OpenAI balance.\n\n"
            "Please try again later — the free limit resets every day."
        ),
        "bad_api_key": "the API key was rejected — the bot owner needs to run vtbot config",
        "unsupported_language": "⚠️ Couldn't recognize the video's language. Please pick it from the list.",
        "btn_update": "🔄 Update the bot",
        "btn_update_yes": "✅ Update",
        "update_confirm": (
            "🔄 Update the bot to the latest version?\n\n"
            "Installed now: <code>{version}</code>\n\n"
            "The bot will restart for a minute and running translations will stop."
        ),
        "update_started": "⏳ Updating… This takes 1–5 minutes, I'll message you when it's done.",
        "update_in_progress": "⏳ An update is already running, please wait for the result.",
        "update_done": "✅ The bot has been updated!\n\nVersion: <code>{version}</code>",
        "update_latest": "✔ You already have the latest version: <code>{version}</code>",
        "update_failed": (
            "❌ The update failed — the bot keeps running the previous version.\n\n"
            "Last log lines:\n<pre>{log}</pre>"
        ),
        "update_unavailable": (
            "⚠️ The update button starts working after one manual update. "
            "Run on the server: <code>vtbot update</code>"
        ),
        "update_timeout": "⚠️ The update is taking too long. Check on the server: <code>vtbot status</code>",
    },
    "uk": {
        "choose_ui_language": "🌐 Оберіть мову бота:",
        "ui_language_set": "✅ Мова бота: українська",
        "welcome": (
            "👋 Привіт! Я перекладаю відео та фільми іншою мовою.\n\n"
            "Як це працює:\n"
            "1️⃣ Натисніть «🎬 Перекласти відео»\n"
            "2️⃣ Надішліть відео\n"
            "3️⃣ Оберіть мову відео та мову перекладу\n"
            "4️⃣ Оберіть формат: субтитри або озвучення\n\n"
            "Решту я зроблю сам 🙂"
        ),
        "menu": "📋 Головне меню",
        "btn_translate": "🎬 Перекласти відео",
        "btn_language": "🌐 Мова бота",
        "btn_help": "ℹ️ Допомога",
        "btn_cancel": "❌ Скасувати",
        "btn_back": "⬅️ Назад",
        "btn_start": "✅ Почати переклад",
        "btn_auto": "🤖 Визначити автоматично",
        "help": (
            "ℹ️ <b>Допомога</b>\n\n"
            "• Надішліть відео як відео або як файл.\n"
            "• Максимальний розмір файлу: <b>{max_mb} МБ</b>.\n"
            "• Максимальна тривалість: <b>{max_min} хв</b>.\n\n"
            "<b>Формати перекладу</b>\n"
            "📝 <b>Субтитри</b> — переклад вшивається у відео, плюс окремий файл .srt.\n"
            "🎙 <b>Озвучення</b> — закадровий голос новою мовою, оригінал звучить тихіше.\n"
            "🎙📝 <b>Озвучення + субтитри</b> — і те, і інше.\n\n"
            "Команди: /start, /menu, /language, /cancel"
        ),
        "send_video": "📤 Надішліть відео, яке потрібно перекласти.",
        "not_a_video": "⚠️ Це не схоже на відео. Надішліть відеофайл.",
        "too_big": "⚠️ Файл завеликий ({size_mb} МБ). Максимум — {max_mb} МБ.",
        "too_long": "⚠️ Відео задовге ({minutes} хв). Максимум — {max_min} хв.",
        "video_received": "✅ Відео отримано: <b>{name}</b>{duration}",
        "choose_source": "🗣 Якою мовою зараз говорять у відео?",
        "choose_target": "🌍 Якою мовою перекласти?",
        "choose_mode": "🎞 Як оформити переклад?",
        "mode_subtitles": "📝 Субтитри",
        "mode_voice": "🎙 Озвучення",
        "mode_both": "🎙📝 Озвучення + субтитри",
        "summary": (
            "📋 <b>Перевірте, чи все правильно:</b>\n\n"
            "🎬 Відео: <b>{name}</b>\n"
            "🗣 Мова відео: <b>{source}</b>\n"
            "🌍 Перекласти на: <b>{target}</b>\n"
            "🎞 Формат: <b>{mode}</b>"
        ),
        "auto_detect": "автовизначення",
        "cancelled": "❌ Скасовано.",
        "nothing_to_cancel": "Зараз нічого скасовувати.",
        "busy": "⏳ У вас уже триває переклад. Дочекайтеся завершення або скасуйте його.",
        "queued": "⏳ Ви в черзі, переклад почнеться, щойно звільниться місце…",
        "access_denied": "⛔ У вас немає доступу до цього бота.",
        "session_expired": "⚠️ Сесія застаріла. Натисніть «🎬 Перекласти відео» і почніть знову.",
        "stage_download": "📥 Завантажую відео…",
        "stage_audio": "🎧 Видобуваю звук…",
        "stage_transcribe": "📝 Розпізнаю мовлення… {progress}",
        "stage_translate": "🌍 Перекладаю… {progress}",
        "stage_tts": "🎙 Озвучую… {progress}",
        "stage_render": "🎞 Збираю відео… {progress}",
        "stage_upload": "📤 Надсилаю результат…",
        "processing_header": "⚙️ <b>Переклад: {source} → {target}</b>\n\n",
        "done": "✅ Готово! Переклад: {source} → {target}",
        "srt_caption": "📝 Субтитри ({target})",
        "result_too_big": (
            "⚠️ Готове відео важить {size_mb} МБ, а Telegram дозволяє боту надсилати "
            "не більше {max_mb} МБ. Надсилаю те, що вміщується."
        ),
        "audio_caption": "🎙 Доріжка озвучення ({target}) — її можна накласти на відео в будь-якому плеєрі.",
        "no_speech": "🤷 У відео не знайдено мовлення — перекладати нічого.",
        "same_language": "⚠️ Мовлення у відео вже мовою {target}. Оберіть іншу мову перекладу.",
        "error": "❌ Не вдалося перекласти відео: {error}\n\nСпробуйте ще раз трохи пізніше.",
        "error_generic": "внутрішня помилка",
        "rate_limited": (
            "⏳ Закінчився ліміт API: денний ліміт безкоштовного тарифу або баланс OpenAI.\n\n"
            "Спробуйте пізніше — безкоштовний ліміт оновлюється щодня."
        ),
        "bad_api_key": "ключ API не підходить — власнику бота потрібно виконати vtbot config",
        "unsupported_language": "⚠️ Не вдалося визначити мову відео. Оберіть її вручну зі списку.",
        "btn_update": "🔄 Оновити бота",
        "btn_update_yes": "✅ Оновити",
        "update_confirm": (
            "🔄 Оновити бота до останньої версії?\n\n"
            "Зараз встановлено: <code>{version}</code>\n\n"
            "Бот перезапуститься на хвилину, поточні переклади перервуться."
        ),
        "update_started": "⏳ Оновлюю… Це займе 1–5 хвилин, я напишу, коли закінчу.",
        "update_in_progress": "⏳ Оновлення вже триває, дочекайтеся повідомлення про результат.",
        "update_done": "✅ Бота оновлено!\n\nВерсія: <code>{version}</code>",
        "update_latest": "✔ У вас уже остання версія: <code>{version}</code>",
        "update_failed": (
            "❌ Оновити не вдалося — бот працює на попередній версії.\n\n"
            "Останні рядки журналу:\n<pre>{log}</pre>"
        ),
        "update_unavailable": (
            "⚠️ Кнопка оновлення запрацює після одного оновлення вручну. "
            "Виконайте на сервері: <code>vtbot update</code>"
        ),
        "update_timeout": "⚠️ Оновлення триває надто довго. Перевірте на сервері: <code>vtbot status</code>",
    },
}


def t(lang: str | None, key: str, **kwargs: object) -> str:
    texts = TEXTS.get(lang or DEFAULT_UI_LANGUAGE, TEXTS[DEFAULT_UI_LANGUAGE])
    text = texts[key]
    return text.format(**kwargs) if kwargs else text


def all_variants(key: str) -> set[str]:
    """The text of `key` in every interface language — for matching reply-keyboard buttons."""
    return {texts[key] for texts in TEXTS.values()}
