import { useEffect, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Legend } from 'recharts';
import { api } from '../api/client';

interface KPICardData {
  name: string;
  metric: string;
  value: number;
  target: number;
  unit: string;
  direction_good: 'up' | 'down';
}

interface BaselineSnapshot {
  captured_at: string;
  cards: KPICardData[];
}

const BASELINE_KEY = 'rcm-kpi-baseline';

function formatKPI(value: number, unit: string): string {
  if (unit === '%') return `${(value * 100).toFixed(1)}%`;
  if (unit === 'days') return `${value.toFixed(1)}d`;
  return value.toFixed(0);
}

function deltaLabel(baseline: number, current: number, direction: 'up' | 'down', unit: string) {
  const diff = current - baseline;
  if (Math.abs(diff) < 1e-9) return { text: '—', good: null };
  const isImprovement = direction === 'up' ? diff > 0 : diff < 0;
  const shown = unit === '%' ? `${(diff * 100).toFixed(1)} pts` : unit === 'days' ? `${diff.toFixed(1)}d` : diff.toFixed(0);
  const sign = diff > 0 ? '+' : '';
  return { text: `${sign}${shown}`, good: isImprovement };
}

export default function Analytics() {
  const { data: daysInAR } = useQuery({
    queryKey: ['ts-days-in-ar'],
    queryFn: () => api<any>('/kpis/timeseries/days_in_ar?days_back=30'),
  });
  const { data: fpr } = useQuery({
    queryKey: ['ts-fpr'],
    queryFn: () => api<any>('/kpis/timeseries/first_pass_rate?days_back=30'),
  });
  const { data: denialByPayer } = useQuery({
    queryKey: ['denial-by-payer'],
    queryFn: () => api<any>('/kpis/denial-rate-by-payer?period_days=30'),
  });
  const { data: forecast } = useQuery({
    queryKey: ['cash-forecast'],
    queryFn: () => api<any>('/kpis/cash-forecast?days_horizon=90'),
  });
  const { data: alerts } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => api<any>('/kpis/alerts'),
  });
  const { data: dashboard } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api<{ cards: KPICardData[] }>('/kpis/dashboard'),
    refetchInterval: 15_000,
  });

  const [baseline, setBaseline] = useState<BaselineSnapshot | null>(null);

  useEffect(() => {
    const raw = localStorage.getItem(BASELINE_KEY);
    if (raw) {
      try { setBaseline(JSON.parse(raw) as BaselineSnapshot); } catch { /* ignore */ }
    }
  }, []);

  const snapshotBaseline = () => {
    if (!dashboard?.cards) return;
    const snap: BaselineSnapshot = { captured_at: new Date().toISOString(), cards: dashboard.cards };
    localStorage.setItem(BASELINE_KEY, JSON.stringify(snap));
    setBaseline(snap);
  };
  const clearBaseline = () => {
    localStorage.removeItem(BASELINE_KEY);
    setBaseline(null);
  };

  const runAnalytics = useMutation({
    mutationFn: () => api('/agents/analytics/run', { method: 'POST', body: '{}' }),
  });

  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">AR Analytics</h1>
        <div className="flex gap-2">
          {baseline ? (
            <button
              className="px-3 py-1.5 bg-slate-200 text-slate-700 text-sm rounded hover:bg-slate-300"
              onClick={clearBaseline}
            >
              Clear Baseline
            </button>
          ) : null}
          <button
            className="px-3 py-1.5 bg-slate-700 text-white text-sm rounded hover:bg-slate-800 disabled:opacity-50"
            onClick={snapshotBaseline}
            disabled={!dashboard?.cards}
          >
            Snapshot Baseline
          </button>
          <button
            className="px-3 py-1.5 bg-envblue text-white text-sm rounded hover:bg-blue-700"
            onClick={() => runAnalytics.mutate()}
            disabled={runAnalytics.isPending}
          >
            Run Analytics Agent
          </button>
        </div>
      </div>

      {baseline && dashboard?.cards && (
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <div className="px-4 py-2 border-b font-semibold flex justify-between">
            <span>KPI Delta vs Baseline</span>
            <span className="text-xs text-slate-500 font-normal">
              Baseline captured {new Date(baseline.captured_at).toLocaleString()}
            </span>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left px-3 py-2">KPI</th>
                <th className="text-right px-3 py-2">Baseline</th>
                <th className="text-right px-3 py-2">Current</th>
                <th className="text-right px-3 py-2">Delta</th>
                <th className="text-right px-3 py-2">Target</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.cards.map((c) => {
                const b = baseline.cards.find((x) => x.metric === c.metric);
                if (!b) return null;
                const d = deltaLabel(b.value, c.value, c.direction_good, c.unit);
                const color = d.good === null ? 'text-slate-500' : d.good ? 'text-emerald-700' : 'text-rose-700';
                return (
                  <tr key={c.metric} className="border-t">
                    <td className="px-3 py-2">{c.name}</td>
                    <td className="px-3 py-2 text-right font-mono">{formatKPI(b.value, c.unit)}</td>
                    <td className="px-3 py-2 text-right font-mono">{formatKPI(c.value, c.unit)}</td>
                    <td className={`px-3 py-2 text-right font-mono ${color}`}>{d.text}</td>
                    <td className="px-3 py-2 text-right font-mono text-slate-500">{formatKPI(c.target, c.unit)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white p-4 rounded border border-slate-200">
          <div className="font-semibold mb-2">Days in AR — 30d Trend</div>
          <div className="h-52">
            <ResponsiveContainer>
              <LineChart data={daysInAR?.points || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#2E75B6" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white p-4 rounded border border-slate-200">
          <div className="font-semibold mb-2">First-Pass Rate — 30d Trend</div>
          <div className="h-52">
            <ResponsiveContainer>
              <LineChart data={fpr?.points || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                <Tooltip formatter={(v: number) => `${(v * 100).toFixed(2)}%`} />
                <Line type="monotone" dataKey="value" stroke="#10b981" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white p-4 rounded border border-slate-200">
          <div className="font-semibold mb-2">Denial Rate by Payer</div>
          <div className="h-52">
            <ResponsiveContainer>
              <BarChart data={denialByPayer || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="payer_id" />
                <YAxis tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                <Tooltip formatter={(v: number) => `${(v * 100).toFixed(2)}%`} />
                <Bar dataKey="denial_rate" fill="#ef4444" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white p-4 rounded border border-slate-200">
          <div className="font-semibold mb-2">Cash Flow Forecast (90d)</div>
          <div className="text-xs mb-1 text-slate-600">
            Outstanding: ${forecast?.total_outstanding?.toFixed(0) ?? '—'}
          </div>
          <div className="h-52">
            <ResponsiveContainer>
              <LineChart data={forecast?.weekly || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="week" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="lower_band" stroke="#94a3b8" strokeDasharray="3 3" />
                <Line type="monotone" dataKey="projected_collections" stroke="#2E75B6" strokeWidth={2} />
                <Line type="monotone" dataKey="upper_band" stroke="#94a3b8" strokeDasharray="3 3" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bg-white p-4 rounded border border-slate-200">
        <div className="font-semibold mb-2">KPI Alerts</div>
        {alerts?.length === 0 && <div className="text-sm text-slate-500">No active alerts</div>}
        <div className="space-y-1">
          {alerts?.map((a: any) => (
            <div key={a.alert_id} className="text-sm flex justify-between border-b py-1">
              <span>
                <span className={a.severity === 'critical' ? 'text-rose-600' : 'text-amber-600'}>
                  ● {a.severity.toUpperCase()}
                </span>{' '}
                {a.description}
              </span>
              <span className="text-xs text-slate-500">{new Date(a.created_at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
