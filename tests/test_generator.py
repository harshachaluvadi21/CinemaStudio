"""
test_generator.py — Tests for the Ollama integration, prompt builder,
response parser, and export helpers.
"""

import io
import pytest
from unittest.mock import patch, MagicMock

from generator import build_prompt, parse_response, generate_content, SECTION_MARKERS
from export import to_txt, to_pdf, to_docx


# ── Prompt Builder ────────────────────────────────────────────────────────────

class TestBuildPrompt:
    def test_contains_storyline(self):
        storyline = "A detective in 1940s LA investigates a haunted jazz club."
        prompt = build_prompt(storyline)
        assert storyline in prompt

    def test_contains_section_markers(self):
        prompt = build_prompt("Any story")
        assert SECTION_MARKERS["screenplay"] in prompt
        assert SECTION_MARKERS["characters"] in prompt
        assert SECTION_MARKERS["sound"] in prompt
        assert SECTION_MARKERS["end"] in prompt

    def test_contains_format_instructions(self):
        prompt = build_prompt("Any story")
        assert "INT." in prompt or "screenplay" in prompt.lower()
        assert "character" in prompt.lower()
        assert "sound" in prompt.lower()


# ── Response Parser ───────────────────────────────────────────────────────────

class TestParseResponse:
    def _make_response(self, screenplay="SP", characters="CH", sound="SD"):
        m = SECTION_MARKERS
        return (
            f"{m['screenplay']}\n{screenplay}\n"
            f"{m['characters']}\n{characters}\n"
            f"{m['sound']}\n{sound}\n"
            f"{m['end']}"
        )

    def test_parses_all_sections(self):
        raw = self._make_response("My screenplay", "My characters", "My sound")
        result = parse_response(raw)
        assert result["screenplay"] == "My screenplay"
        assert result["characters"] == "My characters"
        assert result["sound"] == "My sound"

    def test_fallback_on_missing_markers(self):
        """When markers are absent, falls back to thirds split."""
        raw = "A" * 300 + "B" * 300 + "C" * 300
        result = parse_response(raw)
        assert result["screenplay"]
        assert result["characters"]
        assert result["sound"]

    def test_empty_section_gets_placeholder(self):
        raw = self._make_response("", "", "")
        result = parse_response(raw)
        assert "No screenplay" in result["screenplay"]
        assert "No character" in result["characters"]
        assert "No sound" in result["sound"]


# ── Ollama Integration ────────────────────────────────────────────────────────

class TestGenerateContent:
    def _mock_response(self, text):
        mock = MagicMock()
        mock.json.return_value = {"response": text}
        mock.raise_for_status.return_value = None
        return mock

    def test_successful_generation(self):
        m = SECTION_MARKERS
        fake_text = (
            f"{m['screenplay']}\nINT. BARN - NIGHT\n"
            f"{m['characters']}\nJack: A reclusive inventor.\n"
            f"{m['sound']}\nScene 1: Crickets.\n"
            f"{m['end']}"
        )
        with patch("generator.requests.post", return_value=self._mock_response(fake_text)):
            result = generate_content("A reclusive inventor finds an artifact.")
        assert "INT. BARN" in result["screenplay"]
        assert "Jack" in result["characters"]
        assert "Crickets" in result["sound"]

    def test_retry_on_failure_then_success(self):
        """Should retry on RequestException and succeed on the second attempt."""
        import requests as req_lib
        m = SECTION_MARKERS
        fake_text = (
            f"{m['screenplay']}\nSP\n{m['characters']}\nCH\n{m['sound']}\nSD\n{m['end']}"
        )
        success_mock = self._mock_response(fake_text)
        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise req_lib.RequestException("Connection refused")
            return success_mock

        with patch("generator.requests.post", side_effect=side_effect):
            with patch("generator.time.sleep"):  # skip actual sleep
                result = generate_content("Any story")
        assert call_count["n"] == 2
        assert result["screenplay"] == "SP"

    def test_raises_after_max_retries(self):
        """Should raise RuntimeError after all retries are exhausted."""
        import requests as req_lib
        with patch("generator.requests.post", side_effect=req_lib.RequestException("down")):
            with patch("generator.time.sleep"):
                with pytest.raises(RuntimeError, match="did not respond"):
                    generate_content("Any story")


# ── Export Helpers ────────────────────────────────────────────────────────────

class TestExports:
    SAMPLE = "INT. BARN - NIGHT\n\nJack enters the barn.\n\nJACK\nWhat is this thing?"

    def test_to_txt_returns_bytes(self):
        buf = to_txt(self.SAMPLE, "screenplay")
        assert isinstance(buf, io.BytesIO)
        content = buf.read().decode("utf-8")
        assert "SCREENPLAY" in content
        assert "INT. BARN" in content

    def test_to_pdf_returns_pdf_bytes(self):
        buf = to_pdf(self.SAMPLE, "screenplay")
        assert isinstance(buf, io.BytesIO)
        header = buf.read(4)
        assert header == b"%PDF", "Output should be a valid PDF"

    def test_to_docx_returns_nonempty_bytes(self):
        buf = to_docx(self.SAMPLE, "screenplay")
        assert isinstance(buf, io.BytesIO)
        data = buf.read()
        assert len(data) > 100, "DOCX should not be empty"
        # DOCX files start with PK (ZIP magic bytes)
        assert data[:2] == b"PK"

    def test_to_txt_characters(self):
        buf = to_txt("Jack: A reclusive inventor.", "characters")
        content = buf.read().decode("utf-8")
        assert "CHARACTER PROFILES" in content

    def test_to_pdf_sound(self):
        buf = to_pdf("Scene 1: Crickets and wind.", "sound")
        buf.seek(0)
        assert buf.read(4) == b"%PDF"


# ── Download Route ────────────────────────────────────────────────────────────

class TestDownloadRoute:
    def test_download_without_generated_content(self, logged_in_client):
        """Download before generating returns 404."""
        resp = logged_in_client.get("/download/screenplay/txt")
        assert resp.status_code == 404

    def test_download_invalid_section(self, logged_in_client):
        """Invalid section returns 400."""
        resp = logged_in_client.get("/download/invalid/txt")
        assert resp.status_code == 400

    def test_download_invalid_format(self, logged_in_client):
        """Invalid format returns 400."""
        resp = logged_in_client.get("/download/screenplay/exe")
        assert resp.status_code == 400

    def test_generate_empty_storyline(self, logged_in_client):
        """Empty storyline returns 400."""
        resp = logged_in_client.post(
            "/generate_content",
            json={"storyline": ""},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_generate_too_long_storyline(self, logged_in_client):
        """Storyline over 2000 chars returns 400."""
        resp = logged_in_client.post(
            "/generate_content",
            json={"storyline": "x" * 2001},
            content_type="application/json",
        )
        assert resp.status_code == 400
