import type { ReactNode } from 'react'
import { ApiError } from '../../api/client'

export function LoadingBlock({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-8 text-sm" style={{ color: 'var(--text-dim)' }}>
      <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent opacity-70" />
      {label}
    </div>
  )
}

export function ErrorBlock({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const isApiError = error instanceof ApiError
  const title = isApiError && error.isNetworkError ? 'Backend unreachable' : 'Something went wrong'
  const detail = isApiError ? error.detail : error instanceof Error ? error.message : 'Unknown error.'

  return (
    <div
      className="rounded-[var(--radius)] border p-5"
      style={{ borderColor: 'var(--coral)', background: 'var(--coral-soft)' }}
    >
      <div className="text-sm font-semibold" style={{ color: 'var(--coral)' }}>
        {title}
      </div>
      <div className="mt-1 text-sm" style={{ color: 'var(--text-dim)' }}>
        {detail}
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
          style={{ background: 'var(--surface-2)', color: 'var(--text)', border: '1px solid var(--line)' }}
        >
          Retry
        </button>
      )}
    </div>
  )
}

export function EmptyBlock({ title, detail, icon }: { title: string; detail?: string; icon?: ReactNode }) {
  return (
    <div
      className="rounded-[var(--radius)] border border-dashed p-6 text-center"
      style={{ borderColor: 'var(--line)' }}
    >
      {icon && <div className="mb-2 flex justify-center opacity-60">{icon}</div>}
      <div className="text-sm font-medium">{title}</div>
      {detail && (
        <div className="mt-1 text-xs" style={{ color: 'var(--text-dim)' }}>
          {detail}
        </div>
      )}
    </div>
  )
}

/** For the backend's own status/reason evidence pattern (not_available,
 * not_applicable) — distinct from a loading/network error, this is the
 * backend honestly saying "this capability has nothing to show yet." */
export function UnavailableBlock({ reason, tone = 'neutral' }: { reason: string; tone?: 'neutral' | 'muted' }) {
  return (
    <div
      className="rounded-[var(--radius)] border p-4 text-sm"
      style={{
        borderColor: 'var(--line)',
        background: tone === 'muted' ? 'transparent' : 'var(--surface-2)',
        color: 'var(--text-dim)',
      }}
    >
      {reason}
    </div>
  )
}

export function StatusPill({ tone, children }: { tone: 'emerald' | 'amber' | 'coral' | 'neutral'; children: ReactNode }) {
  const colorVar = tone === 'neutral' ? 'var(--text-dim)' : `var(--${tone})`
  const bgVar = tone === 'neutral' ? 'var(--surface-2)' : `var(--${tone}-soft)`
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
      style={{ color: colorVar, background: bgVar }}
    >
      {children}
    </span>
  )
}
