import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import clsx from 'clsx';
import { api } from '../api/client';

interface HITLTask {
  task_id: string;
  agent_name: string;
  entity_type: string;
  entity_id: string;
  task_description: string;
  priority: 'Critical' | 'High' | 'Medium' | 'Low';
  recommended_action: string;
  agent_reasoning: string;
  created_at: string;
}

const pColor: Record<string, string> = {
  Critical: 'bg-rose-100 text-rose-800 border-rose-300',
  High: 'bg-amber-100 text-amber-800 border-amber-300',
  Medium: 'bg-sky-100 text-sky-800 border-sky-300',
  Low: 'bg-slate-100 text-slate-700 border-slate-300',
};

export default function ReviewQueue() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data } = useQuery({
    queryKey: ['hitl-queue'],
    queryFn: () => api<HITLTask[]>('/hitl/queue?status=pending'),
    refetchInterval: 10_000,
  });
  const selected = data?.find((t) => t.task_id === selectedId) || data?.[0];

  const resolve = useMutation({
    mutationFn: (payload: { task_id: string; decision: string; notes?: string }) =>
      api(`/hitl/${payload.task_id}/resolve`, {
        method: 'POST',
        body: JSON.stringify({ decision: payload.decision, notes: payload.notes }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['hitl-queue'] }),
  });

  return (
    <div className="flex h-full">
      <div className="w-96 border-r overflow-auto">
        <div className="p-4 border-b">
          <h1 className="text-xl font-semibold">Review Queue</h1>
          <div className="text-xs text-slate-500">{data?.length ?? 0} pending tasks</div>
        </div>
        {data?.map((t) => (
          <button
            key={t.task_id}
            onClick={() => setSelectedId(t.task_id)}
            className={clsx(
              'w-full text-left px-4 py-3 border-b hover:bg-slate-50',
              selected?.task_id === t.task_id && 'bg-blue-50',
            )}
          >
            <div className="flex justify-between items-start">
              <span className={clsx('text-xs px-2 py-0.5 rounded border', pColor[t.priority])}>
                {t.priority}
              </span>
              <span className="text-xs text-slate-500">{t.agent_name}</span>
            </div>
            <div className="text-sm mt-2">{t.task_description}</div>
            <div className="text-xs text-slate-500 mt-1">
              {t.entity_type} · {t.entity_id}
            </div>
          </button>
        ))}
      </div>

      <div className="flex-1 p-6 overflow-auto">
        {!selected ? (
          <div className="text-slate-500">Select a task from the queue</div>
        ) : (
          <>
            <h2 className="text-xl font-semibold">{selected.task_description}</h2>
            <div className="text-sm text-slate-500 mt-1">
              From {selected.agent_name} · {selected.entity_type} {selected.entity_id}
            </div>

            <div className="mt-4 bg-white p-4 rounded border border-slate-200">
              <div className="font-semibold text-sm mb-1">Recommended Action</div>
              <div className="text-sm">{selected.recommended_action}</div>
            </div>

            <div className="mt-4 bg-white p-4 rounded border border-slate-200">
              <div className="font-semibold text-sm mb-1">Agent Reasoning</div>
              <pre className="text-xs whitespace-pre-wrap">{selected.agent_reasoning}</pre>
            </div>

            <div className="mt-6 flex gap-2">
              <button
                className="px-4 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700 text-sm"
                onClick={() => resolve.mutate({ task_id: selected.task_id, decision: 'approve' })}
                disabled={resolve.isPending}
              >
                Approve
              </button>
              <button
                className="px-4 py-2 bg-rose-600 text-white rounded hover:bg-rose-700 text-sm"
                onClick={() => resolve.mutate({ task_id: selected.task_id, decision: 'reject' })}
                disabled={resolve.isPending}
              >
                Reject
              </button>
              <button
                className="px-4 py-2 bg-amber-600 text-white rounded hover:bg-amber-700 text-sm"
                onClick={() => resolve.mutate({ task_id: selected.task_id, decision: 'modify' })}
                disabled={resolve.isPending}
              >
                Modify
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
