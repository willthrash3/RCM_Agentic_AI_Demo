import AgentTraceFeed from '../components/AgentTraceFeed';
import { useSSE } from '../hooks/useSSE';

export default function AgentTrace() {
  const { events, connected } = useSSE();
  const byAgent: Record<string, number> = {};
  for (const e of events) byAgent[e.agent_name] = (byAgent[e.agent_name] || 0) + 1;
  const lastCompleted = [...events].reverse().find((e) => e.event_type === 'agent.completed');
  const confidence = lastCompleted?.data?.confidence as number | undefined;

  return (
    <div className="p-6 space-y-4 h-full flex flex-col">
      <div className="flex justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Agent Trace Viewer</h1>
          <div className="text-xs text-slate-500">
            <span className={connected ? 'text-emerald-600' : 'text-rose-600'}>
              {connected ? '● Connected' : '● Disconnected'}
            </span>
            {' · '}{events.length} events captured
          </div>
        </div>
        {confidence !== undefined && (
          <div className="text-right">
            <div className="text-xs text-slate-500">Last confidence</div>
            <div className="text-2xl font-bold">{confidence.toFixed(2)}</div>
            <div className="w-40 h-2 bg-slate-200 rounded mt-1">
              <div
                className="h-full bg-envblue rounded"
                style={{ width: `${Math.max(0, Math.min(100, confidence * 100))}%` }}
              />
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-8 gap-2 text-xs">
        {Object.entries(byAgent).map(([name, count]) => (
          <div key={name} className="bg-white p-2 rounded border text-center">
            <div className="font-semibold">{name}</div>
            <div className="text-lg">{count}</div>
          </div>
        ))}
      </div>

      <div className="flex-1 bg-white rounded-lg border border-slate-200 p-3 overflow-hidden">
        <AgentTraceFeed events={events} />
      </div>
    </div>
  );
}
