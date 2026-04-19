import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from 'recharts';
import { api } from '../api/client';
import KPICard from '../components/KPICard';
import AgentTraceFeed from '../components/AgentTraceFeed';
import { useSSE } from '../hooks/useSSE';

type BriefingStep = {
  label: string;
  run: () => Promise<{ task_id: string }>;
};

const TERMINAL_TASK_STATUSES = new Set(['complete', 'escalated', 'failed']);

async function waitForTask(taskId: string, timeoutMs = 30_000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const task = await api<{ status: string }>(`/agents/tasks/${taskId}`);
    if (TERMINAL_TASK_STATUSES.has(task.status)) return;
    await new Promise((r) => setTimeout(r, 400));
  }
  throw new Error(`Task ${taskId} did not reach a terminal status within ${timeoutMs}ms`);
}

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
  const [briefingError, setBriefingError] = useState<string | null>(null);

  const runTracking = useMutation({
    mutationFn: () => api<{ task_id: string }>('/agents/tracking/run', { method: 'POST', body: '{}' }),
  });
  const runEra = useMutation({
    mutationFn: () => api<{ task_id: string }>('/agents/era-posting/run', { method: 'POST', body: '{}' }),
  });

  const runBriefing = useMutation({
    mutationFn: async () => {
      setBriefingError(null);
      try {
        const pick = <T,>(items: T[]): T | undefined => items[0];
        const patients = await api<{ items: Array<{ patient_id: string }> }>('/patients?page_size=5');
        // Accept any claim status so the briefing reliably has a coding/scrubbing target,
        // even if the seed currently has no Submitted claims.
        const claims = await api<{ items: Array<{ claim_id: string; encounter_id: string }> }>(
          '/claims?page_size=25',
        );
        const pendingDenials = await api<{ items: Array<{ denial_id: string; appeal_submitted_at: string | null }> }>(
          '/denials?page_size=25',
        );

        const patientId = pick(patients.items ?? [])?.patient_id;
        const sampleClaim = pick(claims.items ?? []);
        const pendingDenial = (pendingDenials.items ?? []).find((d) => !d.appeal_submitted_at);

        const missing: string[] = [];
        if (!patientId) missing.push('eligibility (no patient)');
        if (!sampleClaim?.encounter_id) missing.push('coding (no encounter)');
        if (!sampleClaim?.claim_id) missing.push('scrubbing (no claim)');
        if (!pendingDenial?.denial_id) missing.push('denial (no pending denial)');
        if (missing.length) {
          throw new Error(
            `Cannot run full 8-agent briefing — missing seed data for: ${missing.join(', ')}. ` +
              'Reset the database via the Scenarios page and try again.',
          );
        }

        const post = (path: string, body: string = '{}') =>
          api<{ task_id: string }>(path, { method: 'POST', body });

        const steps: BriefingStep[] = [
          { label: 'Opening KPI snapshot', run: () => post('/agents/analytics/run') },
          {
            label: 'Eligibility sweep',
            run: () =>
              post(
                '/agents/eligibility/run',
                JSON.stringify({ patient_id: patientId, service_date: new Date().toISOString().slice(0, 10) }),
              ),
          },
          {
            label: 'Coding pass',
            run: () => post('/agents/coding/run', JSON.stringify({ encounter_id: sampleClaim!.encounter_id })),
          },
          {
            label: 'Scrubbing outbound claim',
            run: () => post('/agents/scrubbing/run', JSON.stringify({ claim_id: sampleClaim!.claim_id })),
          },
          { label: 'Tracking open claims', run: () => post('/agents/tracking/run') },
          {
            label: 'Denial triage',
            run: () => post('/agents/denial/run', JSON.stringify({ denial_id: pendingDenial!.denial_id })),
          },
          { label: 'Posting ERA batch', run: () => post('/agents/era-posting/run') },
          { label: 'Patient collections', run: () => post('/agents/collections/run') },
          { label: 'Closing KPI snapshot', run: () => post('/agents/analytics/run') },
        ];

        for (const step of steps) {
          setBriefingStep(step.label);
          const { task_id } = await step.run();
          await waitForTask(task_id);
        }
        return steps.length;
      } finally {
        setBriefingStep(null);
      }
    },
    onError: (err: Error) => setBriefingError(err.message),
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

      {briefingError && (
        <div className="bg-rose-50 border border-rose-200 text-rose-800 text-sm rounded p-3 flex justify-between">
          <span>{briefingError}</span>
          <button className="text-rose-600 hover:text-rose-800" onClick={() => setBriefingError(null)}>
            dismiss
          </button>
        </div>
      )}

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
