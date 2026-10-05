import { useState, type FormEvent } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { investigationApi, transactionsApi, fraudApi, copilotApi } from '../api/endpoints'
import { Card } from '../components/ui/Card'
import { LoadingBlock, ErrorBlock, UnavailableBlock, StatusPill } from '../components/ui/States'
import type { ShapFeatureContribution } from '../api/types'

function EvidenceSection({ title, stage, children }: { title: string; stage: string; children: React.ReactNode }) {
  return (
    <Card className="p-5">
      <div className="mb-3 flex items-baseline justify-between">
        <div className="text-[13px] font-semibold">{title}</div>
        <div className="text-[10px] tracking-wider" style={{ color: 'var(--text-dim)' }}>
          {stage}
        </div>
      </div>
      {children}
    </Card>
  )
}

function ShapBar({ feature }: { feature: ShapFeatureContribution }) {
  const isRisk = feature.direction === 'increases_risk'
  const width = Math.min(100, Math.abs(feature.contribution) * 400)
  return (
    <div className="mb-2.5">
      <div className="mb-1 flex items-center justify-between text-[12px]">
        <span className="font-mono" style={{ color: 'var(--text)' }}>
          {feature.feature}
        </span>
        <span style={{ color: isRisk ? 'var(--coral)' : 'var(--emerald)' }}>
          {feature.contribution > 0 ? '+' : ''}
          {feature.contribution.toFixed(4)}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full" style={{ background: 'var(--surface-2)' }}>
        <div
          className="h-full rounded-full"
          style={{ width: `${width}%`, background: isRisk ? 'var(--coral)' : 'var(--emerald)' }}
        />
      </div>
    </div>
  )
}

function InvestigationPicker() {
  const [inputId, setInputId] = useState('')
  const navigate = useNavigate()
  const recent = useQuery({ queryKey: ['transactions', 'recent-picker'], queryFn: () => transactionsApi.list({ page: 1, page_size: 8 }) })

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (inputId.trim()) navigate(`/investigation/${inputId.trim()}`)
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-1 text-[11px]" style={{ color: 'var(--emerald)' }}>
        Investigation
      </div>
      <h1 className="font-serif text-2xl">Open a transaction</h1>
      <p className="mt-2 text-[13px]" style={{ color: 'var(--text-dim)' }}>
        Enter a transaction ID, or pick one from the recently ingested transactions below.
      </p>

      <form onSubmit={handleSubmit} className="mt-5 flex gap-2">
        <input
          value={inputId}
          onChange={(e) => setInputId(e.target.value)}
          placeholder="Transaction ID…"
          className="flex-1 rounded-md border px-3 py-2 text-sm outline-none font-mono"
          style={{ background: 'var(--surface)', borderColor: 'var(--line)', color: 'var(--text)' }}
        />
        <button
          type="submit"
          className="rounded-md px-4 py-2 text-sm font-semibold"
          style={{ background: 'var(--emerald)', color: '#0A0E13' }}
        >
          Open
        </button>
      </form>

      <div className="mt-6">
        {recent.isLoading ? (
          <LoadingBlock />
        ) : recent.error ? (
          <ErrorBlock error={recent.error} />
        ) : (
          <Card className="divide-y" style={{ borderColor: 'var(--line)' }}>
            {recent.data!.items.map((txn) => (
              <button
                key={txn.id}
                onClick={() => navigate(`/investigation/${txn.id}`)}
                className="flex w-full items-center justify-between px-4 py-3 text-left text-[13px] transition-colors"
                style={{ borderColor: 'var(--line)' }}
              >
                <span className="font-mono" style={{ color: 'var(--text-dim)' }}>
                  {txn.id.slice(0, 12)}…
                </span>
                <span>{txn.customer_id}</span>
                <span className="font-mono">${txn.amount.toFixed(2)}</span>
              </button>
            ))}
          </Card>
        )}
      </div>
    </div>
  )
}

function InvestigationDetail({ transactionId }: { transactionId: string }) {
  const queryClient = useQueryClient()
  const [question, setQuestion] = useState('')

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['investigation', transactionId],
    queryFn: () => investigationApi.get(transactionId),
  })

  const scoreMutation = useMutation({
    mutationFn: () => fraudApi.score(transactionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['investigation', transactionId] }),
  })

  const copilotMutation = useMutation({
    mutationFn: (q: string) => copilotApi.ask(q, transactionId),
  })

  if (isLoading) return <LoadingBlock label="Assembling investigation evidence…" />
  if (error) return <ErrorBlock error={error} onRetry={refetch} />
  if (!data) return null

  const { transaction, risk_assessment, explanation, behavioral_context, blockchain_context, security_context, investigation_summary } = data

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-1 text-[11px]" style={{ color: 'var(--emerald)' }}>
        Investigation
      </div>
      <h1 className="font-serif text-2xl">Transaction {transaction.id.slice(0, 12)}…</h1>

      {/* Identity strip */}
      <div className="mt-4 grid grid-cols-4 gap-3 text-[13px]">
        <div>
          <div className="text-[11px]" style={{ color: 'var(--text-dim)' }}>Amount</div>
          <div className="font-mono">${transaction.amount.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-[11px]" style={{ color: 'var(--text-dim)' }}>Customer</div>
          <div>{transaction.customer_id}</div>
        </div>
        <div>
          <div className="text-[11px]" style={{ color: 'var(--text-dim)' }}>Merchant category</div>
          <div>{transaction.merchant_category ?? '—'}</div>
        </div>
        <div>
          <div className="text-[11px]" style={{ color: 'var(--text-dim)' }}>Timestamp</div>
          <div>{new Date(transaction.timestamp).toLocaleString()}</div>
        </div>
      </div>

      {/* Summary banner */}
      <Card elevated className="mt-5 p-5">
        <div className="mb-1.5 text-[11px]" style={{ color: 'var(--text-dim)' }}>
          Auto-assembled evidence summary — not AI-generated, not a fraud determination
        </div>
        <p className="text-[14px] leading-relaxed">{investigation_summary}</p>
      </Card>

      <div className="mt-4 grid grid-cols-2 gap-4">
        <EvidenceSection title="Risk assessment" stage="WHAT">
          {risk_assessment.status === 'available' ? (
            <div>
              <div className="flex items-baseline gap-2">
                <span className="font-serif text-3xl">{risk_assessment.risk_score}</span>
                <span style={{ color: 'var(--text-dim)' }}>/100</span>
                <StatusPill
                  tone={
                    risk_assessment.risk_category === 'high'
                      ? 'coral'
                      : risk_assessment.risk_category === 'medium'
                        ? 'amber'
                        : 'emerald'
                  }
                >
                  {risk_assessment.risk_category}
                </StatusPill>
              </div>
              <div className="mt-2 text-[12px]" style={{ color: 'var(--text-dim)' }}>
                {risk_assessment.predicted_class} · model {risk_assessment.model_version}
              </div>
            </div>
          ) : (
            <div>
              <UnavailableBlock reason={risk_assessment.reason ?? 'Not available.'} />
              <button
                onClick={() => scoreMutation.mutate()}
                disabled={scoreMutation.isPending}
                className="mt-3 rounded-md border px-3 py-1.5 text-xs font-medium disabled:opacity-50"
                style={{ borderColor: 'var(--line)' }}
              >
                {scoreMutation.isPending ? 'Scoring…' : 'Try scoring now'}
              </button>
              {scoreMutation.isError && <ErrorBlock error={scoreMutation.error} />}
            </div>
          )}
        </EvidenceSection>

        <EvidenceSection title="Explanation" stage="WHY">
          {explanation.status === 'available' && explanation.top_features ? (
            <div>
              {explanation.top_features.slice(0, 5).map((f, i) => (
                <ShapBar key={i} feature={f} />
              ))}
            </div>
          ) : (
            <UnavailableBlock reason={explanation.reason ?? 'Not available.'} />
          )}
        </EvidenceSection>

        <EvidenceSection title="Behavioral context" stage="CONTEXTUALIZE">
          {behavioral_context.status === 'available' && behavioral_context.context ? (
            <div className="space-y-2">
              {behavioral_context.context.signals.map((sig, i) => {
                const sampleSize = behavioral_context.context!.history_sample_size
                return (
                  <div key={i}>
                    <div className="flex items-center justify-between text-[13px]">
                      <span style={{ color: 'var(--text-dim)' }}>{sig.name.replace(/_/g, ' ')}</span>
                      <StatusPill tone={sig.is_unusual ? 'coral' : 'emerald'}>
                        {sig.deviation_sigma > 0 ? '+' : ''}
                        {sig.deviation_sigma.toFixed(2)}σ
                      </StatusPill>
                    </div>
                    <div className="mt-1 text-[11px]" style={{ color: 'var(--text-dim)' }}>
                      baseline mean ${sig.baseline_mean.toFixed(2)} · {sampleSize} historical transactions
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <UnavailableBlock reason={behavioral_context.reason ?? 'Not available.'} />
          )}
        </EvidenceSection>

        <EvidenceSection title="Blockchain context" stage="INVESTIGATE">
          <UnavailableBlock reason={blockchain_context.reason ?? 'Not applicable.'} tone="muted" />
        </EvidenceSection>

        <EvidenceSection title="Security & integrity" stage="SECURE">
          {security_context.status === 'available' ? (
            <div>
              <div className="flex items-center gap-2">
                <StatusPill tone={security_context.hash_recomputation_matches ? 'emerald' : 'coral'}>
                  {security_context.hash_recomputation_matches ? 'Integrity intact' : 'MISMATCH DETECTED'}
                </StatusPill>
              </div>
              <div className="mt-2 space-y-1 font-mono text-[11px]" style={{ color: 'var(--text-dim)' }}>
                <div>sequence: {security_context.chain_sequence}</div>
                <div>hash: {security_context.record_hash?.slice(0, 24)}…</div>
              </div>
              <p className="mt-2 text-[11px]" style={{ color: 'var(--text-dim)' }}>{security_context.note}</p>
            </div>
          ) : (
            <UnavailableBlock reason="Record not sealed." />
          )}
        </EvidenceSection>

        <EvidenceSection title="Investigation copilot" stage="DECIDE">
          <div className="space-y-2">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask about this transaction's evidence…"
              rows={2}
              className="w-full resize-none rounded-md border px-3 py-2 text-[13px] outline-none"
              style={{ background: 'var(--surface-2)', borderColor: 'var(--line)', color: 'var(--text)' }}
            />
            <button
              onClick={() => question.trim() && copilotMutation.mutate(question)}
              disabled={copilotMutation.isPending || !question.trim()}
              className="rounded-md border px-3 py-1.5 text-xs font-medium disabled:opacity-50"
              style={{ borderColor: 'var(--line)' }}
            >
              {copilotMutation.isPending ? 'Thinking…' : 'Ask'}
            </button>
            {copilotMutation.data && (
              <div className="rounded-md p-3 text-[12.5px]" style={{ background: 'var(--surface-2)' }}>
                {copilotMutation.data.warning && (
                  <div className="mb-2 text-[11px]" style={{ color: 'var(--amber)' }}>
                    {copilotMutation.data.warning}
                  </div>
                )}
                <div className="whitespace-pre-wrap">{copilotMutation.data.answer}</div>
              </div>
            )}
          </div>
        </EvidenceSection>
      </div>
    </div>
  )
}

export function InvestigationPage() {
  const { transactionId } = useParams<{ transactionId: string }>()
  if (!transactionId) return <InvestigationPicker />
  return <InvestigationDetail transactionId={transactionId} />
}
