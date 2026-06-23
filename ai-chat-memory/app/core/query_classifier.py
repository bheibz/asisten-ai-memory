import re
from dataclasses import dataclass


@dataclass
class ProcessedQuery:
    original: str
    complexity: str
    category: str
    needs_memory: bool
    needs_tools: bool
    estimated_tokens: int


class QueryClassifier:

    SIMPLE_PATTERNS = [
        r"^(hi|hello|halo|hey|thanks|ok|oke|terima kasih)",
        r"^(apa itu|what is|siapa|who is) \w{1,20}$",
        r"^(ya|tidak|yes|no|iya|bukan)$",
    ]

    COMPLEX_PATTERNS = [
        r"(buatkan|buat|create|build|develop|implement)",
        r"(analisis|analyze|compare|bandingkan|evaluasi)",
        r"(jelaskan secara detail|explain in detail|step by step)",
        r"(debug|fix|refactor|optimize)",
        r"(essay|artikel|paper|laporan|report)",
    ]

    CODING_PATTERNS = [
        r"(code|kode|function|fungsi|class|api|database|sql|python|javascript)",
        r"(bug|error|exception|traceback)",
    ]

    MEMORY_TRIGGERS = [
        "kemarin", "sebelumnya", "yang tadi", "ingat",
        "remember", "previously", "last time", "you said",
        "seperti yang", "sudah pernah", "yang lalu",
    ]

    SEARCH_TRIGGERS = [
        "cari", "search", "google", "cari tahu", "find", "look up",
        "berita", "news", "info", "informasi", "information",
        "apa yang terbaru", "what is", "siapa", "who is",
        "berapa", "kapan", "dimana", "where", "when",
        "rekomendasi", "recommendation", "review",
    ]

    async def classify(self, message: str) -> ProcessedQuery:
        msg_lower = message.lower().strip()
        word_count = len(message.split())

        complexity = self._detect_complexity(msg_lower, word_count)
        category = self._detect_category(msg_lower)
        needs_memory = any(t in msg_lower for t in self.MEMORY_TRIGGERS)
        needs_tools = any(t in msg_lower for t in self.SEARCH_TRIGGERS)

        return ProcessedQuery(
            original=message,
            complexity=complexity,
            category=category,
            needs_memory=needs_memory,
            needs_tools=needs_tools,
            estimated_tokens=int(word_count * 1.5),
        )

    def _detect_complexity(self, msg: str, word_count: int) -> str:
        if word_count < 10 and any(re.match(p, msg) for p in self.SIMPLE_PATTERNS):
            return "simple"
        if any(re.search(p, msg) for p in self.COMPLEX_PATTERNS):
            return "complex"
        if word_count > 50:
            return "complex"
        return "moderate"

    def _detect_category(self, msg: str) -> str:
        if any(re.search(p, msg) for p in self.CODING_PATTERNS):
            return "coding"
        if any(w in msg for w in ["tulis", "write", "cerita", "story", "puisi", "poem"]):
            return "writing"
        if any(w in msg for w in ["cari", "search", "research", "analisis", "analyze"]):
            return "research"
        return "casual"
