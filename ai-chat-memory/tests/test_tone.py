import pytest
from app.core.context_builder import ContextBuilder


@pytest.fixture
def ctx():
    return ContextBuilder()


def test_tone_neutral(ctx):
    tone = ctx.detect_tone("apa kabar")
    assert tone == "neutral"


def test_tone_sad(ctx):
    tone = ctx.detect_tone("aku sedih hari ini")
    assert tone == "sympathetic"


def test_tone_angry(ctx):
    tone = ctx.detect_tone("aku marah!")
    assert tone == "calm"


def test_tone_happy(ctx):
    tone = ctx.detect_tone("aku senang sekali")
    assert tone == "cheerful"


def test_tone_anxious(ctx):
    tone = ctx.detect_tone("aku cemas sekali")
    assert tone == "anxious"


def test_tone_tired(ctx):
    tone = ctx.detect_tone("aku capek banget")
    assert tone == "tired"


# ── Verify tone word sets still exist ─────────────────────────

def test_tone_words_sad():
    from app.core.context_builder import _TONE_MAP
    assert "sedih" in _TONE_MAP["sympathetic"]
    assert "lelah" in _TONE_MAP["sympathetic"]


def test_tone_words_angry():
    from app.core.context_builder import _TONE_MAP
    assert "marah" in _TONE_MAP["calm"]
    assert "kesal" in _TONE_MAP["calm"]


def test_tone_words_happy():
    from app.core.context_builder import _TONE_MAP
    assert "senang" in _TONE_MAP["cheerful"]
    assert "bahagia" in _TONE_MAP["cheerful"]


def test_tone_words_anxious():
    from app.core.context_builder import _TONE_MAP
    assert "cemas" in _TONE_MAP["anxious"]


def test_tone_words_tired():
    from app.core.context_builder import _TONE_MAP
    assert "capek" in _TONE_MAP["tired"]
