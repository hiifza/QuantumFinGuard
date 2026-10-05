export function NotYetBuiltPage({ title }: { title: string }) {
  return (
    <div className="mx-auto max-w-lg py-20 text-center">
      <h1 className="font-serif text-2xl" style={{ color: 'var(--text)' }}>
        {title}
      </h1>
      <p className="mt-3 text-sm" style={{ color: 'var(--text-dim)' }}>
        Not built in this pass. The backend endpoints this screen needs already exist and are
        live-tested — this is a frontend sequencing gap, not a missing backend capability.
      </p>
    </div>
  )
}
