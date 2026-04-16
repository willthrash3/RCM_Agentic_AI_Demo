import clsx from 'clsx';

export interface KPICardProps {
  name: string;
  value: number;
  target: number;
  alertThreshold: number;
  status: 'On Track' | 'Watch' | 'Alert';
  unit: string;
  directionGood: 'up' | 'down';
}

const statusColors: Record<string, string> = {
  'On Track': 'bg-emerald-100 text-emerald-800',
  Watch: 'bg-amber-100 text-amber-800',
  Alert: 'bg-rose-100 text-rose-800',
};

function formatValue(value: number, unit: string): string {
  if (unit === '%') return `${(value * 100).toFixed(1)}%`;
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(1);
}

export default function KPICard(props: KPICardProps) {
  const { name, value, target, status, unit } = props;
  return (
    <div className="bg-white rounded-lg shadow-sm p-4 border border-slate-200">
      <div className="flex justify-between items-start">
        <div className="text-sm font-medium text-slate-600">{name}</div>
        <span
          className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', statusColors[status])}
        >
          {status}
        </span>
      </div>
      <div className="mt-2 text-3xl font-bold text-ink">{formatValue(value, unit)}</div>
      <div className="mt-1 text-xs text-slate-500">
        Target: {unit === '%' ? `${(target * 100).toFixed(0)}%` : target}
        {unit && unit !== '%' ? ` ${unit}` : ''}
      </div>
    </div>
  );
}
