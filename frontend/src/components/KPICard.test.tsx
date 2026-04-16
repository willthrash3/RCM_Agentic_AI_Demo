import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import KPICard from './KPICard';

const baseProps = {
  name: 'Days in AR',
  value: 40,
  target: 45,
  alertThreshold: 55,
  status: 'On Track' as const,
  unit: 'days',
  directionGood: 'down' as const,
};

describe('KPICard', () => {
  it('renders the name', () => {
    render(<KPICard {...baseProps} />);
    expect(screen.getByText('Days in AR')).toBeInTheDocument();
  });

  it('shows On Track badge with emerald styles', () => {
    render(<KPICard {...baseProps} status="On Track" />);
    const badge = screen.getByText('On Track');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('emerald');
  });

  it('shows Alert badge with rose styles', () => {
    render(<KPICard {...baseProps} status="Alert" />);
    const badge = screen.getByText('Alert');
    expect(badge.className).toContain('rose');
  });

  it('shows Watch badge with amber styles', () => {
    render(<KPICard {...baseProps} status="Watch" />);
    const badge = screen.getByText('Watch');
    expect(badge.className).toContain('amber');
  });

  it('formats percentage values correctly', () => {
    render(<KPICard {...baseProps} unit="%" value={0.94} name="First Pass Rate" />);
    expect(screen.getByText('94.0%')).toBeInTheDocument();
  });

  it('renders integer days value without decimal', () => {
    render(<KPICard {...baseProps} value={40} unit="days" />);
    expect(screen.getByText('40')).toBeInTheDocument();
  });

  it('shows the target value', () => {
    render(<KPICard {...baseProps} target={45} unit="days" />);
    expect(screen.getByText(/Target:/)).toBeInTheDocument();
    expect(screen.getByText(/45/)).toBeInTheDocument();
  });

  it('formats percentage target correctly', () => {
    render(<KPICard {...baseProps} unit="%" value={0.94} target={0.94} />);
    expect(screen.getByText(/94%/)).toBeInTheDocument();
  });
});
