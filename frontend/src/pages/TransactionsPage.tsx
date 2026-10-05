import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { transactionsApi, dataApi } from '../api/endpoints'
import { Card } from '../components/ui/Card'
import { LoadingBlock, ErrorBlock, StatusPill } from '../components/ui/States'

const PAGE_SIZE = 20

export function TransactionsPage() {
  const [page, setPage] = useState(1)

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['transactions', page],
    queryFn: () => transactionsApi.list({ page, page_size: PAGE_SIZE }),
  })

  const sourceBreakdown = useQuery({ queryKey: ['data', 'source-breakdown'], queryFn: dataApi.sourceBreakdown })

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-1 text-[11px]" style={{ color: 'var(--emerald)' }}>
        Overview
      </div>
      <h1 className="font-serif text-2xl">Transactions</h1>

      {sourceBreakdown.data && (
        <div className="mt-4 flex gap-2">
          {Object.entries(sourceBreakdown.data).map(([source, info]) => (
            <StatusPill key={source} tone={info.is_synthetic ? 'amber' : 'emerald'}>
              {source}: {info.count.toLocaleString()}
            </StatusPill>
          ))}
        </div>
      )}

      <Card className="mt-5 p-0">
        {isLoading ? (
          <div className="p-6">
            <LoadingBlock label="Loading transactions…" />
          </div>
        ) : error ? (
          <div className="p-6">
            <ErrorBlock error={error} onRetry={refetch} />
          </div>
        ) : data!.items.length === 0 ? (
          <div className="p-8 text-center text-[13px]" style={{ color: 'var(--text-dim)' }}>
            No transactions found.
          </div>
        ) : (
          <>
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b text-left text-[11px]" style={{ borderColor: 'var(--line)', color: 'var(--text-dim)' }}>
                  <th className="px-5 py-3 font-normal">ID</th>
                  <th className="px-5 py-3 font-normal">Customer</th>
                  <th className="px-5 py-3 font-normal">Merchant category</th>
                  <th className="px-5 py-3 font-normal text-right">Amount</th>
                  <th className="px-5 py-3 font-normal">Timestamp</th>
                  <th className="px-5 py-3 font-normal text-right">Integrity</th>
                  <th className="px-5 py-3 font-normal text-right"></th>
                </tr>
              </thead>
              <tbody>
                {data!.items.map((txn) => (
                  <tr key={txn.id} className="border-b" style={{ borderColor: 'var(--line)' }}>
                    <td className="px-5 py-3 font-mono text-[12px]" style={{ color: 'var(--text-dim)' }}>
                      {txn.id.slice(0, 10)}…
                    </td>
                    <td className="px-5 py-3">{txn.customer_id}</td>
                    <td className="px-5 py-3" style={{ color: 'var(--text-dim)' }}>
                      {txn.merchant_category ?? '—'}
                    </td>
                    <td className="px-5 py-3 text-right font-mono">${txn.amount.toFixed(2)}</td>
                    <td className="px-5 py-3" style={{ color: 'var(--text-dim)' }}>
                      {new Date(txn.timestamp).toLocaleString()}
                    </td>
                    <td className="px-5 py-3 text-right">
                      {txn.record_hash ? (
                        <StatusPill tone="emerald">Sealed</StatusPill>
                      ) : (
                        <StatusPill tone="neutral">Unsealed</StatusPill>
                      )}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <Link to={`/investigation/${txn.id}`} className="text-[12.5px]" style={{ color: 'var(--emerald)' }}>
                        Investigate →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div
              className="flex items-center justify-between border-t px-5 py-3 text-[12.5px]"
              style={{ borderColor: 'var(--line)', color: 'var(--text-dim)' }}
            >
              <span>
                Page {page} of {totalPages} — {data!.total.toLocaleString()} total
              </span>
              <div className="flex gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded-md border px-3 py-1 disabled:opacity-40"
                  style={{ borderColor: 'var(--line)' }}
                >
                  Previous
                </button>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-md border px-3 py-1 disabled:opacity-40"
                  style={{ borderColor: 'var(--line)' }}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
