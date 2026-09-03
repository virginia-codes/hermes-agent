"""Tests for TTS speed configuration across providers."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in (
        "OPENAI_API_KEY",
        "HERMES_SESSION_PLATFORM",
    ):
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# Edge TTS speed
# ---------------------------------------------------------------------------

class TestEdgeTtsSpeed:
    def _run(self, tts_config, tmp_path):
        mock_comm = MagicMock()
        mock_comm.save = AsyncMock()
        mock_edge = MagicMock()
        mock_edge.Communicate = MagicMock(return_value=mock_comm)

        with patch("tools.tts_tool._import_edge_tts", return_value=mock_edge):
            from tools.tts_tool import _generate_edge_tts
            asyncio.run(_generate_edge_tts("Hello", str(tmp_path / "out.mp3"), tts_config))
        return mock_edge.Communicate

    def test_default_no_rate_kwarg(self, tmp_path):
        """No speed config => no rate kwarg passed to Communicate."""
        comm_cls = self._run({}, tmp_path)
        kwargs = comm_cls.call_args[1]
        assert "rate" not in kwargs


    def test_speed_exactly_one_no_rate(self, tmp_path):
        """Explicit speed=1.0 should not pass rate kwarg."""
        comm_cls = self._run({"speed": 1.0}, tmp_path)
        kwargs = comm_cls.call_args[1]
        assert "rate" not in kwargs


# ---------------------------------------------------------------------------
# OpenAI TTS speed
# ---------------------------------------------------------------------------

class TestOpenaiTtsSpeed:
    def _run(self, tts_config, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        mock_response = MagicMock()
        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = mock_response
        mock_cls = MagicMock(return_value=mock_client)

        with patch("tools.tts_tool._import_openai_client", return_value=mock_cls), \
             patch("tools.tts_tool._resolve_openai_audio_client_config",
                   return_value=("test-key", None, False)):
            from tools.tts_tool import _generate_openai_tts
            _generate_openai_tts("Hello", str(tmp_path / "out.mp3"), tts_config)
        return mock_client.audio.speech.create

    def test_default_no_speed_kwarg(self, tmp_path, monkeypatch):
        """No speed config => no speed kwarg in create call."""
        create = self._run({}, tmp_path, monkeypatch)
        kwargs = create.call_args[1]
        assert "speed" not in kwargs


    def test_speed_clamped_high(self, tmp_path, monkeypatch):
        """Speed above 4.0 is clamped to 4.0."""
        create = self._run({"speed": 10.0}, tmp_path, monkeypatch)
        kwargs = create.call_args[1]
        assert kwargs["speed"] == 4.0


# ---------------------------------------------------------------------------
# OpenAI TTS language (lang_code for OpenAI-compatible endpoints)
# ---------------------------------------------------------------------------

class TestOpenaiTtsLangCode:
    def _run(self, tts_config, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        mock_response = MagicMock()
        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = mock_response
        mock_cls = MagicMock(return_value=mock_client)

        with patch("tools.tts_tool._import_openai_client", return_value=mock_cls), \
             patch("tools.tts_tool._resolve_openai_audio_client_config",
                   return_value=("test-key", None, False)):
            from tools.tts_tool import _generate_openai_tts
            _generate_openai_tts("Hola", str(tmp_path / "out.mp3"), tts_config)
        return mock_client.audio.speech.create

    def test_default_no_extra_body(self, tmp_path, monkeypatch):
        """No language config => no extra_body kwarg in create call."""
        create = self._run({}, tmp_path, monkeypatch)
        kwargs = create.call_args[1]
        assert "extra_body" not in kwargs


    def test_language_coexists_with_speed(self, tmp_path, monkeypatch):
        """language and speed are forwarded independently."""
        create = self._run({"openai": {"language": "es", "speed": 2.0}},
                           tmp_path, monkeypatch)
        kwargs = create.call_args[1]
        assert kwargs["extra_body"] == {"lang_code": "es"}
        assert kwargs["speed"] == 2.0


# ---------------------------------------------------------------------------
# Tool-level speed parameter (text_to_speech_tool speed injection)
# ---------------------------------------------------------------------------

class TestToolLevelSpeed:
    """Verify that the speed parameter on text_to_speech_tool injects into config."""

    def test_speed_injected_into_config(self, tmp_path, monkeypatch):
        """When speed is passed to the tool, it overrides config speed."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        mock_response = MagicMock()
        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = mock_response
        mock_cls = MagicMock(return_value=mock_client)

        with patch("tools.tts_tool._import_openai_client", return_value=mock_cls), \
             patch("tools.tts_tool._resolve_openai_audio_client_config",
                   return_value=("test-key", None, False)), \
             patch("tools.tts_tool._load_tts_config", return_value={"provider": "openai", "openai": {}}), \
             patch("tools.tts_tool._get_provider", return_value="openai"), \
             patch("tools.tts_tool._resolve_command_provider_config", return_value=None), \
             patch("tools.tts_tool._resolve_max_text_length", return_value=4096), \
             patch("tools.tts_tool._generate_openai_tts") as mock_gen, \
             patch("gateway.session_context.get_session_env", return_value=""):
            from tools.tts_tool import text_to_speech_tool
            text_to_speech_tool("Hello", str(tmp_path / "out.mp3"), speed=0.7)

        # Verify the tts_config passed to the generator has speed=0.7
        call_args = mock_gen.call_args
        config_passed = call_args[0][2]  # (text, output_path, tts_config)
        assert config_passed["speed"] == 0.7

    def test_speed_clamped_range(self, tmp_path, monkeypatch):
        """Speed values outside 0.25-4.0 are clamped."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        with patch("tools.tts_tool._load_tts_config", return_value={"provider": "openai", "openai": {}}), \
             patch("tools.tts_tool._get_provider", return_value="openai"), \
             patch("tools.tts_tool._resolve_command_provider_config", return_value=None), \
             patch("tools.tts_tool._resolve_max_text_length", return_value=4096), \
             patch("tools.tts_tool._generate_openai_tts") as mock_gen, \
             patch("gateway.session_context.get_session_env", return_value=""):
            from tools.tts_tool import text_to_speech_tool
            text_to_speech_tool("Hello", str(tmp_path / "out.mp3"), speed=10.0)

        config_passed = mock_gen.call_args[0][2]
        assert config_passed["speed"] == 4.0

    def test_no_speed_preserves_config(self, tmp_path, monkeypatch):
        """When speed is None, config is not mutated."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        original_config = {"provider": "openai", "openai": {}, "speed": 1.5}

        with patch("tools.tts_tool._load_tts_config", return_value=original_config), \
             patch("tools.tts_tool._get_provider", return_value="openai"), \
             patch("tools.tts_tool._resolve_command_provider_config", return_value=None), \
             patch("tools.tts_tool._resolve_max_text_length", return_value=4096), \
             patch("tools.tts_tool._generate_openai_tts") as mock_gen, \
             patch("gateway.session_context.get_session_env", return_value=""):
            from tools.tts_tool import text_to_speech_tool
            text_to_speech_tool("Hello", str(tmp_path / "out.mp3"), speed=None)

        config_passed = mock_gen.call_args[0][2]
        assert config_passed.get("speed") == 1.5  # original config preserved
        assert original_config.get("speed") == 1.5  # original not mutated
