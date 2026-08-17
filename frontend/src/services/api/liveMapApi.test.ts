import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { fetchSegments } from './liveMapApi';

describe('fetchSegments', () => {
  afterEach(() => vi.restoreAllMocks());

  it('requests the segment set matching a snapshot network source', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: [] });
    await fetchSegments('osm_geo_v2');
    expect(get).toHaveBeenCalledWith('/api/v1/segments', { params: { network_source: 'osm_geo_v2' } });
  });

  it('preserves the V1 request when no network source is provided', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: [] });
    await fetchSegments();
    expect(get).toHaveBeenCalledWith('/api/v1/segments', { params: undefined });
  });
});
