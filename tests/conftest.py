import pytest

from bot.pipeline import voices

# A snapshot-like slice of Microsoft's voice list, so tests never depend on the network.
FAKE_EDGE_VOICES = [
    {"ShortName": name, "Locale": "-".join(name.split("-")[:2]), "Gender": gender}
    for name, gender in [
        ("ru-RU-DmitryNeural", "Male"), ("ru-RU-SvetlanaNeural", "Female"),
        ("en-US-AndrewNeural", "Male"), ("en-US-AndrewMultilingualNeural", "Male"),
        ("en-US-BrianMultilingualNeural", "Male"), ("en-GB-RyanNeural", "Male"),
        ("en-US-EmmaMultilingualNeural", "Female"), ("en-US-AvaNeural", "Female"),
        ("en-US-AvaMultilingualNeural", "Female"), ("en-AU-NatashaNeural", "Female"),
        ("fr-FR-RemyMultilingualNeural", "Male"), ("fr-FR-VivienneMultilingualNeural", "Female"),
        ("de-AT-JonasNeural", "Male"), ("de-DE-KillianNeural", "Male"), ("de-DE-AmalaNeural", "Female"),
        ("tr-TR-AhmetNeural", "Male"), ("tr-TR-EmelNeural", "Female"),
    ]
]


@pytest.fixture(autouse=True)
def fake_edge_voice_list(monkeypatch):
    monkeypatch.setattr(voices, "_edge_cache", list(FAKE_EDGE_VOICES))
