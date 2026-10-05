"""
Unit tests for app/rag/retriever.py.
"""
from app.rag.retriever import get_retriever, _chunk_markdown, KB_DIR


class TestChunking:
    def test_chunk_titles_are_not_all_identical(self):
        """Regression test for a real chunking bug: `$` in the header
        regex without re.MULTILINE required the header line to extend to
        the END OF THE WHOLE STRING (impossible for any non-final
        section), so every section silently fell back to the same
        document-title label. Real chunk titles for a multi-section
        document must be distinct."""
        for md_file in KB_DIR.glob("*.md"):
            chunks = _chunk_markdown(md_file)
            titles = [title for title, _ in chunks]
            if len(titles) > 1:
                assert len(set(titles)) > 1, f"{md_file.name}: all chunk titles identical ({titles[0]!r}) — chunking regressed"

    def test_chunk_titles_reference_their_own_file(self):
        for md_file in KB_DIR.glob("*.md"):
            chunks = _chunk_markdown(md_file)
            for title, _ in chunks:
                assert title.startswith(md_file.name)


class TestRetrieval:
    def test_retriever_is_ready_with_knowledge_base_present(self):
        retriever = get_retriever()
        assert retriever.is_ready() is True
        assert len(retriever._chunks) > 0

    def test_pqc_tls_question_surfaces_the_right_passage(self):
        """This is the real query that caught the chunking bug in the
        first place -- the correct passage explicitly discusses TLS
        being out of scope for the PQC implementation."""
        retriever = get_retriever()
        results = retriever.retrieve("does post-quantum cryptography protect network traffic TLS", top_k=3)
        assert len(results) > 0
        assert any("pqc_scope" in r.source for r in results)

    def test_behavioral_dataset_mismatch_question_surfaces_right_passage(self):
        retriever = get_retriever()
        results = retriever.retrieve("why is behavioral context unavailable for this transaction", top_k=3)
        assert len(results) > 0
        assert any("behavioral_analytics_scope" in r.source for r in results)

    def test_low_relevance_query_returns_few_or_no_results(self):
        retriever = get_retriever()
        results = retriever.retrieve("what is the weather in paris today", top_k=3)
        assert all(r.score < 0.3 for r in results)
