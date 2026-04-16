import { useQuery, useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../api/client';
import { useSSE } from '../hooks/useSSE';
import AgentTraceFeed from '../components/AgentTraceFeed';

interface Scenario {
  scenario_id: string;
  name: string;
  description: string;
  expected_outcome: string;
}

export default function Scenarios() {
  const { data } = useQuery({
    queryKey: ['scenarios'],
    queryFn: () => api<Scenario[]>('/scenarios'),
  });
  const [runResult, setRunResult] = useState<any>(null);
  const { events } = useSSE();

  const runScenario = useMutation({
    mutationFn: (scenario_id: string) =>
      api<any>('/scenarios/run', { method: 'POST', body: JSON.stringify({ scenario_id }) }),
    onSuccess: (r) => setRunResult(r),
  });

  const reset = useMutation({
    mutationFn: () => api<any>('/scenarios/reset', { method: 'POST' }),
  });

  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between">
        <h1 className="text-2xl font-semibold">Scenario Runner</h1>
        <button
          className="px-3 py-1.5 bg-slate-700 text-white text-sm rounded hover:bg-slate-900"
          onClick={() => reset.mutate()}
          disabled={reset.isPending}
        >
          Reset DB to Seed
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {data?.map((s) => (
          <div key={s.scenario_id} className="bg-white p-4 rounded-lg border border-slate-200">
            <div className="font-semibold">{s.name}</div>
            <div className="text-xs text-slate-600 mt-1">{s.description}</div>
            <div className="text-xs text-slate-500 mt-2 italic">{s.expected_outcome}</div>
            <button
              className="mt-3 w-full px-3 py-1.5 bg-envblue text-white text-sm rounded hover:bg-blue-700"
              onClick={() => runScenario.mutate(s.scenario_id)}
              disabled={runScenario.isPending}
            >
              Run Scenario
            </button>
          </div>
        ))}
      </div>

      {runResult && (
        <div className="bg-white p-4 rounded border border-slate-200">
          <div className="font-semibold">Latest Run: {runResult.name}</div>
          <div className="text-sm text-slate-600 mt-1">
            Affected: {runResult.affected_count} · Expected: {runResult.expected_outcome}
          </div>
          <pre className="text-xs mt-2 bg-slate-50 p-2 rounded overflow-auto">
            {JSON.stringify(runResult, null, 2)}
          </pre>
        </div>
      )}

      <div className="bg-white rounded-lg border border-slate-200">
        <div className="px-4 py-2 border-b font-semibold">Live Agent Reactions</div>
        <div className="p-3 h-64 overflow-auto">
          <AgentTraceFeed events={events} />
        </div>
      </div>
    </div>
  );
}
