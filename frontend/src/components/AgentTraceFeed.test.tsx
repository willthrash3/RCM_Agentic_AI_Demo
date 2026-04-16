import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import AgentTraceFeed from './AgentTraceFeed';
import type { AgentEvent } from '../hooks/useSSE';

const makeEvent = (overrides: Partial<AgentEvent> = {}): AgentEvent => ({
  event_id: 'evt-001',
  event_type: 'agent.started',
  agent_name: 'coding_agent',
  entity_type: 'encounter',
  entity_id: 'enc-001',
  data: {},
  timestamp: new Date().toISOString(),
  ...overrides,
});

describe('AgentTraceFeed', () => {
  it('shows placeholder when events array is empty', () => {
    render(<AgentTraceFeed events={[]} />);
    expect(screen.getByText(/Waiting for agent events/)).toBeInTheDocument();
  });

  it('renders the agent_name from an event', () => {
    render(<AgentTraceFeed events={[makeEvent({ agent_name: 'eligibility_agent' })]} />);
    expect(screen.getByText('eligibility_agent')).toBeInTheDocument();
  });

  it('renders tool name when data.tool is present', () => {
    render(
      <AgentTraceFeed
        events={[makeEvent({ data: { tool: 'search_cpt_codes' } })]}
      />
    );
    expect(screen.getByText(/search_cpt_codes/)).toBeInTheDocument();
  });

  it('renders reasoning when data.reasoning is present', () => {
    render(
      <AgentTraceFeed
        events={[makeEvent({ data: { reasoning: 'High confidence match' } })]}
      />
    );
    expect(screen.getByText('High confidence match')).toBeInTheDocument();
  });

  it('renders multiple events', () => {
    const events = [
      makeEvent({ event_id: 'e1', agent_name: 'coding_agent' }),
      makeEvent({ event_id: 'e2', agent_name: 'denial_agent' }),
    ];
    render(<AgentTraceFeed events={events} />);
    expect(screen.getByText('coding_agent')).toBeInTheDocument();
    expect(screen.getByText('denial_agent')).toBeInTheDocument();
  });
});
