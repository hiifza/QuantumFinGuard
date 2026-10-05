import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { dataApi, fraudApi, blockchainApi, securityApi, copilotApi, transactionsApi } from '../api/endpoints'
import { Card } from '../components/ui/Card'
import { LoadingBlock, ErrorBlock, StatusPill } from '../components/ui/States'
import { RiskOrb } from '../components/three/RiskOrb'

function MetricCard({
  label,
  value,
  sub,
  loading,
  error,
}: {
  label: string
  value: string | null
  sub?: string
  loading: boolean
  error: unknown
}) {
  return (
    <Card className="p-5">
      <div className="text-[11.5px]" style={{ color: 'var(--text-dim)' }}>
        {label}
      </div>
      {loading ? (
        <div className="mt-3">
          <LoadingBlock label="" />
        </div>
      ) : error ? (
        <div className="mt-2 text-[12px]" style={{ color: 'var(--coral)' }}>
          Unavailable
        </div>
      ) : (
        <>
          <div className="mt-1.5 font-serif text-[27px] font-medium">{value}</div>
          {sub && (
            <div className="mt-1 text-[11px]" style={{ color: 'var(--text-dim)' }}>
              {sub}
            </div>
          )}
        </>
      )}
    </Card>
  )
}

export function OverviewPage() {
  const sourceBreakdown = useQuery({ queryKey: ['data', 'source-breakdown'], queryFn: dataApi.sourceBreakdown })
  const ingestionStatus = useQuery({ queryKey: ['data', 'ingestion-status'], queryFn: dataApi.ingestionStatus })
  const modelMetrics = useQuery({ queryKey: ['fraud', 'model-metrics'], queryFn: fraudApi.modelMetrics, retry: false })
  const blockchainStatus = useQuery({ queryKey: ['blockchain', 'status'], queryFn: blockchainApi.status })
  const securityOverview = useQuery({ queryKey: ['security', 'overview'], queryFn: securityApi.centerOverview })
  const copilotStatus = useQuery({ queryKey: ['copilot', 'status'], queryFn: copilotApi.status })
  const recentTransactions = useQuery({
    queryKey: ['transactions', 'recent'],
    queryFn: () => transactionsApi.list({ page: 1, page_size: 6 }),
  })

  const totalTransactions = sourceBreakdown.data
    ? Object.values(sourceBreakdown.data).reduce((sum, s) => sum + s.count, 0)
    : null

  const anySynthetic = sourceBreakdown.data ? Object.values(sourceBreakdown.data).some((s) => s.is_synthetic) : false

  const fraudRatePct = modelMetrics.data ? modelMetrics.data.fraud_rate_full_dataset * 100 : null
  const riskOrbLevel = fraudRatePct !== null ? Math.min(100, fraudRatePct * 8) : 20 // scaled for visual legibility, still driven by the real rate

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-1 text-[11px]" style={{ color: 'var(--emerald)' }}>
        Overview
      </div>
      <h1 className="font-serif text-2xl">Platform status</h1>

      {anySynthetic && (
        <div
          className="mt-4 inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-[12px]"
          style={{ background: 'var(--amber-soft)', color: 'var(--amber)' }}
        >
          Synthetic / demo data in use — real Kaggle datasets not yet ingested. See Dataset Status.
        </div>
      )}

      {/* Hero: risk orb + headline */}
      <Card elevated className="mt-6 grid grid-cols-[1fr_260px] items-center gap-6 overflow-hidden p-8">
        <div>
          <div className="text-[11.5px]" style={{ color: 'var(--text-dim)' }}>
            Dataset fraud prevalence
          </div>
          <div className="mt-2 font-serif text-4xl">
            {modelMetrics.isLoading ? (
              <span style={{ color: 'var(--text-dim)' }}>—</span>
            ) : modelMetrics.error ? (
              <span className="text-2xl" style={{ color: 'var(--text-dim)' }}>
                No model trained yet
              </span>
            ) : (
              `${fraudRatePct!.toFixed(2)}%`
            )}
          </div>
          {modelMetrics.data && (
            <p className="mt-3 max-w-md text-[13px] leading-relaxed" style={{ color: 'var(--text-dim)' }}>
              Selected model: <strong style={{ color: 'var(--text)' }}>{modelMetrics.data.selected_model}</strong>{' '}
              (by validation PR-AUC = {modelMetrics.data.test_metrics.pr_auc.toFixed(3)}).{' '}
              {modelMetrics.data.is_synthetic_data && 'Trained on labeled-synthetic data — not yet real IEEE-CIS results.'}
            </p>
          )}
          <Link to="/transactions" className="mt-4 inline-block text-[12.5px]" style={{ color: 'var(--emerald)' }}>
            View transactions →
          </Link>
        </div>
        <div className="h-[220px]">
          <RiskOrb riskLevel={riskOrbLevel} />
        </div>
      </Card>

      {/* Metric grid */}
      <div className="mt-6 grid grid-cols-4 gap-4">
        <MetricCard
          label="Total transactions"
          value={totalTransactions !== null ? totalTransactions.toLocaleString() : null}
          sub="ingested, all sources"
          loading={sourceBreakdown.isLoading}
          error={sourceBreakdown.error}
        />
        <MetricCard
          label="Blockchain graph"
          value={blockchainStatus.data ? (blockchainStatus.data.ready ? 'Ready' : 'Unavailable') : null}
          sub={blockchainStatus.data?.backend}
          loading={blockchainStatus.isLoading}
          error={blockchainStatus.error}
        />
        <MetricCard
          label="Chain integrity"
          value={
            securityOverview.data
              ? securityOverview.data.blockchain_integrity.last_verification.status === 'available'
                ? securityOverview.data.blockchain_integrity.last_verification.result?.valid
                  ? 'Intact'
                  : 'BROKEN'
                : 'Not yet run'
              : null
          }
          sub={`${securityOverview.data?.blockchain_integrity.sealed_transactions ?? '—'} sealed records`}
          loading={securityOverview.isLoading}
          error={securityOverview.error}
        />
        <MetricCard
          label="Copilot"
          value={copilotStatus.data ? (copilotStatus.data.llm_configured ? 'LLM-generated' : 'Evidence digest') : null}
          sub={copilotStatus.data?.llm_provider}
          loading={copilotStatus.isLoading}
          error={copilotStatus.error}
        />
      </div>

      {/* PQC + dataset status row */}
      <div className="mt-4 grid grid-cols-2 gap-4">
        <Card className="p-5">
          <div className="mb-3 text-[13px] font-semibold">Post-quantum readiness</div>
          {securityOverview.isLoading ? (
            <LoadingBlock />
          ) : securityOverview.error ? (
            <ErrorBlock error={securityOverview.error} />
          ) : (
            <div className="space-y-2 text-[13px]">
              <div className="flex items-center justify-between">
                <span style={{ color: 'var(--text-dim)' }}>{securityOverview.data!.quantum_safe_security.kem_algorithm}</span>
                <StatusPill tone={securityOverview.data!.quantum_safe_security.kem_self_test_passed ? 'emerald' : 'coral'}>
                  {securityOverview.data!.quantum_safe_security.kem_self_test_passed ? 'Pass' : 'Fail'}
                </StatusPill>
              </div>
              <div className="flex items-center justify-between">
                <span style={{ color: 'var(--text-dim)' }}>{securityOverview.data!.quantum_safe_security.signature_algorithm}</span>
                <StatusPill tone={securityOverview.data!.quantum_safe_security.signature_self_test_passed ? 'emerald' : 'coral'}>
                  {securityOverview.data!.quantum_safe_security.signature_self_test_passed ? 'Pass' : 'Fail'}
                </StatusPill>
              </div>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <div className="mb-3 text-[13px] font-semibold">Dataset ingestion</div>
          {ingestionStatus.isLoading ? (
            <LoadingBlock />
          ) : ingestionStatus.error ? (
            <ErrorBlock error={ingestionStatus.error} />
          ) : (
            <div className="space-y-2 text-[13px]">
              {(['ieee_cis', 'ibm_credit', 'ethereum'] as const).map((key) => (
                <div key={key} className="flex items-center justify-between">
                  <span style={{ color: 'var(--text-dim)' }}>{key.replace('_', '-')}</span>
                  <StatusPill tone={ingestionStatus.data![key].real_data_available ? 'emerald' : 'amber'}>
                    {ingestionStatus.data![key].real_data_available ? 'Real data' : 'Synthetic'}
                  </StatusPill>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Recent transactions */}
      <Card className="mt-4 p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="text-[13px] font-semibold">Recent transactions</div>
          <Link to="/transactions" className="text-[12px]" style={{ color: 'var(--emerald)' }}>
            View all →
          </Link>
        </div>
        {recentTransactions.isLoading ? (
          <LoadingBlock />
        ) : recentTransactions.error ? (
          <ErrorBlock error={recentTransactions.error} />
        ) : recentTransactions.data!.items.length === 0 ? (
          <div className="py-4 text-center text-[13px]" style={{ color: 'var(--text-dim)' }}>
            No transactions ingested yet.
          </div>
        ) : (
          <table className="w-full text-[13px]">
            <tbody>
              {recentTransactions.data!.items.map((txn) => (
                <tr key={txn.id} className="border-t" style={{ borderColor: 'var(--line)' }}>
                  <td className="py-2.5 font-mono text-[12px]" style={{ color: 'var(--text-dim)' }}>
                    {txn.id.slice(0, 8)}…
                  </td>
                  <td className="py-2.5">{txn.customer_id}</td>
                  <td className="py-2.5" style={{ color: 'var(--text-dim)' }}>
                    {txn.merchant_category ?? '—'}
                  </td>
                  <td className="py-2.5 text-right font-mono">${txn.amount.toFixed(2)}</td>
                  <td className="py-2.5 text-right">
                    <Link to={`/investigation/${txn.id}`} style={{ color: 'var(--emerald)' }}>
                      Investigate →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
