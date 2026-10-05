"""
RAG Investigation Copilot orchestration (Phase 11).

This is the actual RAG pipeline: retrieve real evidence (transaction
risk/SHAP/behavioral/blockchain/security via evidence_service.py, which
is the same code the Transaction Investigation view uses) and real
knowledge-base passages (via retriever.py's TF-IDF search), assemble
them into a grounded context bundle with explicit source citations,
then either:

  (a) hand that context to an LLM with a strict "answer only from this
      context, cite sources, say 'insufficient data' if not covered"
      system prompt — if a provider is configured, or
  (b) return a deterministic, clearly-labeled evidence digest built
      directly from the same retrieved context — if no provider is
      configured.

(b) is not a degraded imitation of (a); it is what "RAG minus the
generation step" honestly looks like. The retrieval and grounding are
real and identical in both paths — only the natural-language synthesis
differs, and no response text is ever presented as AI-generated unless
it actually was.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.rag.llm_provider import LlmProviderCallError, LlmProviderUnavailableError, get_llm_provider
from app.rag.retriever import RetrievedChunk, get_retriever
from app.services.evidence_service import gather_all_evidence

SYSTEM_PROMPT = """You are the QuantumFinGuard Investigation Copilot, assisting a financial fraud/risk analyst.

STRICT RULES:
1. Answer ONLY using the evidence and knowledge-base context provided below. Do not use outside knowledge about fraud detection, blockchain, or cryptography in general.
2. Cite the specific source for every factual claim using its bracketed id, e.g. [risk_assessment] or [kb:pqc_scope.md#What this protects].
3. If the provided context does not contain enough information to answer the question, say exactly: "Insufficient data available to determine this." Do not speculate or fill gaps with general knowledge.
4. Never render a final fraud/no-fraud verdict or tell the analyst what decision to make. Present evidence; the analyst decides.
5. Be concise. This is a working tool for an analyst under time pressure, not an essay.
"""


@dataclass
class CopilotSource:
    id: str
    type: str  # "evidence" | "knowledge_base"
    detail: str


@dataclass
class CopilotResponse:
    mode: str  # "llm_generated" | "evidence_digest"
    answer: str
    sources: list[CopilotSource] = field(default_factory=list)
    llm_provider: str = "none"
    warning: str | None = None


def _format_evidence_context(evidence: dict) -> tuple[str, list[CopilotSource]]:
    lines = []
    sources = []

    risk = evidence["risk_assessment"]
    if risk["status"] == "available":
        lines.append(f"[risk_assessment] Risk score {risk['risk_score']}/100, category={risk['risk_category']}, "
                      f"predicted_class={risk['predicted_class']}, model={risk['model_version']}.")
        sources.append(CopilotSource("risk_assessment", "evidence", f"risk_score={risk['risk_score']}"))
    else:
        lines.append(f"[risk_assessment] NOT AVAILABLE: {risk['reason']}")

    expl = evidence["explanation"]
    if expl["status"] == "available" and expl["top_features"]:
        top_str = "; ".join(f"{f['feature']} ({f['direction']}, contribution={f['contribution']})" for f in expl["top_features"][:5])
        lines.append(f"[explanation] Top SHAP contributing features: {top_str}.")
        sources.append(CopilotSource("explanation", "evidence", f"{len(expl['top_features'])} SHAP features"))
    else:
        lines.append(f"[explanation] NOT AVAILABLE: {expl.get('reason', 'no explanation available')}")

    beh = evidence["behavioral_context"]
    if beh["status"] == "available":
        sig = beh["context"].signals[0] if beh["context"].signals else None
        if sig:
            lines.append(f"[behavioral_context] Deviation {sig.deviation_sigma:+.2f} sigma from baseline "
                          f"(unusual={sig.is_unusual}), baseline_mean={sig.baseline_mean:.2f}, "
                          f"sample_size={beh['context'].history_sample_size}.")
            sources.append(CopilotSource("behavioral_context", "evidence", f"sigma={sig.deviation_sigma:+.2f}"))
    else:
        lines.append(f"[behavioral_context] NOT AVAILABLE: {beh['reason']}")

    bc = evidence["blockchain_context"]
    lines.append(f"[blockchain_context] {bc['status'].upper()}: {bc['reason']}")

    sec = evidence["security_context"]
    if sec["status"] == "available":
        integrity = "intact" if sec["hash_recomputation_matches"] else "MISMATCH (possible tampering)"
        lines.append(f"[security_context] Record integrity: {integrity}. chain_sequence={sec['chain_sequence']}.")
        sources.append(CopilotSource("security_context", "evidence", f"integrity={integrity}"))
    else:
        lines.append("[security_context] NOT AVAILABLE (record not sealed).")

    return "\n".join(lines), sources


def _format_kb_context(chunks: list[RetrievedChunk]) -> tuple[str, list[CopilotSource]]:
    if not chunks:
        return "(No knowledge base passages matched this question closely enough to include.)", []
    lines = []
    sources = []
    for chunk in chunks:
        cid = f"kb:{chunk.source}"
        lines.append(f"[{cid}] (relevance={chunk.score}) {chunk.text}")
        sources.append(CopilotSource(cid, "knowledge_base", f"relevance={chunk.score}"))
    return "\n\n".join(lines), sources


def _build_evidence_digest(question: str, evidence_context: str, kb_context: str, has_transaction: bool) -> str:
    """The honest non-LLM fallback: a structured presentation of exactly
    what was retrieved, with no synthesized narrative. This is real RAG
    output (retrieval + grounding) minus the generation step, clearly
    labeled as such."""
    parts = [
        "LLM PROVIDER NOT CONFIGURED — showing retrieved evidence directly. "
        "No natural-language synthesis has been performed; nothing below is AI-generated.",
        "",
        f"Question: {question}",
        "",
    ]
    if has_transaction:
        parts.append("--- Transaction evidence retrieved ---")
        parts.append(evidence_context)
        parts.append("")
    parts.append("--- Knowledge base passages retrieved ---")
    parts.append(kb_context)
    return "\n".join(parts)


class CopilotService:
    def ask(self, db: Session, question: str, transaction: Transaction | None = None) -> CopilotResponse:
        evidence_context = ""
        evidence_sources: list[CopilotSource] = []
        if transaction is not None:
            evidence = gather_all_evidence(db, transaction)
            evidence_context, evidence_sources = _format_evidence_context(evidence)

        kb_chunks = get_retriever().retrieve(question, top_k=3)
        kb_context, kb_sources = _format_kb_context(kb_chunks)

        all_sources = evidence_sources + kb_sources

        provider = get_llm_provider()
        if not provider.is_configured():
            digest = _build_evidence_digest(question, evidence_context, kb_context, transaction is not None)
            return CopilotResponse(
                mode="evidence_digest",
                answer=digest,
                sources=all_sources,
                llm_provider="none",
                warning="No LLM provider configured (ANTHROPIC_API_KEY unset). This is a retrieved-evidence "
                        "digest, not an AI-generated response.",
            )

        user_prompt = (
            f"Analyst question: {question}\n\n"
            f"--- Transaction evidence ---\n{evidence_context or '(No transaction specified.)'}\n\n"
            f"--- Knowledge base context ---\n{kb_context}"
        )
        try:
            answer = provider.generate(SYSTEM_PROMPT, user_prompt)
            return CopilotResponse(mode="llm_generated", answer=answer, sources=all_sources, llm_provider=provider.provider_name)
        except (LlmProviderUnavailableError, LlmProviderCallError) as exc:
            digest = _build_evidence_digest(question, evidence_context, kb_context, transaction is not None)
            return CopilotResponse(
                mode="evidence_digest", answer=digest, sources=all_sources, llm_provider=provider.provider_name,
                warning=f"LLM call failed, falling back to evidence digest: {exc}",
            )


def get_copilot_service() -> CopilotService:
    return CopilotService()
