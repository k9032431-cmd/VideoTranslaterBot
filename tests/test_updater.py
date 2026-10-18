"""The "Update the bot" button: request file → (systemd runs vtbot self-update) → result message."""

import asyncio

import pytest

from bot import updater as updater_module
from bot.i18n import t
from bot.updater import Updater


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text))


@pytest.fixture(autouse=True)
def fast_polling(monkeypatch):
    monkeypatch.setattr(updater_module, "POLL_INTERVAL", 0.01)
    monkeypatch.setattr(updater_module, "TRIGGER_TIMEOUT", 0.2)


async def _wait_until(predicate, timeout=3.0):
    for _ in range(int(timeout / 0.01)):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not met")


async def test_update_success_is_reported(tmp_path):
    (tmp_path / "version.txt").write_text("abc123 от 18.10.2026 — old\n")
    bot = FakeBot()
    up = Updater(bot, tmp_path)
    assert up.version() == "abc123 от 18.10.2026 — old"

    up.start(42, "ru")
    assert (tmp_path / "update.request").exists() and up.running
    # what `vtbot self-update` does:
    (tmp_path / "update.request").unlink()
    (tmp_path / "update.result").write_text("status=updated\nversion=def456 — new <b>\n")
    await _wait_until(lambda: bot.sent)

    assert bot.sent == [(42, t("ru", "update_done", version="def456 — new &lt;b&gt;"))]
    assert not (tmp_path / "update.pending").exists() and not (tmp_path / "update.result").exists()


async def test_report_survives_bot_restart(tmp_path):
    bot = FakeBot()
    Updater(bot, tmp_path).pending.write_text("7\nen\n")  # written before the restart
    (tmp_path / "update.result").write_text("status=latest\nversion=v1\n")

    up = Updater(bot, tmp_path)  # the new bot process
    up.resume()
    await _wait_until(lambda: bot.sent)
    assert bot.sent == [(7, t("en", "update_latest", version="v1"))]


async def test_failed_update_shows_log(tmp_path):
    bot = FakeBot()
    up = Updater(bot, tmp_path)
    up.start(1, "ru")
    (tmp_path / "update.request").unlink()
    (tmp_path / "update.log").write_text("line1\n✘ Обновление отменено <x>\n")
    (tmp_path / "update.result").write_text("status=failed\nversion=v0\n")
    await _wait_until(lambda: bot.sent)
    assert "Обновление отменено &lt;x&gt;" in bot.sent[0][1]


async def test_old_install_without_watcher(tmp_path):
    bot = FakeBot()
    up = Updater(bot, tmp_path)
    up.start(1, "ru")  # nobody removes update.request
    await _wait_until(lambda: bot.sent)
    assert bot.sent == [(1, t("ru", "update_unavailable"))]
    assert not (tmp_path / "update.request").exists()


def test_resume_without_pending_does_nothing(tmp_path):
    up = Updater(FakeBot(), tmp_path)
    up.resume()
    assert not up.running
