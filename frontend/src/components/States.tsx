export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-20 text-sm text-cat-gray">
      <span className="h-3.5 w-3.5 animate-spin border-2 border-cat-yellow border-t-transparent" />
      {label}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="py-16 text-center">
      <p className="text-sm font-semibold text-red-800">Something went wrong</p>
      <p className="mt-1 text-xs text-cat-gray">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn-primary mt-4">
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="border-y border-cat-muted py-14 text-center">
      <p className="text-sm font-semibold text-cat-black">{title}</p>
      {description && <p className="mx-auto mt-1 max-w-lg text-xs text-cat-gray">{description}</p>}
    </div>
  );
}
