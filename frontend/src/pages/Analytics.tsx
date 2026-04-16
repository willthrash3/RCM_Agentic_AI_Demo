import { useQuery, useMutation } from '@tanstack/react-query';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Legend } from 'recharts';
import { api } from '../api/client';

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

  const runAnalytics = useMutation({
    mutationFn: () => api('/agents/analytics/run', { method: 'POST', body: '{}' }),
  });

  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">AR Analytics</h1>
        <button
          className="px-3 py-1.5 bg-envblue text-white text-sm rounded hover:bg-blue-700"
          onClick={() => runAnalytics.mutate()}
          disabled={runAnalytics.isPending}
        >
          Run Analytics Agent
        </button>
      </div>

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
