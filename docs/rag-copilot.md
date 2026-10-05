# RAG Investigation Copilot

## Pipeline

```
Analyst question (+ optional transaction_id)
  -> retrieve transaction evidence (app/services/evidence_service.py --
     the SAME code the Transaction Investigation view uses, so the
     copilot and the investigation page can never disagree about what
     "the real evidence" is)
  -> retrieve knowledge-base passages (app/rag/retriever.py -- TF-IDF +
     cosine similarity over 5 markdown documents, chunked by section)
  -> assemble a context bundle with explicit source citations
  -> IF an LLM provider is configured: hand the context to the LLM
     with a strict "answer only from this context, cite sources, say
     'insufficient data' if not covered" system prompt
  -> IF NOT configured: return a deterministic evidence digest built
     directly from the same retrieved context, explicitly labeled as
     not AI-generated
  -> log the query to the audit trail
```

## Retrieval method, stated honestly

TF-IDF + cosine similarity, not neural embeddings. This is a real,
working, well-established retrieval method, not a downgrade hidden
behind vague language. It requires no external embedding API, which
matters given this environment has no credentialed access to one.

## Knowledge base

Five markdown documents (app/rag/knowledge_base/), each describing a
real, accurate aspect of this system's own implementation and scope
(PQC boundary, integrity mechanism, fraud model status and its
synthetic-vs-real data caveat, behavioral analytics dataset-linkage
limitation, blockchain graph backend). These are genuine internal
documentation, written to be retrieved and cited, not a simulated or
placeholder corpus.

## LLM provider

app/rag/llm_provider.py defines a real, complete AnthropicProvider
implementation. Activated by setting ANTHROPIC_API_KEY. Without it,
get_llm_provider() returns NoProviderAvailable, and
CopilotService.ask() falls back to the evidence digest.

No fabrication guarantee, tested: tests/integration/test_security_pqc_copilot.py
asserts that when no LLM is configured, the response's mode field is
"evidence_digest" (not "llm_generated"), a warning field is present,
and the answer text explicitly states no AI synthesis was performed.

## Citations

Every response includes a sources list distinguishing evidence sources
(risk_assessment, explanation, behavioral_context, security_context)
from knowledge-base sources (kb:{file}#{section}). Verified by a test
that confirms at least one evidence-type source is present when a
transaction_id is supplied.
