import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from 'recharts';
import { api } from '../api/client';
import KPICard from '../components/KPICard';
import AgentTraceFeed from '../components/AgentTraceFeed';
import { useSSE } from '../hooks/useSSE';

interface DashboardResponse {
  as_of: string;
  cards: Array<{
    name: string;
    metric: string;
    value: number;
    target: number;
    alert_threshold: number;
    status: 'On Track' | 'Watch' | 'Alert';
    direction_good: 'up' | 'down';
    unit: string;
  }>;
  agent_activity_ticker: Array<any>;
}

export default function Dashboard() {
  const { data } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api<DashboardResponse>('/kpis/dashboard'),
    refetchInterval: 15_000,
  });
  const { data: aging } = useQuery({
    queryKey: ['ar-aging'],
    queryFn: () => api<any>('/kpis/ar-aging'),
  });
  const { data: timeseries } = useQuery({
    queryKey: ['denial-rate-series'],
    queryFn: () => api<any>('/kpis/timeseries/denial_rate?days_back=30'),
  });
  const { events } = useSSE();

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Executive Dashboard</h1>
        <p className="text-slate-500 text-sm">
          {data ? `As of ${new Date(data.as_of).toLocaleString()}` : 'Loading…'}
        </p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {data?.cards.map((c) => (
          <KPICard
            key={c.metric}
            name={c.name}
            value={c.value}
            target={c.target}
            alertThreshold={c.alert_threshold}
            status={c.status}
            unit={c.unit}
            directionGood={c.direction_good}
          />
        ))}
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 bg-white rounded-lg shadow-sm p-4 border border-slate-200">
          <div className="font-semibold mb-2">AR Aging by Payer</div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={aging?.buckets || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="payer_id" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="bucket_0_30" stackId="a" fill="#4ade80" name="0-30" />
                <Bar dataKey="bucket_31_60" stackId="a" fill="#fbbf24" name="31-60" />
                <Bar dataKey="bucket_61_90" stackId="a" fill="#fb923c" name="61-90" />
                <Bar dataKey="bucket_91_120" stackId="a" fill="#f87171" name="91-120" />
                <Bar dataKey="bucket_over_120" stackId="a" fill="#ef4444" name="120+" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-4 border border-slate-200">
          <div className="font-semibold mb-2">Denial Rate — 30d Trend</div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeseries?.points || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                <Tooltip formatter={(v: number) => `${(v * 100).toFixed(2)}%`} />
                <Line type="monotone" dataKey="value" stroke="#2E75B6" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-slate-200">
        <div className="px-4 py-2 border-b border-slate-200 flex justify-between">
          <div className="font-semibold">Live Agent Activity</div>
          <div className="text-xs text-slate-500">{events.length} events</div>
        </div>
        <div className="p-3 h-64 overflow-auto">
          <AgentTraceFeed events={events} />
        </div>
      </div>
    </div>
  );
}
