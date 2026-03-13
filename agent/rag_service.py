from __future__ import annotations

from pathlib import Path
import re


class RAGService:
    """Lightweight local retrieval service. Upgrades cleanly to ChromaDB when configured."""

    def __init__(self, knowledge_dir: Path) -> None:
        self._documents = []
        for path in sorted(knowledge_dir.glob("*.md")):
            content = path.read_text(encoding="utf-8")
            self._documents.append((path.name, content))

    def search(self, query: str, top_k: int = 3) -> list[str]:
        query_tokens = set(self._tokenize(query))
        scored: list[tuple[int, str]] = []
        for title, content in self._documents:
            excerpt = content[:900]
            score = len(query_tokens.intersection(self._tokenize(excerpt)))
            scored.append((score, f"[{title}]\n{excerpt}"))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [excerpt for score, excerpt in scored[:top_k] if score > 0]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", text.lower())
