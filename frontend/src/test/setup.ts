import '@testing-library/jest-dom';

// Mock EventSource globally for useSSE tests
const mockEventSource = {
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  close: vi.fn(),
  readyState: 1,
  CONNECTING: 0,
  OPEN: 1,
  CLOSED: 2,
};

global.EventSource = vi.fn(() => mockEventSource) as unknown as typeof EventSource;
