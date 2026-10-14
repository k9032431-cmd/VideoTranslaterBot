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
    if [[ -r /dev/tty ]]; then
        read -r -p "$prompt: " answer </dev/tty || true
    fi
    printf '%s' "${answer:-$default}"
}

ask_secret() {
    local prompt="$1" answer=""
    if [[ -r /dev/tty ]]; then
        read -r -s -p "$prompt: " answer </dev/tty || true
        echo >/dev/tty
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

check_openai_key() {
    [[ "${VTBOT_SKIP_CHECKS:-0}" == 1 ]] && return 0
    local base="${OPENAI_BASE_URL:-https://api.openai.com/v1}" code
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
        -H "Authorization: Bearer $1" "$base/models" 2>/dev/null || true)"
    if [[ "$code" == 200 ]]; then ok "Ключ OpenAI верный"; return 0; fi
    return 1
}

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

configure() {
    local reconfigure="${1:-0}" token key ids current
    step "Настройка"
    if [[ ! -f "$(ENV_FILE)" ]]; then
        cp "$APP_DIR/.env.example" "$(ENV_FILE)"
    fi

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
            [[ -n "$token" ]] || { warn "Токен обязателен."; continue; }
            check_bot_token "$token" && break
            warn "Telegram не принял этот токен. Проверьте и введите ещё раз."
            [[ -r /dev/tty ]] || die "Неверный BOT_TOKEN."
        done
    elif [[ -n "$token" ]]; then
        check_bot_token "$token" || die "Telegram не принял BOT_TOKEN."
    fi
    if [[ -n "$token" ]]; then env_set BOT_TOKEN "$token"; fi

    # Ключ OpenAI
    current="$(env_get OPENAI_API_KEY)"
    key="${OPENAI_API_KEY:-}"
    if [[ -z "$key" && ( -z "$current" || "$reconfigure" == 1 ) ]]; then
        while true; do
            if [[ -n "$current" ]]; then
                key="$(ask_secret "Ключ OpenAI (Enter — оставить $(mask "$current"))")"
                key="${key:-$current}"
            else
                key="$(ask_secret "Ключ OpenAI (https://platform.openai.com/api-keys)")"
            fi
            [[ -n "$key" ]] || { warn "Ключ обязателен."; continue; }
            check_openai_key "$key" && break
            warn "OpenAI не принял этот ключ (или на счёте нет денег). Проверьте и введите ещё раз."
            [[ -r /dev/tty ]] || die "Неверный OPENAI_API_KEY."
        done
    elif [[ -n "$key" ]]; then
        check_openai_key "$key" || die "OpenAI не принял OPENAI_API_KEY."
    fi
    if [[ -n "$key" ]]; then env_set OPENAI_API_KEY "$key"; fi

    # Кому разрешено пользоваться
    current="$(env_get ALLOWED_USER_IDS)"
    if [[ -n "${ALLOWED_USER_IDS+set}" ]]; then
        ids="$ALLOWED_USER_IDS"
    elif [[ -z "$current" || "$reconfigure" == 1 ]]; then
        echo "Перевод стоит денег, поэтому лучше разрешить бота только себе."
        echo "Свой Telegram id можно узнать у @userinfobot. Несколько id — через запятую."
        ids="$(ask "Telegram id, кому разрешён бот (Enter — всем)" "$current")"
    else
        ids="$current"
    fi
    ids="${ids// /}"
    [[ -z "$ids" || "$ids" =~ ^[0-9]+(,[0-9]+)*$ ]] || die "ALLOWED_USER_IDS: только числа через запятую."
    env_set ALLOWED_USER_IDS "$ids"

    secure_env
    [[ -n "$(env_get BOT_TOKEN)" && -n "$(env_get OPENAI_API_KEY)" ]] || die "Не заданы BOT_TOKEN и OPENAI_API_KEY."
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
    prepare_dirs
    configure
    install_cli
    write_service
    start_and_verify || die "Проверьте настройки: vtbot config"
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
    env_merge_new_keys
    secure_env
    prepare_dirs
    install_cli
    write_service
    if ! start_and_verify; then
        warn "Новая версия не запустилась — возвращаю предыдущую."
        rollback "$old"
        start_and_verify || true
        die "Обновление отменено, бот работает на прежней версии."
    fi
    ok "Обновлено до версии: $(version_string)"
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
  vtbot config      изменить токен, ключ OpenAI, список пользователей
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
