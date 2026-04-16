import clsx from 'clsx';
import type { AgentEvent } from '../hooks/useSSE';

const eventColors: Record<string, string> = {
  'agent.started': 'bg-sky-100 text-sky-800 border-sky-300',
  'agent.tool_call': 'bg-slate-100 text-slate-800 border-slate-300',
  'agent.reasoning': 'bg-indigo-50 text-indigo-800 border-indigo-300',
  'agent.completed': 'bg-emerald-100 text-emerald-800 border-emerald-300',
  'agent.escalated': 'bg-amber-100 text-amber-800 border-amber-300',
  'agent.failed': 'bg-rose-100 text-rose-800 border-rose-300',
  'kpi.alert': 'bg-rose-100 text-rose-900 border-rose-400',
  'hitl.task_created': 'bg-violet-100 text-violet-800 border-violet-300',
  'hitl.task_resolved': 'bg-emerald-50 text-emerald-700 border-emerald-200',
  'scenario.injected': 'bg-cyan-100 text-cyan-800 border-cyan-300',
};

export default function AgentTraceFeed({ events }: { events: AgentEvent[] }) {
  return (
    <div className="flex flex-col gap-1 max-h-full overflow-auto font-mono text-xs">
      {events.length === 0 && (
        <div className="text-slate-500 italic p-3">Waiting for agent events…</div>
      )}
      {events.slice().reverse().map((e) => (
        <div
          key={e.event_id}
          className={clsx('border rounded p-2', eventColors[e.event_type] || 'bg-white border-slate-200')}
        >
          <div className="flex justify-between">
            <span className="font-semibold">{e.agent_name}</span>
            <span className="text-[10px] text-slate-500">{new Date(e.timestamp).toLocaleTimeString()}</span>
          </div>
          <div className="text-[11px] opacity-80">
            {e.event_type} · {e.entity_type} {e.entity_id}
          </div>
          {e.data?.tool && (
            <div className="mt-1">
              <strong>tool:</strong> {e.data.tool}
            </div>
          )}
          {e.data?.reasoning && (
            <div className="mt-1 whitespace-pre-wrap">{e.data.reasoning}</div>
          )}
          {e.data?.confidence !== undefined && (
            <div className="mt-1">confidence: {Number(e.data.confidence).toFixed(2)}</div>
          )}
        </div>
      ))}
    </div>
  );
}
