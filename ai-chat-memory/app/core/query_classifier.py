import re
from dataclasses import dataclass


@dataclass
class ProcessedQuery:
    original: str
    complexity: str
    category: str
    needs_memory: bool
    needs_tools: bool
    needs_search: bool
    needs_time: bool
    estimated_tokens: int


class QueryClassifier:

    SIMPLE_PATTERNS = [
        r"^(hi|hello|halo|hey|thanks|ok|oke|terima kasih)",
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

    SEARCH_PATTERNS = [
        r"^cari\s+",
        r"^search\s+",
        r"^google\s+",
        r"(bisa|tolong|coba)?\s*cek (di|ke)\s+(internet|online|web|google)",
        r"cari (tahu|info|berita)",
        r"(berita|news)\s+(terbaru|hari ini|tentang)",
        r"recommend",
        r"rekomendasi",
    ]

    FACTUAL_PATTERNS = [
        r"^(siapa|apa|berapa|kapan|dimana|bagaimana|kenapa|mengapa)",
        r"(berita|news|info terbaru)",
        r"(tanggal|hari)\s+(berapa|apa|ini)",
        r"(cuaca|weather|suhu|temperature)",
        r"(presiden|gubernur|walikota|menteri)\s+(saat ini|sekarang|202\d)",
        r"(populasi|jumlah penduduk|luas)",
        r"(harga|price|rate|kurs)",
        r"(film|buku|musik|lagu|series)\s+terbaru",
        r"rekomendasi",
        r"perbedaan antara",
        r"sejarah",
        r"pengertian",
        r"hijriyah",
    ]

    CURRENT_TIME_PATTERNS = [
        r"(tanggal|date|hari)\s+(berapa|apa|ini|sekarang|skrng|skarang)",
        r"(jam|waktu|time|pukul)\s+(berapa|sekarang|skrng|skarang)",
        r"(sekarang|skrng|skarang)\s+(tanggal|jam|hari)",
        r"(hari|day)\s+(apa|ini|sekarang|skrng)",
        r"what (time|day|date) (is|are)",
    ]

    async def classify(self, message: str) -> ProcessedQuery:
        msg_lower = message.lower().strip()
        word_count = len(message.split())

        complexity = self._detect_complexity(msg_lower, word_count)
        category = self._detect_category(msg_lower)
        needs_memory = any(t in msg_lower for t in self.MEMORY_TRIGGERS)
        needs_tools = any(re.search(p, msg_lower) for p in self.SEARCH_PATTERNS)
        needs_search = needs_tools or any(re.search(p, msg_lower) for p in self.FACTUAL_PATTERNS)
        needs_time = any(re.search(p, msg_lower) for p in self.CURRENT_TIME_PATTERNS)

        if needs_search and complexity == "simple":
            complexity = "moderate"

        return ProcessedQuery(
            original=message,
            complexity=complexity,
            category=category,
            needs_memory=needs_memory,
            needs_tools=needs_tools,
            needs_search=needs_search,
            needs_time=needs_time,
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
