interface AlertCardProps {
  title: string;
  message: string;
  severity: string;
  equipmentId?: string | null;
  time?: string;
  onClick?: () => void;
}

const DOT: Record<string, string> = {
  CRITICAL: 'bg-red-600',
  OVERDUE: 'bg-red-600',
  URGENT: 'bg-orange-500',
  WARNING: 'bg-amber-500',
  REMINDER: 'bg-sky-500',
  INFO: 'bg-cat-gray',
};

export function AlertCard({ title, message, severity, equipmentId, time, onClick }: AlertCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full gap-3 border-b border-cat-muted py-3 text-left last:border-0 hover:bg-cat-light/80"
    >
      <span
        className={`mt-1.5 h-2 w-2 shrink-0 ${DOT[severity] || 'bg-cat-gray'}`}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <p className="text-sm font-semibold text-cat-black">{title}</p>
          <span className="text-[10px] font-semibold uppercase tracking-wide text-cat-gray">
            {severity}
          </span>
        </div>
        <p className="mt-0.5 line-clamp-1 text-xs text-cat-gray">{message}</p>
        <div className="mt-1 flex gap-3 text-[11px] text-cat-gray">
          {equipmentId && <span className="font-medium text-cat-dark">{equipmentId}</span>}
          {time && <span>{new Date(time).toLocaleString()}</span>}
        </div>
      </div>
    </button>
  );
}
