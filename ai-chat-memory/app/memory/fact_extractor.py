import json
import re


class FactExtractor:

    async def extract(self, user_msg: str, ai_response: str) -> list[dict]:
        facts = []

        facts.extend(self._extract_name(user_msg))
        facts.extend(self._extract_preference(user_msg))
        facts.extend(self._extract_key_value(user_msg))

        return facts

    def _extract_name(self, text: str) -> list[dict]:
        patterns = [
            r"(?:namaku|nama saya|nama aku|my name is|i'm called)\s+(\w+)",
            r"(?:panggil)\s+(?:aku|saya)\s+(\w+)",
        ]
        results = []
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                results.append({"type": "personal", "key": "nama", "value": m.group(1)})
        return results

    def _extract_preference(self, text: str) -> list[dict]:
        patterns = [
            r"(?:aku|saya)\s+(?:suka|gemar|hobi)\s+(\w+(?:\s+\w+)?)",
            r"(?:i like|i love|i prefer|i enjoy)\s+(\w+(?:\s+\w+)?)",
            r"(?:suka|like)\s+(\w+(?:\s+\w+)?)",
        ]
        results = []
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m and len(m.group(1)) > 2:
                results.append({"type": "preference", "key": "suka", "value": m.group(1)})
        return results

    def _extract_key_value(self, text: str) -> list[dict]:
        patterns = [
            r"(?:hutang|utang)\s+(\w+(?:\s+\d+)?)",
            r"(?:umur|usia)\s+(\d+)",
            r"(?:tinggal|domisili|alamat)\s+(\w+(?:\s+\w+)?)",
            r"(?:kerja|bekerja)\s+(?:sebagai|di)\s+(\w+(?:\s+\w+)?)",
        ]
        results = []
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                key = p.split(r"\(")[0].strip("?:")
                results.append({"type": "personal", "key": "info", "value": m.group(0)})
        return results
