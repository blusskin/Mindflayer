import { useState, useEffect, useCallback } from 'react';
import { api } from '@/api/client';
import type { PotResponse } from '@/types/api';

interface UsePotOptions {
  pollInterval?: number; // in milliseconds, 0 to disable
}

export function usePot(options: UsePotOptions = {}) {
  const { pollInterval = 30000 } = options;
  const [pot, setPot] = useState<PotResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPot = useCallback(async () => {
    try {
      const data = await api.getPot();
      setPot(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch pot');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPot();

    if (pollInterval > 0) {
      const interval = setInterval(fetchPot, pollInterval);
      return () => clearInterval(interval);
    }
  }, [fetchPot, pollInterval]);

  return { pot, loading, error, refetch: fetchPot };
}
