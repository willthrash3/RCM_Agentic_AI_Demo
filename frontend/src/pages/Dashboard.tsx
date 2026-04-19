import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from 'recharts';
import { api } from '../api/client';
import KPICard from '../components/KPICard';
import AgentTraceFeed from '../components/AgentTraceFeed';
import { useSSE } from '../hooks/useSSE';

type BriefingStep = {
  label: string;
  run: () => Promise<unknown>;
};

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

  const [briefingStep, setBriefingStep] = useState<string | null>(null);

  const runTracking = useMutation({
    mutationFn: () => api('/agents/tracking/run', { method: 'POST', body: '{}' }),
  });
  const runEra = useMutation({
    mutationFn: () => api('/agents/era-posting/run', { method: 'POST', body: '{}' }),
  });

  const runBriefing = useMutation({
    mutationFn: async () => {
      const pick = <T,>(items: T[]): T | undefined => items[0];
      const patients = await api<{ items: Array<{ patient_id: string }> }>('/patients?page_size=5');
      const openClaims = await api<{ items: Array<{ claim_id: string; encounter_id: string }> }>(
        '/claims?status=Submitted&page_size=5',
      );
      const pendingDenials = await api<{ items: Array<{ denial_id: string; appeal_submitted_at: string | null }> }>(
        '/denials?page_size=10',
      );

      const patientId = pick(patients.items ?? [])?.patient_id;
      const sampleClaim = pick(openClaims.items ?? []);
      const pendingDenial = (pendingDenials.items ?? []).find((d) => !d.appeal_submitted_at);

      const steps: BriefingStep[] = [
        { label: 'Opening KPI snapshot', run: () => api('/agents/analytics/run', { method: 'POST', body: '{}' }) },
      ];
      if (patientId) {
        steps.push({
          label: 'Eligibility sweep',
          run: () =>
            api('/agents/eligibility/run', {
              method: 'POST',
              body: JSON.stringify({ patient_id: patientId, service_date: new Date().toISOString().slice(0, 10) }),
            }),
        });
      }
      if (sampleClaim?.encounter_id) {
        steps.push({
          label: 'Coding pass',
          run: () =>
            api('/agents/coding/run', {
              method: 'POST',
              body: JSON.stringify({ encounter_id: sampleClaim.encounter_id }),
            }),
        });
      }
      if (sampleClaim?.claim_id) {
        steps.push({
          label: 'Scrubbing outbound claim',
          run: () =>
            api('/agents/scrubbing/run', {
              method: 'POST',
              body: JSON.stringify({ claim_id: sampleClaim.claim_id }),
            }),
        });
      }
      steps.push({ label: 'Tracking open claims', run: () => api('/agents/tracking/run', { method: 'POST', body: '{}' }) });
      if (pendingDenial?.denial_id) {
        steps.push({
          label: 'Denial triage',
          run: () =>
            api('/agents/denial/run', {
              method: 'POST',
              body: JSON.stringify({ denial_id: pendingDenial.denial_id }),
            }),
        });
      }
      steps.push({ label: 'Posting ERA batch', run: () => api('/agents/era-posting/run', { method: 'POST', body: '{}' }) });
      steps.push({ label: 'Patient collections', run: () => api('/agents/collections/run', { method: 'POST', body: '{}' }) });
      steps.push({ label: 'Closing KPI snapshot', run: () => api('/agents/analytics/run', { method: 'POST', body: '{}' }) });

      for (const step of steps) {
        setBriefingStep(step.label);
        await step.run();
        await new Promise((r) => setTimeout(r, 750));
      }
      setBriefingStep(null);
      return steps.length;
    },
    onError: () => setBriefingStep(null),
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-semibold">Executive Dashboard</h1>
          <p className="text-slate-500 text-sm">
            {data ? `As of ${new Date(data.as_of).toLocaleString()}` : 'Loading…'}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className="px-3 py-1.5 bg-amber-600 text-white text-sm rounded hover:bg-amber-700 disabled:opacity-50"
            onClick={() => runTracking.mutate()}
            disabled={runTracking.isPending || runBriefing.isPending}
          >
            Run Tracking Agent
          </button>
          <button
            className="px-3 py-1.5 bg-emerald-600 text-white text-sm rounded hover:bg-emerald-700 disabled:opacity-50"
            onClick={() => runEra.mutate()}
            disabled={runEra.isPending || runBriefing.isPending}
          >
            Run ERA Posting
          </button>
          <button
            className="px-3 py-1.5 bg-envblue text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
            onClick={() => runBriefing.mutate()}
            disabled={runBriefing.isPending}
          >
            {runBriefing.isPending ? `Running: ${briefingStep ?? 'starting…'}` : 'Run Daily Briefing'}
          </button>
        </div>
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
