import type { HTMLAttributes, ReactNode } from 'react'
import clsx from 'clsx'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  elevated?: boolean
  interactive?: boolean
}

/**
 * Depth here comes from a two-layer shadow (a tight contact shadow +
 * a soft ambient one) plus a 1px inset highlight on the top edge — the
 * combination reads as a physical object catching light, not a flat
 * rectangle with a drop-shadow filter. `elevated` cards sit further
 * "off the surface" for primary/hero content; `interactive` cards lift
 * slightly on hover to signal they respond to the pointer.
 */
export function Card({ children, elevated = false, interactive = false, className, style, ...rest }: CardProps) {
  return (
    <div
      className={clsx('rounded-[var(--radius)] border transition-[transform,box-shadow] duration-200', className)}
      style={{
        background: elevated
          ? 'linear-gradient(160deg, var(--surface-2), var(--surface-3))'
          : 'var(--surface)',
        borderColor: 'var(--line)',
        boxShadow: elevated
          ? '0 1px 0 0 rgba(255,255,255,0.04) inset, 0 8px 24px -8px rgba(0,0,0,0.45), 0 2px 6px -1px rgba(0,0,0,0.3)'
          : '0 1px 0 0 rgba(255,255,255,0.03) inset, 0 4px 14px -6px rgba(0,0,0,0.35)',
        cursor: interactive ? 'pointer' : undefined,
        ...style,
      }}
      onMouseEnter={(e) => {
        if (interactive) {
          e.currentTarget.style.transform = 'translateY(-2px)'
          e.currentTarget.style.boxShadow =
            '0 1px 0 0 rgba(255,255,255,0.05) inset, 0 14px 30px -10px rgba(0,0,0,0.5), 0 4px 10px -2px rgba(0,0,0,0.35)'
        }
      }}
      onMouseLeave={(e) => {
        if (interactive) {
          e.currentTarget.style.transform = 'translateY(0)'
          e.currentTarget.style.boxShadow = elevated
            ? '0 1px 0 0 rgba(255,255,255,0.04) inset, 0 8px 24px -8px rgba(0,0,0,0.45), 0 2px 6px -1px rgba(0,0,0,0.3)'
            : '0 1px 0 0 rgba(255,255,255,0.03) inset, 0 4px 14px -6px rgba(0,0,0,0.35)'
        }
      }}
      {...rest}
    >
      {children}
    </div>
  )
}
