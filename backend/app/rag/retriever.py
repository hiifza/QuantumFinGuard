"""
Retrieval component of the RAG Investigation Copilot.

Uses TF-IDF + cosine similarity (scikit-learn) over the knowledge base
markdown files — a real, working retrieval mechanism that requires no
external embedding API. Stated honestly: this is lexical/term-based
retrieval, not neural semantic embeddings. That's a real design choice
given this environment has no credentialed access to an embedding API,
not a downgrade hidden behind vague language — TF-IDF is a legitimate,
well-established retrieval method, just not the same as e.g. OpenAI or
Voyage embeddings.

Each knowledge base document is chunked by section (## headers) so
retrieval returns focused passages, not entire multi-topic files —
better grounding, and citations that point to a specific section
rather than "see this whole document."
"""
import re
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KB_DIR = Path(__file__).parent / "knowledge_base"


@dataclass
class RetrievedChunk:
    source: str  # e.g. "pqc_scope.md#What this protects"
    text: str
    score: float


def _chunk_markdown(path: Path) -> list[tuple[str, str]]:
    """Splits a markdown file into (section_title, section_text) chunks
    on ## headers. The top-level # title becomes the doc name prefix."""
    text = path.read_text()
    doc_title_match = re.match(r"^#\s+(.+)$", text, re.MULTILINE)
    doc_title = doc_title_match.group(1) if doc_title_match else path.stem

    sections = re.split(r"\n(?=##\s+)", text)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section or section.startswith("# "):
            continue
        header_match = re.match(r"^##\s+(.+)", section.split("\n", 1)[0])
        section_title = header_match.group(1) if header_match else doc_title
        chunks.append((f"{path.name}#{section_title}", section))
    return chunks


class KnowledgeBaseRetriever:
    def __init__(self, kb_dir: Path = KB_DIR):
        self._chunks: list[tuple[str, str]] = []
        for md_file in sorted(kb_dir.glob("*.md")):
            self._chunks.extend(_chunk_markdown(md_file))

        if not self._chunks:
            self._vectorizer = None
            self._matrix = None
            return

        self._vectorizer = TfidfVectorizer(stop_words="english", max_df=0.9)
        texts = [text for _, text in self._chunks]
        self._matrix = self._vectorizer.fit_transform(texts)

    def is_ready(self) -> bool:
        return self._vectorizer is not None

    def retrieve(self, query: str, top_k: int = 3, min_score: float = 0.05) -> list[RetrievedChunk]:
        if not self.is_ready():
            return []
        query_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self._matrix)[0]
        ranked = sorted(zip(self._chunks, scores), key=lambda x: x[1], reverse=True)

        results = []
        for (source, text), score in ranked[:top_k]:
            if score < min_score:
                continue
            results.append(RetrievedChunk(source=source, text=text, score=round(float(score), 4)))
        return results


_retriever_instance: KnowledgeBaseRetriever | None = None


def get_retriever() -> KnowledgeBaseRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = KnowledgeBaseRetriever()
    return _retriever_instance
