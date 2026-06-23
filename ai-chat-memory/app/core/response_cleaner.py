"""
Response cleaner — strips reasoning noise and status markers from LLM output.
Uses a multi-strategy scoring approach instead of hardcoded keyword matching.
"""

import re
from typing import Optional, Tuple

# ── Status / command markers ────────────────────────────────────────────

_MARKER_RE = re.compile(r"__STATUS__:[^\n]*\n?|__CMD__:[^\n]*")

# ── Explicit answer markers (checked from the end of the text) ──────────

_ANSWER_MARKERS = [
    # Indonesian
    "Jawaban:", "Jawab:", "Respon:", "Mulai respon.",
    "Saya jawab:", "Saya mulai jawab:", "Saya akan menjawab:",
    "Saya akan mulai:", "Ini jawaban saya:", "Saya merespon:",
    "Aku akan menjawab:", "Kesimpulan:",
    # English
    "Answer:", "Here is my response:", "Thus, response:",
    "Final answer:", "Result:", "Conclusion:",
    "Hasil:",
]

# ── Reasoning keyword patterns (to identify reasoning text) ─────────────

_REASONING_STARTS = re.compile(
    r"^(?:The|We|I|My|This|It|To|But|So|Let|In|"
    r"For|First|Second|Since|Because|However|Therefore|"
    r"Thus|Note|Wait|Yes|No|Maybe|Actually|Basically|"
    r"Oke|Jadi|Baik|Mari|Saya|Aku|Kita|Pertama|Kedua|"
    r"Karena|Namun|Tetapi|Mungkin|Sebenarnya|Misalnya|"
    r"Langkah|Pertimbangan|Analisis|Berdasarkan|Menurut)\b",
    re.IGNORECASE,
)

# ── Sentence-ending markers ─────────────────────────────────────────────

_SENTENCE_END = re.compile(r"[.!?]\s*$")


class ResponseCleaner:
    """
    Cleans LLM output by removing:
    1. Status markers (__STATUS__, __CMD__)
    2. Reasoning/thinking text (when the model outputs thinking before answer)
    """

    @staticmethod
    def clean(text: str) -> str:
        """Remove markers and strip reasoning content. Returns cleaned text."""
        # Step 1: Remove marker lines
        text = _MARKER_RE.sub("", text).strip()
        if not text:
            return text

        # Step 2: Try to find the real answer within the text
        answer = ResponseCleaner._extract_answer(text)
        return answer or text

    @staticmethod
    def _extract_answer(text: str) -> Optional[str]:
        """Try to extract the real answer from potentially long reasoning text."""

        # Strategy 1: Explicit answer markers
        split_at = ResponseCleaner._find_marker_split(text)

        # Strategy 2: Score-based sentence extraction
        if split_at == -1 and len(text) > 200:
            split_at = ResponseCleaner._score_based_split(text)

        # Strategy 3: Last-resort percentage-based cutoff
        if split_at == -1 and len(text) > 500:
            split_at = int(len(text) * 0.55)

        if 0 < split_at < len(text):
            answer = text[split_at:].strip().lstrip('"\'!.,;:? ')
            answer = re.sub(r"^[^a-zA-Z0-9\u0400-\u04FF\u0600-\u06FF\u4E00-\u9FFF]+",
                            "", answer)
            if len(answer) > 20:
                return answer
        return None

    @staticmethod
    def _find_marker_split(text: str) -> int:
        """Find the latest explicit answer marker and split there."""
        best = -1
        for marker in _ANSWER_MARKERS:
            idx = text.rfind(marker)
            if idx > best:
                best = idx + len(marker)
        return best

    @staticmethod
    def _score_based_split(text: str) -> int:
        """
        Score each sentence and find the transition point from
        reasoning-like text to answer-like text.
        """
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) < 3:
            return -1

        scores = []
        for s in sentences:
            s = s.strip()
            if not s:
                scores.append(0)
                continue
            score = ResponseCleaner._sentence_score(s)
            scores.append(score)

        # Find the transition point: where short, direct sentences start
        # after a block of long, reasoning-style sentences
        for i in range(1, len(sentences)):
            prev_avg = sum(scores[:i]) / i if i > 0 else 0
            next_avg = sum(scores[i:]) / (len(scores) - i) if i < len(scores) else 0

            # Higher score = more likely to be an answer (shorter, more direct)
            if next_avg > prev_avg * 1.4 and len(sentences[i].strip()) < 200:
                return len(" ".join(sentences[:i])) + 1

        return -1

    @staticmethod
    def _sentence_score(sentence: str) -> float:
        """
        Score a sentence for "answer-ness".
        Higher = more likely to be a real answer (short, direct, ends with punctuation).
        Lower = more likely to be reasoning (long, starts with connecting words).
        """
        score = 0.0
        s = sentence.strip()

        # Length: short sentences are more likely to be answers
        length = len(s)
        if length < 80:
            score += 3
        elif length < 150:
            score += 1
        elif length > 300:
            score -= 3
        elif length > 200:
            score -= 1

        # Starts with reasoning word = penalty
        if _REASONING_STARTS.match(s):
            score -= 2

        # Ends with punctuation = good
        if _SENTENCE_END.search(s):
            score += 1

        # Contains bullet points or numbered lists = likely answer
        if re.search(r"^\s*(?:[-•*\d]+[.)]\s)", s):
            score += 2

        # Contains code blocks
        if "```" in s:
            score += 1

        return score
