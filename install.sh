#!/usr/bin/env bash
# VideoTranslaterBot — установка, обновление и управление на VPS (Ubuntu / Debian).
#
# Установка (и повторный запуск = обновление):
#   bash <(curl -fsSL https://raw.githubusercontent.com/k9032431-cmd/VideoTranslaterBot/main/install.sh)
#
# После установки доступна команда `vtbot`:
#   vtbot update | status | logs | restart | stop | start | config | bigfiles | uninstall
#
# Всё тело скрипта — внутри функций, а вызов main стоит в самом конце: bash сначала читает
# весь файл, поэтому `vtbot update` может безопасно заменить этот файл новой версией.

set -Eeuo pipefail

REPO_URL="${VTBOT_REPO:-https://github.com/k9032431-cmd/VideoTranslaterBot.git}"
BRANCH="${VTBOT_BRANCH:-main}"
APP_DIR="${VTBOT_DIR:-/opt/videotranslaterbot}"
SERVICE="vtbot"
APP_USER="vtbot"
CLI="/usr/local/bin/vtbot"
BOT_API_CONTAINER="telegram-bot-api"
BOT_API_DIR="/var/lib/telegram-bot-api"
MIN_PY_MINOR=10
MAX_PY_MINOR=14

# ── вывод ────────────────────────────────────────────────────────────────────────────────────

if [[ -t 1 ]]; then
    C_RED=$'\e[31m' C_GREEN=$'\e[32m' C_YELLOW=$'\e[33m' C_BLUE=$'\e[34m' C_BOLD=$'\e[1m' C_RESET=$'\e[0m'
else
    C_RED="" C_GREEN="" C_YELLOW="" C_BLUE="" C_BOLD="" C_RESET=""
fi

step() { printf '\n%s==>%s %s%s%s\n' "$C_BLUE" "$C_RESET" "$C_BOLD" "$*" "$C_RESET"; }
ok()   { printf '%s✔%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '%s!%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
die()  { printf '%s✘ %s%s\n' "$C_RED" "$*" "$C_RESET" >&2; exit 1; }

# Читаем ответы с терминала, даже если скрипт пришёл через `curl | bash`.
ask() {
    local prompt="$1" default="${2:-}" answer=""
    if [[ -n "$default" ]]; then prompt="$prompt [$default]"; fi
    # Вопрос печатаем прямо в терминал: `read -p` пишет его в stderr, а stderr здесь заглушён
    # (иначе без терминала сыплются ошибки /dev/tty).
    if [[ -r /dev/tty ]]; then
        { printf '%s: ' "$prompt" >/dev/tty && read -r answer </dev/tty; } 2>/dev/null || true
    fi
    printf '%s' "${answer:-$default}"
}

ask_secret() {
    local prompt="$1" answer=""
    if [[ -r /dev/tty ]]; then
        { printf '%s: ' "$prompt" >/dev/tty && read -r -s answer </dev/tty && echo >/dev/tty; } 2>/dev/null || true
    fi
    printf '%s' "$answer"
}

confirm() {
    local answer
    answer="$(ask "$1 (y/n)" "${2:-n}")"
    [[ "$answer" =~ ^[YyДд] ]]
}

mask() {
    local value="$1"
    if (( ${#value} <= 8 )); then printf '***'; else printf '%s…%s' "${value:0:4}" "${value: -4}"; fi
}

# ── .env ─────────────────────────────────────────────────────────────────────────────────────

ENV_FILE() { printf '%s/.env' "$APP_DIR"; }

env_get() {
    local file; file="$(ENV_FILE)"
    [[ -f "$file" ]] || return 0
    awk -F= -v key="$1" '$1 == key { sub(/^[^=]*=/, ""); value = $0 } END { printf "%s", value }' "$file"
}

env_set() {
    local key="$1" value="$2" file tmp
    file="$(ENV_FILE)"
    touch "$file"
    tmp="$(mktemp)"
    KEY="$key" VALUE="$value" awk -F= '
        BEGIN { key = ENVIRON["KEY"]; value = ENVIRON["VALUE"] }
        $1 == key || $1 == "# " key { if (!done) print key "=" value; done = 1; next }
        { print }
        END { if (!done) print key "=" value }
    ' "$file" >"$tmp"
    cat "$tmp" >"$file"
    rm -f "$tmp"
}

# Добавляет в .env настройки, которые появились в новой версии (из .env.example), не трогая старые.
env_merge_new_keys() {
    local example="$APP_DIR/.env.example" file line key added=0
    file="$(ENV_FILE)"
    [[ -f "$example" && -f "$file" ]] || return 0
    while IFS= read -r line; do
        [[ "$line" =~ ^([A-Z_][A-Z0-9_]*)= ]] || continue
        key="${BASH_REMATCH[1]}"
        if ! grep -qE "^#? ?${key}=" "$file"; then
            printf '%s\n' "$line" >>"$file"
            added=$((added + 1))
        fi
    done <"$example"
    if (( added > 0 )); then ok "Добавлено новых настроек в .env: $added"; fi
}

secure_env() {
    chown root:"$APP_USER" "$(ENV_FILE)"
    chmod 640 "$(ENV_FILE)"
}

# ── проверки ─────────────────────────────────────────────────────────────────────────────────

require_root() {
    [[ $EUID -eq 0 ]] && return 0
    # Перезапуск через sudo возможен, только если скрипт — настоящий файл (а не `bash <(curl …)`).
    if [[ -f "$0" ]] && command -v sudo >/dev/null; then
        exec sudo -E bash "$0" "${ORIGINAL_ARGS[@]}"
    fi
    die "Нужны права root. Выполните сначала: sudo -i"
}

require_installed() {
    [[ -d "$APP_DIR/.git" ]] || die "Бот не установлен. Установите: bash <(curl -fsSL https://raw.githubusercontent.com/k9032431-cmd/VideoTranslaterBot/main/install.sh)"
}

has_systemd() { [[ -d /run/systemd/system ]]; }

check_os() {
    command -v apt-get >/dev/null || die "Поддерживаются только Ubuntu и Debian (нужен apt)."
}

check_python() {
    local version minor
    version="$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
    minor="${version#3.}"
    if (( minor < MIN_PY_MINOR || minor > MAX_PY_MINOR )); then
        die "Нужен Python 3.${MIN_PY_MINOR}–3.${MAX_PY_MINOR}, а в системе $version. Используйте Ubuntu 22.04/24.04 или Debian 12."
    fi
    ok "Python $version"
}

check_bot_token() {
    [[ "${VTBOT_SKIP_CHECKS:-0}" == 1 ]] && return 0
    local response
    response="$(curl -fsS --max-time 15 "https://api.telegram.org/bot$1/getMe" 2>/dev/null || true)"
    if [[ "$response" == *'"ok":true'* ]]; then
        local username="${response#*\"username\":\"}"
        ok "Токен верный: @${username%%\"*}"
        return 0
    fi
    return 1
}

check_api_key() {  # $1 = base url, $2 = key
    [[ "${VTBOT_SKIP_CHECKS:-0}" == 1 ]] && return 0
    local code
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
        -H "Authorization: Bearer $2" "$1/models" 2>/dev/null || true)"
    [[ "$code" == 200 ]]
}

check_groq_key()   { check_api_key "https://api.groq.com/openai/v1" "$1" && ok "Ключ Groq верный"; }
check_openai_key() { check_api_key "${OPENAI_BASE_URL:-https://api.openai.com/v1}" "$1" && ok "Ключ OpenAI верный"; }

# ── шаги установки ───────────────────────────────────────────────────────────────────────────

install_packages() {
    step "Устанавливаю системные пакеты (ffmpeg, python, шрифты)…"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends \
        git curl ca-certificates acl python3 python3-venv python3-pip ffmpeg \
        fonts-dejavu-core fonts-noto-core fonts-noto-cjk >/dev/null
    ok "Пакеты установлены"
}

create_user() {
    if ! id "$APP_USER" >/dev/null 2>&1; then
        useradd --system --home-dir "$APP_DIR/data" --shell /usr/sbin/nologin "$APP_USER"
        ok "Создан системный пользователь $APP_USER"
    fi
}

fetch_code() {
    step "Скачиваю бота…"
    if [[ -d "$APP_DIR/.git" ]]; then
        git -C "$APP_DIR" fetch --quiet origin "$BRANCH"
        git -C "$APP_DIR" reset --quiet --hard "origin/$BRANCH"
    else
        mkdir -p "$(dirname "$APP_DIR")"
        git clone --quiet --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
    fi
    ok "Версия: $(version_string)"
}

version_string() {
    git -C "$APP_DIR" log -1 --format='%h от %cd — %s' --date=format:'%d.%m.%Y %H:%M'
}

install_python_deps() {
    step "Устанавливаю Python-зависимости…"
    # Каждая команда проверяется явно: при вызове из `if` bash не останавливается на ошибках сам.
    if [[ ! -x "$APP_DIR/venv/bin/python" ]]; then
        python3 -m venv "$APP_DIR/venv" || return 1
    fi
    "$APP_DIR/venv/bin/pip" install --quiet --upgrade pip || return 1
    "$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt" || return 1
    ok "Зависимости установлены"
}

smoke_test() {
    (cd "$APP_DIR" && "$APP_DIR/venv/bin/python" -c "import bot.__main__") >/dev/null
}

prepare_dirs() {
    mkdir -p "$APP_DIR/data"
    chown -R "$APP_USER:$APP_USER" "$APP_DIR/data"
}

provider_key_name() {
    if [[ "$1" == openai ]]; then echo OPENAI_API_KEY; else echo GROQ_API_KEY; fi
}

# Нужна ли первичная настройка: нет токена или нет ключа для выбранного режима.
config_complete() {
    [[ -f "$(ENV_FILE)" ]] || return 1
    local provider
    provider="$(env_get PROVIDER)"
    [[ -n "$(env_get BOT_TOKEN)" ]] || return 1
    [[ "$provider" == local ]] && return 0
    [[ -n "$provider" && -n "$(env_get "$(provider_key_name "$provider")")" ]]
}

# Спрашивает секрет, пока проверка не пройдёт. $1 — имя в .env, $2 — подсказка, $3 — функция проверки.
ask_key() {
    local name="$1" prompt="$2" check="$3" reask="$4" current value
    current="$(env_get "$name")"
    value="${!name:-}"
    if [[ -n "$value" ]]; then
        "$check" "$value" || die "Ключ $name не принят."
    elif [[ -z "$current" || "$reask" == 1 ]]; then
        while true; do
            if [[ -n "$current" ]]; then
                value="$(ask_secret "$prompt (Enter — оставить $(mask "$current"))")"
                value="${value:-$current}"
            else
                value="$(ask_secret "$prompt")"
            fi
            [[ -n "$value" ]] || { warn "Это поле обязательно."; [[ -r /dev/tty ]] || die "Не задан $name."; continue; }
            "$check" "$value" && break
            warn "Ключ не принят. Проверьте, что скопировали его целиком, и введите ещё раз."
            [[ -r /dev/tty ]] || die "Неверный $name."
        done
    fi
    if [[ -n "$value" ]]; then env_set "$name" "$value"; fi
}

configure() {
    local reconfigure="${1:-0}" first=0 token ids current provider choice
    step "Настройка"
    if [[ ! -f "$(ENV_FILE)" ]]; then
        cp "$APP_DIR/.env.example" "$(ENV_FILE)"
    fi
    config_complete || first=1
    local ask_all=$(( first || reconfigure ))

    # Токен бота
    current="$(env_get BOT_TOKEN)"
    token="${BOT_TOKEN:-}"
    if [[ -z "$token" && ( -z "$current" || "$reconfigure" == 1 ) ]]; then
        while true; do
            if [[ -n "$current" ]]; then
                token="$(ask "Токен бота от @BotFather (Enter — оставить $(mask "$current"))")"
                token="${token:-$current}"
            else
                token="$(ask "Токен бота от @BotFather")"
            fi
            [[ -n "$token" ]] || { warn "Токен обязателен."; [[ -r /dev/tty ]] || die "Не задан BOT_TOKEN."; continue; }
            check_bot_token "$token" && break
            warn "Telegram не принял этот токен. Проверьте и введите ещё раз."
            [[ -r /dev/tty ]] || die "Неверный BOT_TOKEN."
        done
    elif [[ -n "$token" ]]; then
        check_bot_token "$token" || die "Telegram не принял BOT_TOKEN."
    fi
    if [[ -n "$token" ]]; then env_set BOT_TOKEN "$token"; fi

    # Режим работы
    provider="${PROVIDER:-}"
    current="$(env_get PROVIDER)"
    if [[ -z "$provider" ]]; then
        if (( ask_all )); then
            local default=1
            [[ "$current" == free && -n "$(env_get GROQ_API_KEY)" ]] && default=2
            [[ "$current" == openai ]] && default=3
            echo
            echo "Режим работы:"
            echo "  1) На сервере — бесплатно, без регистраций и лимитов. Медленнее: фильм ~1.5–3 часа."
            echo "  2) Groq — бесплатно, быстро, нужен ключ Groq. Лимит ~8 ч видео в сутки."
            echo "  3) OpenAI — платно (~\$0.6 за фильм с субтитрами, ~\$2 с озвучкой), лучший перевод."
            choice="$(ask "Выберите 1, 2 или 3" "$default")"
            case "$choice" in
                2) provider=free ;;
                3) provider=openai ;;
                *) provider=local ;;
            esac
        else
            provider="${current:-local}"
        fi
    fi
    [[ "$provider" =~ ^(local|free|openai)$ ]] || die "PROVIDER должен быть local, free или openai."
    env_set PROVIDER "$provider"

    if [[ "$provider" == local ]]; then
        configure_local_models "$ask_all"
    elif [[ "$provider" == free ]]; then
        if (( ask_all )) && [[ -z "${GROQ_API_KEY:-}" && -z "$(env_get GROQ_API_KEY)" ]]; then
            echo "Бесплатный ключ Groq: https://console.groq.com/keys → Create API Key (начинается с gsk_)."
        fi
        ask_key GROQ_API_KEY "Ключ Groq" check_groq_key "$reconfigure"
    else
        ask_key OPENAI_API_KEY "Ключ OpenAI (https://platform.openai.com/api-keys)" check_openai_key "$reconfigure"
    fi

    # Кому разрешено пользоваться
    current="$(env_get ALLOWED_USER_IDS)"
    if [[ -n "${ALLOWED_USER_IDS+set}" ]]; then
        ids="$ALLOWED_USER_IDS"
    elif (( ask_all )); then
        echo
        echo "Лучше разрешить бота только себе, чтобы чужие не тратили ваши лимиты."
        echo "Свой Telegram id можно узнать у @userinfobot. Несколько id — через запятую."
        ids="$(ask "Telegram id, кому разрешён бот (Enter — всем)" "$current")"
    else
        ids="$current"
    fi
    ids="${ids// /}"
    [[ -z "$ids" || "$ids" =~ ^[0-9]+(,[0-9]+)*$ ]] || die "ALLOWED_USER_IDS: только числа через запятую."
    env_set ALLOWED_USER_IDS "$ids"

    secure_env
    config_complete || die "Настройка не завершена: нет токена бота или ключа."
    ok "Настройки сохранены в $(ENV_FILE)"
}

write_service() {
    has_systemd || { warn "systemd не найден — автозапуск не настроен. Запуск вручную: cd $APP_DIR && venv/bin/python -m bot"; return 0; }
    cat >"/etc/systemd/system/$SERVICE.service" <<EOF
[Unit]
Description=VideoTranslaterBot (Telegram video translator)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=DATA_DIR=$APP_DIR/data
Environment=PYTHONUNBUFFERED=1
Environment=HOME=$APP_DIR/data
Environment=HF_HUB_DISABLE_TELEMETRY=1
ExecStart=$APP_DIR/venv/bin/python -m bot
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --quiet "$SERVICE"
}

install_cli() {
    chmod +x "$APP_DIR/install.sh"
    ln -sf "$APP_DIR/install.sh" "$CLI"
}

# Запускает сервис и убеждается, что он не упал сразу после старта.
start_and_verify() {
    has_systemd || return 0
    systemctl restart "$SERVICE" || return 1
    sleep 8
    if systemctl is-active --quiet "$SERVICE"; then
        ok "Бот запущен"
        return 0
    fi
    warn "Бот не запустился. Последние строки лога:"
    journalctl -u "$SERVICE" -n 25 --no-pager >&2 || true
    return 1
}

# ── команды ──────────────────────────────────────────────────────────────────────────────────

cmd_install() {
    require_root
    check_os
    if [[ -d "$APP_DIR/.git" ]]; then
        warn "Бот уже установлен — обновляю."
        cmd_update
        return
    fi
    printf '%s🎬 Установка VideoTranslaterBot%s\n' "$C_BOLD" "$C_RESET"
    install_packages
    check_python
    create_user
    fetch_code
    install_python_deps
    smoke_test || die "Бот не прошёл проверку после установки."
    finish_setup || die "Проверьте настройки: vtbot config"
    printf '\n%s✅ Готово!%s Напишите своему боту /start в Telegram.\n\n' "$C_GREEN" "$C_RESET"
    cmd_help
}

cmd_update() {
    require_root
    require_installed
    local force=0 old new
    [[ "${1:-}" == "--force" ]] && force=1
    BRANCH="$(git -C "$APP_DIR" rev-parse --abbrev-ref HEAD)"

    step "Проверяю обновления…"
    git -C "$APP_DIR" fetch --quiet origin "$BRANCH" || die "Не удалось связаться с GitHub."
    old="$(git -C "$APP_DIR" rev-parse HEAD)"
    new="$(git -C "$APP_DIR" rev-parse "origin/$BRANCH")"
    if [[ "$old" == "$new" && $force == 0 ]]; then
        ok "Уже установлена последняя версия: $(version_string)"
        # Установка могла прерваться на настройке — тогда доводим её до конца.
        if config_complete && { ! has_systemd || systemctl is-active --quiet "$SERVICE"; }; then
            return 0
        fi
        finish_setup || die "Бот не запустился. Проверьте настройки: vtbot config"
        return 0
    fi
    if [[ "$old" != "$new" ]]; then
        echo "Что нового:"
        git -C "$APP_DIR" log --format='  • %s' "$old..$new" | head -20
    fi

    git -C "$APP_DIR" reset --quiet --hard "$new"
    if ! install_python_deps || ! smoke_test; then
        warn "Новая версия не прошла проверку — возвращаю предыдущую."
        rollback "$old"
        die "Обновление отменено, бот работает на прежней версии."
    fi
    if ! finish_setup; then
        warn "Новая версия не запустилась — возвращаю предыдущую."
        rollback "$old"
        start_and_verify || true
        die "Обновление отменено, бот работает на прежней версии."
    fi
    ok "Обновлено до версии: $(version_string)"
}

LOCAL_WHISPER_MODELS="tiny base small medium large-v2 large-v3 large-v3-turbo turbo distil-large-v3"
NLLB_SMALL="JustFrederik/nllb-200-distilled-600M-ct2-int8"
NLLB_LARGE="OpenNMT/nllb-200-distilled-1.3B-ct2-int8"

mem_total_mb() { awk '/^MemTotal:/ { print int($2 / 1024) }' /proc/meminfo; }

# Подбирает модели под память сервера: распознавание речи и перевод работают прямо на нём.
configure_local_models() {
    local force="$1" whisper nllb mem cores
    whisper="$(env_get TRANSCRIBE_MODEL)"
    nllb="$(env_get TRANSLATE_MODEL)"
    if [[ "$force" != 1 && " $LOCAL_WHISPER_MODELS " == *" $whisper "* && "$nllb" == *nllb* ]]; then
        return 0
    fi
    mem="$(mem_total_mb)"
    cores="$(nproc)"
    if (( mem >= 7000 )); then
        whisper=large-v3-turbo nllb="$NLLB_LARGE"
    elif (( mem >= 3500 )); then
        whisper=large-v3-turbo nllb="$NLLB_SMALL"
    else
        whisper=small nllb="$NLLB_SMALL"
    fi
    env_set TRANSCRIBE_MODEL "$whisper"
    env_set TRANSLATE_MODEL "$nllb"
    env_set MAX_CONCURRENT_JOBS 1  # всё считает процессор — по одному видео за раз
    ok "Сервер: ${mem} МБ памяти, ${cores} ядер → распознавание: $whisper, перевод: ${nllb#*/}"
    if (( cores < 2 )); then
        warn "Одно ядро — перевод будет очень медленным. Лучше сервер хотя бы с 2 ядрами."
    fi
}

ensure_swap() {
    # На маленьких серверах модели могут не поместиться в память — добавляем файл подкачки.
    (( $(mem_total_mb) < 3500 )) || return 0
    [[ -n "$(swapon --show --noheadings 2>/dev/null)" ]] && return 0
    [[ -e /swapfile ]] && return 0
    step "Мало памяти — создаю файл подкачки 2 ГБ…"
    if { fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none; } \
        && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile; then
        grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
        ok "Файл подкачки включён"
    else
        rm -f /swapfile
        warn "Не удалось создать файл подкачки."
    fi
}

# Скачивает модели и проверяет, что они загружаются (только для режима «на сервере»).
prefetch_models() {
    [[ "$(env_get PROVIDER)" == local ]] || return 0
    local free_mb
    free_mb="$(df --output=avail -m "$APP_DIR" | tail -1 | tr -d ' ')"
    if (( free_mb < 4000 )); then
        warn "На диске свободно ${free_mb} МБ, а моделям нужно до 4 ГБ."
    fi
    ensure_swap
    step "Скачиваю и проверяю модели (первый раз 1–3 ГБ, это может занять несколько минут)…"
    if ! (cd "$APP_DIR" && runuser -u "$APP_USER" -- env HOME="$APP_DIR/data" DATA_DIR="$APP_DIR/data" \
            HF_HUB_DISABLE_TELEMETRY=1 "$APP_DIR/venv/bin/python" -m bot.prefetch); then
        warn "Не удалось скачать или запустить модели."
        return 1
    fi
    ok "Модели готовы"
}

# В старых версиях .env модели OpenAI были прописаны явно. В бесплатном режиме Groq их не знает,
# поэтому такие значения по умолчанию очищаются — бот сам возьмёт модели выбранного режима.
clear_openai_defaults() {
    [[ "$(env_get PROVIDER)" == free ]] || return 0
    local pair key value
    for pair in TRANSCRIBE_MODEL=whisper-1 TRANSLATE_MODEL=gpt-5.4 TTS_MODEL=gpt-4o-mini-tts; do
        key="${pair%%=*}" value="${pair#*=}"
        if [[ "$(env_get "$key")" == "$value" ]]; then env_set "$key" ""; fi
    done
}

# Общий хвост установки и обновления. Настройки спрашиваются, только если чего-то не хватает.
finish_setup() {
    # Старые установки работали только через OpenAI — не переключаем их в бесплатный режим.
    if [[ -f "$(ENV_FILE)" && -z "$(env_get PROVIDER)" && -n "$(env_get OPENAI_API_KEY)" ]]; then
        env_set PROVIDER openai
    fi
    create_user
    env_merge_new_keys
    configure
    clear_openai_defaults
    prepare_dirs
    prefetch_models || return 1
    install_cli
    write_service
    start_and_verify
}

rollback() {
    git -C "$APP_DIR" reset --quiet --hard "$1"
    install_python_deps || true
}

cmd_config() {
    require_root
    require_installed
    configure 1
    if has_systemd; then start_and_verify || true; fi
}

cmd_bigfiles() {
    require_root
    require_installed
    step "Большие файлы (до 2 ГБ) через локальный сервер Telegram Bot API"
    echo "Нужны api_id и api_hash: https://my.telegram.org → API development tools."
    local api_id api_hash token
    api_id="$(ask "api_id" "$(env_get TELEGRAM_API_ID)")"
    api_hash="$(ask "api_hash" "$(env_get TELEGRAM_API_HASH)")"
    [[ "$api_id" =~ ^[0-9]+$ && -n "$api_hash" ]] || die "Нужны api_id (число) и api_hash."

    if ! command -v docker >/dev/null; then
        step "Устанавливаю Docker…"
        curl -fsSL https://get.docker.com | sh >/dev/null
    fi

    mkdir -p "$BOT_API_DIR"
    # Бот должен читать файлы, которые скачивает сервер, под каким бы пользователем тот ни работал.
    setfacl -R -m "u:$APP_USER:rwX" "$BOT_API_DIR"
    setfacl -R -d -m "u:$APP_USER:rwX" "$BOT_API_DIR"

    docker rm -f "$BOT_API_CONTAINER" >/dev/null 2>&1 || true
    docker run -d --name "$BOT_API_CONTAINER" --restart unless-stopped \
        -p 127.0.0.1:8081:8081 \
        -e TELEGRAM_API_ID="$api_id" -e TELEGRAM_API_HASH="$api_hash" -e TELEGRAM_LOCAL=1 \
        -v "$BOT_API_DIR:$BOT_API_DIR" \
        aiogram/telegram-bot-api:latest >/dev/null
    ok "Сервер Bot API запущен"

    # Бота нужно один раз «выписать» из облачного API, иначе локальный сервер его не примет.
    if [[ -z "$(env_get TELEGRAM_API_URL)" ]]; then
        token="$(env_get BOT_TOKEN)"
        curl -fsS --max-time 15 "https://api.telegram.org/bot$token/logOut" >/dev/null 2>&1 || true
    fi
    env_set TELEGRAM_API_ID "$api_id"
    env_set TELEGRAM_API_HASH "$api_hash"
    env_set TELEGRAM_API_URL "http://127.0.0.1:8081"
    secure_env
    start_and_verify || die "Бот не запустился с локальным сервером. Смотрите: vtbot logs"
    ok "Теперь бот принимает и отправляет файлы до 2 ГБ"
}

cmd_uninstall() {
    require_root
    confirm "Удалить бота вместе с настройками и данными?" n || { echo "Отменено."; return 0; }
    if has_systemd; then
        systemctl disable --now "$SERVICE" >/dev/null 2>&1 || true
        rm -f "/etc/systemd/system/$SERVICE.service"
        systemctl daemon-reload
    fi
    if command -v docker >/dev/null; then docker rm -f "$BOT_API_CONTAINER" >/dev/null 2>&1 || true; fi
    rm -rf "$APP_DIR" "$CLI"
    userdel "$APP_USER" >/dev/null 2>&1 || true
    ok "Бот удалён"
}

cmd_status() {
    require_installed
    echo "Версия:  $(version_string)"
    echo "Папка:   $APP_DIR"
    if has_systemd; then
        if systemctl is-active --quiet "$SERVICE"; then
            echo "Статус:  ${C_GREEN}работает${C_RESET}"
        else
            echo "Статус:  ${C_RED}остановлен${C_RESET}"
        fi
    fi
    if [[ -n "$(env_get TELEGRAM_API_URL)" ]]; then echo "Файлы:   до 2 ГБ (локальный Bot API)"; else echo "Файлы:   до 20 МБ (vtbot bigfiles — до 2 ГБ)"; fi
}

cmd_help() {
    cat <<EOF
Управление ботом:
  vtbot update      обновить до новой версии (настройки и данные сохраняются)
  vtbot status      версия и состояние
  vtbot logs        логи в реальном времени (выход — Ctrl+C)
  vtbot restart     перезапустить
  vtbot stop        остановить
  vtbot start       запустить
  vtbot config      изменить токен, режим работы, ключ, список пользователей
  vtbot bigfiles    включить файлы до 2 ГБ
  vtbot uninstall   удалить бота
EOF
}

main() {
    ORIGINAL_ARGS=("$@")
    local command="${1:-}"
    [[ $# -gt 0 ]] && shift
    case "$command" in
        "")
            # Без аргументов: через curl — установка, у установленного бота — справка.
            if [[ -d "$APP_DIR/.git" && "$(basename "$0")" == vtbot ]]; then cmd_help; else cmd_install "$@"; fi
            ;;
        install)   cmd_install "$@" ;;
        update)    cmd_update "$@" ;;
        config)    cmd_config "$@" ;;
        bigfiles)  cmd_bigfiles "$@" ;;
        uninstall) cmd_uninstall "$@" ;;
        status)    cmd_status ;;
        logs)      journalctl -u "$SERVICE" -f -n 100 ;;
        restart)   require_root; start_and_verify ;;
        stop)      require_root; systemctl stop "$SERVICE"; ok "Бот остановлен" ;;
        start)     require_root; start_and_verify ;;
        help|-h|--help) cmd_help ;;
        *) warn "Неизвестная команда: $command"; cmd_help; exit 1 ;;
    esac
}

main "$@"
exit
