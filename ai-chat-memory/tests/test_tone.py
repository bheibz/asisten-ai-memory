import pytest
from app.core.orchestrator import BrainOrchestrator, SAD_WORDS, ANGRY_WORDS, HAPPY_WORDS


@pytest.fixture
def orch():
    return BrainOrchestrator(None)


def test_tone_neutral(orch):
    tone = orch._detect_tone("apa kabar")
    assert tone == "neutral"


def test_tone_sad(orch):
    tone = orch._detect_tone("aku sedih hari ini")
    assert tone == "sympathetic"


def test_tone_angry(orch):
    tone = orch._detect_tone("aku marah!")
    assert tone == "calm"


def test_tone_happy(orch):
    tone = orch._detect_tone("aku senang sekali")
    assert tone == "cheerful"


def test_tone_words_sad():
    assert "sedih" in SAD_WORDS
    assert "lelah" in SAD_WORDS


def test_tone_words_angry():
    assert "marah" in ANGRY_WORDS
    assert "kesal" in ANGRY_WORDS


def test_tone_words_happy():
    assert "senang" in HAPPY_WORDS
    assert "bahagia" in HAPPY_WORDS
