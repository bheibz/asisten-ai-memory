import asyncio
from duckduckgo_search import DDGS


class WebSearch:

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        try:
            results = await asyncio.to_thread(self._sync_search, query, max_results)
            return [
                {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
                for r in results
            ]
        except Exception as e:
            return [{"title": "Search error", "url": "", "snippet": f"Gagal search: {e}"}]

    def _sync_search(self, query: str, max_results: int) -> list:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))

    def format_for_prompt(self, results: list[dict], query: str = "") -> str:
        lines = ["[WEB SEARCH RESULTS]"]
        if not results:
            lines.append(f"Pencarian untuk \"{query}\" tidak menemukan hasil.")
            lines.append("Kamu bisa bilang ke user bahwa search tidak menemukan hasil.")
            return "\n".join(lines)
        for i, r in enumerate(results[:5], 1):
            snippet = r["snippet"][:300]
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   {snippet}")
            if r["url"]:
                lines.append(f"   Source: {r['url']}")
        return "\n".join(lines)


web_search = WebSearch()
