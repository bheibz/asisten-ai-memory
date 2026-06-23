import json
import re

from app.llm.gateway import llm_gateway


class FactExtractor:

    async def extract(self, user_msg: str, ai_response: str) -> list[dict]:
        facts = []

        facts.extend(self._extract_name(user_msg))
        facts.extend(self._extract_preference(user_msg))
        facts.extend(self._extract_key_value(user_msg))

        if len(facts) < 3:
            llm_facts = await self._extract_llm(user_msg)
            for f in llm_facts:
                if not any(existing.get("key") == f.get("key") and existing.get("value") == f.get("value") for existing in facts):
                    facts.append(f)

        return facts[:5]

    async def _extract_llm(self, text: str) -> list[dict]:
        if len(text.strip()) < 10:
            return []
        prompt = (
            f"Extract facts from this text. Return ONLY a JSON array. "
            f"Each item: {{\"type\":\"personal|preference|knowledge\",\"key\":\"...\",\"value\":\"...\"}}\n\n"
            f"Text: {text[:500]}"
        )
        try:
            result = await llm_gateway.complete(model="google/gemini-2.0-flash-exp:free", prompt=prompt, max_tokens=150)
            return self._parse(result)
        except Exception:
            return []

    def _parse(self, text: str) -> list[dict]:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("\n```", 1)[0]
        text = text.strip()
        if text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return []

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
                results.append({"type": "personal", "key": "info", "value": m.group(0)})
        return results
