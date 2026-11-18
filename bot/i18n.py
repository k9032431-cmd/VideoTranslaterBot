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
            "• Отправьте видео как видео или как файл — или ссылку на него (YouTube, VK, TikTok…).\n"
            "• Максимальный размер файла: <b>{max_mb} МБ</b>.\n"
            "• Максимальная длительность (мин): <b>{max_min}</b>.\n\n"
            "<b>Форматы перевода</b>\n"
            "📝 <b>Субтитры</b> — перевод вшивается в видео, плюс отдельный файл .srt.\n"
            "🎙 <b>Озвучка</b> — закадровый голос на новом языке, оригинал звучит тише.\n"
            "🎭 <b>Многоголосая озвучка</b> — бот различает говорящих: у каждого свой голос "
            "(мужской или женский, как в оригинале).\n"
            "🎙📝 <b>Озвучка + субтитры</b> — и то и другое.\n\n"
            "Команды: /start, /menu, /language, /cancel"
        ),
        "send_video": "📤 Отправьте видео или ссылку на него: YouTube, VK, TikTok, Rutube, Google Drive и другие сайты.",
        "not_a_video": "⚠️ Это не похоже на видео. Отправьте видеофайл.",
        "too_big": "⚠️ Файл слишком большой ({size_mb} МБ): Telegram даёт боту скачать максимум {max_mb} МБ.\n\n💡 Отправьте вместо файла ссылку на видео — так можно и большие файлы.",
        "too_long": "⚠️ Видео слишком длинное ({minutes} мин). Максимум — {max_min} мин.",
        "video_received": "✅ Видео получено: <b>{name}</b>{duration}",
        "choose_source": "🗣 На каком языке сейчас говорят в видео?",
        "choose_target": "🌍 На какой язык перевести?",
        "choose_mode": "🎞 Как оформить перевод?",
        "mode_subtitles": "📝 Субтитры",
        "mode_voice": "🎙 Озвучка (один голос)",
        "mode_multi": "🎭 Многоголосая озвучка",
        "mode_both": "🎙📝 Озвучка + субтитры",
        "mode_multi_both": "🎭📝 Многоголосая + субтитры",
        "summary": (
            "📋 <b>Проверьте, всё ли верно:</b>\n\n"
            "🎬 Видео: <b>{name}</b>\n"
            "🗣 Язык видео: <b>{source}</b>\n"
            "🌍 Перевести на: <b>{target}</b>\n"
            "🎞 Формат: <b>{mode}</b>\n"
            "📺 Качество: <b>{quality}</b>"
        ),
        "choose_quality": (
            "📺 В каком качестве сделать видео?\n\n"
            "Чем ниже качество, тем меньше файл и быстрее обработка. Больше, чем в оригинале, не будет."
        ),
        "quality_360": "360p — самый лёгкий",
        "quality_480": "480p",
        "quality_720": "720p HD ⭐",
        "quality_1080": "1080p Full HD",
        "quality_orig": "🎬 Как в оригинале",
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
        "stage_speakers": "🎭 Различаю голоса… {progress}",
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
        "checking_link": "🔎 Проверяю ссылку…",
        "link_bot_check": (
            "⚠️ YouTube не пускает сервер без входа в аккаунт («подтвердите, что вы не бот»).\n\n"
            "Администратор может добавить файл cookies YouTube командой /cookies. Другие сайты работают и без этого."
        ),
        "link_unsupported": "⚠️ С этого сайта скачать видео не получается. Пришлите другую ссылку или сам файл.",
        "link_private": "⚠️ Видео закрытое или с ограничением по возрасту — его нельзя скачать без входа в аккаунт.",
        "link_unavailable": "⚠️ Видео не найдено или удалено. Проверьте ссылку.",
        "link_failed": "⚠️ Не удалось скачать видео по ссылке. Попробуйте ещё раз или пришлите файл.",
        "link_drive_private": (
            "⚠️ Google Drive не отдаёт файл. Откройте доступ: в Google Drive нажмите на файл → "
            "<b>Поделиться</b> → «Общий доступ» → <b>Все, у кого есть ссылка</b>, и пришлите ссылку ещё раз.\n\n"
            "Если доступ уже открыт, у файла мог закончиться дневной лимит скачиваний Google — попробуйте позже."
        ),
        "link_drive_folder": "⚠️ Это ссылка на папку. Пришлите ссылку на сам видеофайл (нажмите на файл → Поделиться → Копировать ссылку).",
        "link_not_video": "⚠️ По ссылке не видеофайл. Пришлите ссылку на видео.",
        "link_playlist": "⚠️ Это плейлист. Пришлите ссылку на одно видео.",
        "link_live": "⚠️ Это прямая трансляция — её нельзя перевести, пока она идёт.",
        "link_too_big": "⚠️ Видео по ссылке больше {max_mb} МБ — это слишком много.",
        "download_link": (
            "📦 Готовое видео весит {size_mb} МБ — Telegram не даёт ботам отправлять такие файлы.\n\n"
            "⬇️ <a href=\"{url}\">Скачать видео</a>\n\n"
            "⏳ Ссылка работает {hours} ч, потом файл автоматически удалится с сервера."
        ),
        "cookies_prompt": (
            "🍪 <b>Cookies YouTube</b> ({status})\n\n"
            "YouTube часто не отдаёт видео серверам без входа в аккаунт. Чтобы это обойти:\n"
            "1. Войдите в YouTube в браузере на компьютере — лучше <b>запасным</b> аккаунтом Google.\n"
            "2. Установите расширение «Get cookies.txt LOCALLY» (Chrome/Firefox).\n"
            "3. Откройте youtube.com, нажмите расширение → <b>Export</b>.\n"
            "4. Пришлите сюда полученный файл <code>cookies.txt</code>.\n\n"
            "Удалить: <code>/cookies delete</code>"
        ),
        "cookies_on": "сейчас добавлены",
        "cookies_off": "сейчас нет",
        "cookies_saved": "✅ Cookies сохранены, файл удалён из чата. Пробуйте ссылку YouTube.",
        "cookies_invalid": "⚠️ Это не похоже на cookies.txt с YouTube. Экспортируйте его на открытой странице youtube.com.",
        "cookies_deleted": "🗑 Cookies удалены.",
        "admin_only": (
            "🔒 Эта команда только для администратора бота.\n\n"
            "Ваш Telegram id: <code>{user_id}</code>\n"
            "Чтобы стать администратором, выполните на сервере <code>vtbot config</code> и впишите этот id."
        ),
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
            "• Send the video as a video or a file — or a link to it (YouTube, VK, TikTok…).\n"
            "• Maximum file size: <b>{max_mb} MB</b>.\n"
            "• Maximum length (min): <b>{max_min}</b>.\n\n"
            "<b>Translation formats</b>\n"
            "📝 <b>Subtitles</b> — burned into the video, plus a separate .srt file.\n"
            "🎙 <b>Voice-over</b> — a voice in the new language, the original plays quieter.\n"
            "🎭 <b>Multi-voice voice-over</b> — the bot tells speakers apart and gives each "
            "their own voice (male or female, as in the original).\n"
            "🎙📝 <b>Voice-over + subtitles</b> — both.\n\n"
            "Commands: /start, /menu, /language, /cancel"
        ),
        "send_video": "📤 Send a video or a link to it: YouTube, VK, TikTok, Vimeo, Google Drive and other sites.",
        "not_a_video": "⚠️ That doesn't look like a video. Please send a video file.",
        "too_big": "⚠️ The file is too large ({size_mb} MB): Telegram lets bots download at most {max_mb} MB.\n\n💡 Send a link to the video instead — that works for big files too.",
        "too_long": "⚠️ The video is too long ({minutes} min). The limit is {max_min} min.",
        "video_received": "✅ Video received: <b>{name}</b>{duration}",
        "choose_source": "🗣 What language is spoken in the video?",
        "choose_target": "🌍 Which language should it be translated into?",
        "choose_mode": "🎞 How should the translation be delivered?",
        "mode_subtitles": "📝 Subtitles",
        "mode_voice": "🎙 Voice-over (one voice)",
        "mode_multi": "🎭 Multi-voice voice-over",
        "mode_both": "🎙📝 Voice-over + subtitles",
        "mode_multi_both": "🎭📝 Multi-voice + subtitles",
        "summary": (
            "📋 <b>Please check everything:</b>\n\n"
            "🎬 Video: <b>{name}</b>\n"
            "🗣 Video language: <b>{source}</b>\n"
            "🌍 Translate into: <b>{target}</b>\n"
            "🎞 Format: <b>{mode}</b>\n"
            "📺 Quality: <b>{quality}</b>"
        ),
        "choose_quality": (
            "📺 What quality should the video be?\n\n"
            "Lower quality means a smaller file and faster processing. It never gets better than the original."
        ),
        "quality_360": "360p — smallest",
        "quality_480": "480p",
        "quality_720": "720p HD ⭐",
        "quality_1080": "1080p Full HD",
        "quality_orig": "🎬 As in the original",
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
        "stage_speakers": "🎭 Telling voices apart… {progress}",
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
        "checking_link": "🔎 Checking the link…",
        "link_bot_check": (
            "⚠️ YouTube refuses this server without a signed-in account (\"confirm you're not a bot\").\n\n"
            "The admin can add YouTube cookies with /cookies. Other sites work without it."
        ),
        "link_unsupported": "⚠️ Videos can't be downloaded from this site. Send another link or the file itself.",
        "link_private": "⚠️ The video is private or age-restricted — it can't be downloaded without signing in.",
        "link_unavailable": "⚠️ The video was not found or has been removed. Check the link.",
        "link_failed": "⚠️ Couldn't download the video from the link. Try again or send the file.",
        "link_drive_private": (
            "⚠️ Google Drive won't hand out the file. Share it: in Google Drive click the file → "
            "<b>Share</b> → \"General access\" → <b>Anyone with the link</b>, then send the link again.\n\n"
            "If it's already shared, the file may have hit Google's daily download limit — try again later."
        ),
        "link_drive_folder": "⚠️ That's a folder link. Send a link to the video file itself (click the file → Share → Copy link).",
        "link_not_video": "⚠️ The link doesn't point to a video file. Send a link to a video.",
        "link_playlist": "⚠️ That's a playlist. Send a link to a single video.",
        "link_live": "⚠️ That's a live stream — it can't be translated while it's live.",
        "link_too_big": "⚠️ The linked video is larger than {max_mb} MB — that's too much.",
        "download_link": (
            "📦 The finished video is {size_mb} MB — Telegram doesn't let bots send files that big.\n\n"
            "⬇️ <a href=\"{url}\">Download the video</a>\n\n"
            "⏳ The link works for {hours} h, then the file is deleted from the server automatically."
        ),
        "cookies_prompt": (
            "🍪 <b>YouTube cookies</b> ({status})\n\n"
            "YouTube often refuses to serve videos to servers without a signed-in account. To get around it:\n"
            "1. Sign in to YouTube in a desktop browser — preferably with a <b>spare</b> Google account.\n"
            "2. Install the \"Get cookies.txt LOCALLY\" extension (Chrome/Firefox).\n"
            "3. Open youtube.com, click the extension → <b>Export</b>.\n"
            "4. Send the resulting <code>cookies.txt</code> file here.\n\n"
            "Remove: <code>/cookies delete</code>"
        ),
        "cookies_on": "currently added",
        "cookies_off": "none yet",
        "cookies_saved": "✅ Cookies saved and the file removed from the chat. Try a YouTube link.",
        "cookies_invalid": "⚠️ That doesn't look like a YouTube cookies.txt. Export it on an open youtube.com page.",
        "cookies_deleted": "🗑 Cookies removed.",
        "admin_only": (
            "🔒 This command is for the bot's admin only.\n\n"
            "Your Telegram id: <code>{user_id}</code>\n"
            "To become the admin, run <code>vtbot config</code> on the server and enter this id."
        ),
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
            "• Надішліть відео як відео або як файл — або посилання на нього (YouTube, TikTok…).\n"
            "• Максимальний розмір файлу: <b>{max_mb} МБ</b>.\n"
            "• Максимальна тривалість (хв): <b>{max_min}</b>.\n\n"
            "<b>Формати перекладу</b>\n"
            "📝 <b>Субтитри</b> — переклад вшивається у відео, плюс окремий файл .srt.\n"
            "🎙 <b>Озвучення</b> — закадровий голос новою мовою, оригінал звучить тихіше.\n"
            "🎭 <b>Багатоголосе озвучення</b> — бот розрізняє мовців: у кожного свій голос "
            "(чоловічий або жіночий, як в оригіналі).\n"
            "🎙📝 <b>Озвучення + субтитри</b> — і те, і інше.\n\n"
            "Команди: /start, /menu, /language, /cancel"
        ),
        "send_video": "📤 Надішліть відео або посилання на нього: YouTube, TikTok, Vimeo, Google Drive та інші сайти.",
        "not_a_video": "⚠️ Це не схоже на відео. Надішліть відеофайл.",
        "too_big": "⚠️ Файл завеликий ({size_mb} МБ): Telegram дозволяє боту завантажити максимум {max_mb} МБ.\n\n💡 Надішліть замість файлу посилання на відео — так можна й великі файли.",
        "too_long": "⚠️ Відео задовге ({minutes} хв). Максимум — {max_min} хв.",
        "video_received": "✅ Відео отримано: <b>{name}</b>{duration}",
        "choose_source": "🗣 Якою мовою зараз говорять у відео?",
        "choose_target": "🌍 Якою мовою перекласти?",
        "choose_mode": "🎞 Як оформити переклад?",
        "mode_subtitles": "📝 Субтитри",
        "mode_voice": "🎙 Озвучення (один голос)",
        "mode_multi": "🎭 Багатоголосе озвучення",
        "mode_both": "🎙📝 Озвучення + субтитри",
        "mode_multi_both": "🎭📝 Багатоголосе + субтитри",
        "summary": (
            "📋 <b>Перевірте, чи все правильно:</b>\n\n"
            "🎬 Відео: <b>{name}</b>\n"
            "🗣 Мова відео: <b>{source}</b>\n"
            "🌍 Перекласти на: <b>{target}</b>\n"
            "🎞 Формат: <b>{mode}</b>\n"
            "📺 Якість: <b>{quality}</b>"
        ),
        "choose_quality": (
            "📺 У якій якості зробити відео?\n\n"
            "Чим нижча якість, тим менший файл і швидша обробка. Кращою за оригінал не буде."
        ),
        "quality_360": "360p — найлегше",
        "quality_480": "480p",
        "quality_720": "720p HD ⭐",
        "quality_1080": "1080p Full HD",
        "quality_orig": "🎬 Як в оригіналі",
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
        "stage_speakers": "🎭 Розрізняю голоси… {progress}",
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
        "checking_link": "🔎 Перевіряю посилання…",
        "link_bot_check": (
            "⚠️ YouTube не пускає сервер без входу в акаунт («підтвердіть, що ви не бот»).\n\n"
            "Адміністратор може додати cookies YouTube командою /cookies. Інші сайти працюють і без цього."
        ),
        "link_unsupported": "⚠️ З цього сайту завантажити відео не вдається. Надішліть інше посилання або сам файл.",
        "link_private": "⚠️ Відео закрите або з віковим обмеженням — його не завантажити без входу в акаунт.",
        "link_unavailable": "⚠️ Відео не знайдено або видалено. Перевірте посилання.",
        "link_failed": "⚠️ Не вдалося завантажити відео за посиланням. Спробуйте ще раз або надішліть файл.",
        "link_drive_private": (
            "⚠️ Google Drive не віддає файл. Відкрийте доступ: у Google Drive натисніть на файл → "
            "<b>Поділитися</b> → «Загальний доступ» → <b>Усі, хто має посилання</b>, і надішліть посилання ще раз.\n\n"
            "Якщо доступ уже відкрито, у файлу міг закінчитися денний ліміт завантажень Google — спробуйте пізніше."
        ),
        "link_drive_folder": "⚠️ Це посилання на папку. Надішліть посилання на сам відеофайл (натисніть на файл → Поділитися → Копіювати посилання).",
        "link_not_video": "⚠️ За посиланням не відеофайл. Надішліть посилання на відео.",
        "link_playlist": "⚠️ Це плейлист. Надішліть посилання на одне відео.",
        "link_live": "⚠️ Це пряма трансляція — її не можна перекласти, поки вона триває.",
        "link_too_big": "⚠️ Відео за посиланням більше {max_mb} МБ — це забагато.",
        "download_link": (
            "📦 Готове відео важить {size_mb} МБ — Telegram не дозволяє ботам надсилати такі файли.\n\n"
            "⬇️ <a href=\"{url}\">Завантажити відео</a>\n\n"
            "⏳ Посилання працює {hours} год, потім файл автоматично видалиться з сервера."
        ),
        "cookies_prompt": (
            "🍪 <b>Cookies YouTube</b> ({status})\n\n"
            "YouTube часто не віддає відео серверам без входу в акаунт. Щоб це обійти:\n"
            "1. Увійдіть у YouTube у браузері на комп'ютері — краще <b>запасним</b> акаунтом Google.\n"
            "2. Встановіть розширення «Get cookies.txt LOCALLY» (Chrome/Firefox).\n"
            "3. Відкрийте youtube.com, натисніть розширення → <b>Export</b>.\n"
            "4. Надішліть сюди отриманий файл <code>cookies.txt</code>.\n\n"
            "Видалити: <code>/cookies delete</code>"
        ),
        "cookies_on": "зараз додані",
        "cookies_off": "зараз немає",
        "cookies_saved": "✅ Cookies збережено, файл видалено з чату. Пробуйте посилання YouTube.",
        "cookies_invalid": "⚠️ Це не схоже на cookies.txt з YouTube. Експортуйте його на відкритій сторінці youtube.com.",
        "cookies_deleted": "🗑 Cookies видалено.",
        "admin_only": (
            "🔒 Ця команда тільки для адміністратора бота.\n\n"
            "Ваш Telegram id: <code>{user_id}</code>\n"
            "Щоб стати адміністратором, виконайте на сервері <code>vtbot config</code> і впишіть цей id."
        ),
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
