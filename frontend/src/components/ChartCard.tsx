interface ChartCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}

export function ChartCard({ title, subtitle, children, action }: ChartCardProps) {
  return (
    <div className="min-w-0">
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-cat-black">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-cat-gray">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}
