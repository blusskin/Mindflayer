import { useState, useEffect, useCallback } from 'react';
import { api } from '@/api/client';
import type { StatsResponse } from '@/types/api';

interface UseStatsOptions {
  pollInterval?: number; // in milliseconds, 0 to disable
}

export function useStats(options: UseStatsOptions = {}) {
  const { pollInterval = 30000 } = options;
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    try {
      const data = await api.getStats();
      setStats(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch stats');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();

    if (pollInterval > 0) {
      const interval = setInterval(fetchStats, pollInterval);
      return () => clearInterval(interval);
    }
  }, [fetchStats, pollInterval]);

  return { stats, loading, error, refetch: fetchStats };
}
