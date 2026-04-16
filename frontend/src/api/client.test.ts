import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from './client';

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('api client', () => {
  it('returns parsed JSON on success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [] }),
    }));
    const result = await api('/claims');
    expect(result).toEqual({ items: [] });
  });

  it('includes X-API-Key header', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    vi.stubGlobal('fetch', fetchMock);
    await api('/claims');
    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers['X-API-Key']).toBeDefined();
  });

  it('includes Content-Type application/json header', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    vi.stubGlobal('fetch', fetchMock);
    await api('/claims');
    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers['Content-Type']).toBe('application/json');
  });

  it('throws an error on non-OK response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      text: async () => 'Claim not found',
    }));
    await expect(api('/claims/missing')).rejects.toThrow('404');
  });
});
