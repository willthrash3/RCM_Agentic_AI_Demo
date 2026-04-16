import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useSSE } from './useSSE';

// Capture the mock instance created in setup.ts
let mockESInstance: {
  addEventListener: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
  mockESInstance = (global.EventSource as ReturnType<typeof vi.fn>).mock.results[0]?.value ?? {
    addEventListener: vi.fn(),
    close: vi.fn(),
  };
});

describe('useSSE', () => {
  it('starts with connected=false', () => {
    const { result } = renderHook(() => useSSE());
    expect(result.current.connected).toBe(false);
  });

  it('starts with empty events array', () => {
    const { result } = renderHook(() => useSSE());
    expect(result.current.events).toHaveLength(0);
  });

  it('creates an EventSource on mount', () => {
    renderHook(() => useSSE());
    expect(global.EventSource).toHaveBeenCalled();
  });

  it('closes EventSource on unmount', () => {
    const { unmount } = renderHook(() => useSSE());
    // Get the last created mock instance
    const calls = (global.EventSource as ReturnType<typeof vi.fn>).mock.results;
    const instance = calls[calls.length - 1]?.value;
    unmount();
    expect(instance.close).toHaveBeenCalled();
  });
});
