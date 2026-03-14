from __future__ import annotations

import hashlib
import importlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

from backend.config import Settings


@dataclass
class RetrievalCandidate:
    source: str
    text: str
    score: float


class DashScopeEmbeddings:
    """Embedding client backed by DashScope's OpenAI-compatible embedding API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        batch_size = 16
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            vectors.extend(self._embed(batch))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        vectors = self._embed([text])
        if not vectors:
            raise RuntimeError("DashScope embedding API returned no vectors")
        return vectors[0]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not self._settings.qwen_api_key:
            raise RuntimeError("QWEN_API_KEY is empty")

        url = f"{self._settings.qwen_api_base.rstrip('/')}/embeddings"
        payload = json.dumps(
            {
                "model": self._settings.qwen_embedding_model,
                "input": texts,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._settings.qwen_api_key}",
        }
        req = request.Request(url=url, data=payload, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self._settings.rag_timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("DashScope embedding API call failed") from exc

        data = body.get("data", [])
        if not isinstance(data, list):
            raise RuntimeError("Unexpected embedding response format")

        ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
        vectors = [item.get("embedding", []) for item in ordered]
        if any(not isinstance(vec, list) or not vec for vec in vectors):
            raise RuntimeError("Embedding response contains empty vectors")
        return vectors


class LangChainRAGService:
    """RAG service with native ChromaDB retrieval plus offline keyword fallback."""

    def __init__(self, settings: Settings, knowledge_dir: Path) -> None:
        self._settings = settings
        self._knowledge_dir = knowledge_dir
        self._token_pattern = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]+")
        self._documents = self._load_documents()
        self._chunks = self._build_chunks(self._documents)
        self._docs_hash = self._build_docs_hash(self._chunks)
        self._embedding_client = DashScopeEmbeddings(settings)
        self._chromadb = None
        self._client = None
        self._collection = None

    def search(
        self,
        query: str,
        top_k: int = 3,
        *,
        network_online: bool = False,
        allow_rerank: bool | None = None,
    ) -> list[str]:
        query = query.strip()
        if not query or not self._chunks:
            return []

        limit = max(1, top_k)
        fetch_k = max(limit, self._settings.rag_fetch_k)
        candidates: list[RetrievalCandidate] = []

        if network_online and bool(self._settings.qwen_api_key):
            candidates = self._vector_retrieve(query, fetch_k)
        if not candidates:
            candidates = self._keyword_retrieve(query, fetch_k)

        if allow_rerank is None:
            allow_rerank = self._settings.qwen_enable_rerank
        if allow_rerank and network_online and bool(self._settings.qwen_api_key):
            reranked = self._rerank(query, candidates, limit)
            if reranked:
                candidates = reranked

        return [self._format_candidate(item) for item in candidates[:limit]]

    def _vector_retrieve(self, query: str, top_k: int) -> list[RetrievalCandidate]:
        if not self._ensure_vectorstore() or self._collection is None:
            return []

        try:
            query_embedding = self._embedding_client.embed_query(query)
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            return []

        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]
        ranked: list[RetrievalCandidate] = []
        for text, metadata, distance in zip(documents, metadatas, distances):
            ranked.append(
                RetrievalCandidate(
                    source=str((metadata or {}).get("source", "knowledge-base")),
                    text=str(text),
                    score=1.0 / (1.0 + float(distance or 0.0)),
                )
            )

        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked

    def _keyword_retrieve(self, query: str, top_k: int) -> list[RetrievalCandidate]:
        query_tokens = set(self._tokenize(query))
        if not query_tokens:
            return []

        scored: list[RetrievalCandidate] = []
        for chunk in self._chunks:
            tokens = set(self._tokenize(chunk["text"]))
            overlap = len(query_tokens.intersection(tokens))
            if overlap <= 0:
                continue
            scored.append(
                RetrievalCandidate(
                    source=chunk["source"],
                    text=chunk["text"],
                    score=float(overlap),
                )
            )

        if not scored:
            return [
                RetrievalCandidate(source=chunk["source"], text=chunk["text"], score=0.0)
                for chunk in self._chunks[:top_k]
            ]

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    def _rerank(self, query: str, candidates: list[RetrievalCandidate], top_k: int) -> list[RetrievalCandidate]:
        if not candidates or not self._settings.qwen_rerank_api or not self._settings.qwen_api_key:
            return []

        payload = json.dumps(
            {
                "model": self._settings.qwen_rerank_model,
                "input": {
                    "query": query,
                    "documents": [item.text for item in candidates],
                },
                "parameters": {
                    "top_n": min(len(candidates), max(top_k, self._settings.rag_fetch_k)),
                    "return_documents": False,
                },
            },
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._settings.qwen_api_key}",
        }
        req = request.Request(
            url=self._settings.qwen_rerank_api,
            data=payload,
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self._settings.rag_timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
            return []

        results = self._extract_rerank_results(body)
        if not results:
            return []

        ranked: list[RetrievalCandidate] = []
        for row in results:
            idx = row.get("index")
            if not isinstance(idx, int) or idx < 0 or idx >= len(candidates):
                continue
            score = float(row.get("relevance_score", row.get("score", 0.0)))
            item = candidates[idx]
            ranked.append(RetrievalCandidate(source=item.source, text=item.text, score=score))

        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked or candidates

    @staticmethod
    def _extract_rerank_results(body: dict[str, Any]) -> list[dict[str, Any]]:
        output = body.get("output")
        if isinstance(output, dict) and isinstance(output.get("results"), list):
            return output["results"]
        if isinstance(body.get("results"), list):
            return body["results"]
        if isinstance(body.get("data"), list):
            return body["data"]
        return []

    def _load_chromadb(self):
        if self._chromadb is False:
            return None
        if self._chromadb is not None:
            return self._chromadb
        try:
            self._chromadb = importlib.import_module("chromadb")
        except Exception:
            self._chromadb = False
            return None
        return self._chromadb

    def _ensure_vectorstore(self) -> bool:
        if self._collection is not None:
            return True

        chromadb_module = self._load_chromadb()
        if chromadb_module is None or not self._chunks:
            return False

        collection_name = f"health_kb_{self._docs_hash[:16]}"
        try:
            self._client = chromadb_module.PersistentClient(path=self._settings.chroma_path)
            self._collection = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"docs_hash": self._docs_hash},
            )
            if self._collection.count() == 0:
                texts = [chunk["text"] for chunk in self._chunks]
                embeddings = self._embedding_client.embed_documents(texts)
                self._collection.add(
                    ids=[chunk["chunk_id"] for chunk in self._chunks],
                    documents=texts,
                    metadatas=[{"source": chunk["source"], "chunk_id": chunk["chunk_id"]} for chunk in self._chunks],
                    embeddings=embeddings,
                )
            return True
        except Exception:
            self._client = None
            self._collection = None
            return False

    def _load_documents(self) -> list[tuple[str, str]]:
        if not self._knowledge_dir.exists():
            return []

        documents: list[tuple[str, str]] = []
        for path in sorted(self._knowledge_dir.glob("*.md")):
            content = path.read_text(encoding="utf-8").strip()
            if content:
                documents.append((path.name, content))
        return documents

    def _build_chunks(self, documents: list[tuple[str, str]]) -> list[dict[str, str]]:
        chunk_size = max(200, self._settings.rag_chunk_size)
        overlap = max(0, min(self._settings.rag_chunk_overlap, chunk_size - 1))
        chunks: list[dict[str, str]] = []

        for source, content in documents:
            start = 0
            chunk_idx = 0
            while start < len(content):
                end = min(len(content), start + chunk_size)
                text = content[start:end].strip()
                if text:
                    chunks.append(
                        {
                            "source": source,
                            "chunk_id": f"{source}:{chunk_idx}",
                            "text": text,
                        }
                    )
                    chunk_idx += 1

                if end >= len(content):
                    break
                start = max(start + 1, end - overlap)
        return chunks

    @staticmethod
    def _build_docs_hash(chunks: list[dict[str, str]]) -> str:
        digest = hashlib.sha1()
        for chunk in chunks:
            digest.update(chunk["chunk_id"].encode("utf-8"))
            digest.update(chunk["text"].encode("utf-8"))
        return digest.hexdigest()

    def _tokenize(self, text: str) -> list[str]:
        return self._token_pattern.findall(text.lower())

    @staticmethod
    def _format_candidate(item: RetrievalCandidate) -> str:
        excerpt = item.text[:900].strip()
        return f"[{item.source}]\n{excerpt}"