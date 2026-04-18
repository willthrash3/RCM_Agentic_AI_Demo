import { useEffect, useRef, useState } from 'react';
import { api, apiBase } from '../api/client';

export interface AgentEvent {
  event_id: string;
  event_type: string;
  agent_name: string;
  entity_type: string;
  entity_id: string;
  task_id?: string;
  data: Record<string, any>;
  timestamp: string;
}

/**
 * Subscribe to the SSE stream of agent events.
 * Auto-reconnects after 5s on drop (PRD §10.2).
 */
export function useSSE(
  filter?: { task_id?: string; entity_type?: string; entity_id?: string },
  loadHistory = false,
) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const seenIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!loadHistory) return;
    api<AgentEvent[]>('/events/recent').then((history) => {
      setEvents(history);
      for (const e of history) seenIds.current.add(e.event_id);
    }).catch(() => {});
  }, [loadHistory]);

  useEffect(() => {
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      const params = new URLSearchParams();
      if (filter?.task_id) params.set('task_id', filter.task_id);
      if (filter?.entity_type) params.set('entity_type', filter.entity_type);
      if (filter?.entity_id) params.set('entity_id', filter.entity_id);
      const url = `${apiBase}/events/stream${params.toString() ? `?${params}` : ''}`;
      const es = new EventSource(url);
      esRef.current = es;
      es.addEventListener('open', () => setConnected(true));
      const handler = (evt: MessageEvent) => {
        try {
          const ae = JSON.parse(evt.data) as AgentEvent;
          if (seenIds.current.has(ae.event_id)) return;
          seenIds.current.add(ae.event_id);
          setEvents((prev) => [...prev.slice(-499), ae]);
        } catch {
          /* keepalive */
        }
      };
      ['agent.started', 'agent.tool_call', 'agent.reasoning', 'agent.completed',
       'agent.escalated', 'agent.failed', 'kpi.alert', 'hitl.task_created',
       'hitl.task_resolved', 'scenario.injected'].forEach((t) => {
         es.addEventListener(t, handler as EventListener);
       });
      es.addEventListener('error', () => {
        setConnected(false);
        es.close();
        setTimeout(connect, 5_000);
      });
    };

    connect();
    return () => {
      cancelled = true;
      esRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter?.task_id, filter?.entity_type, filter?.entity_id]);

  return { events, connected };
}
