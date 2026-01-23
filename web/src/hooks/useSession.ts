import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '@/api/client';
import type { SessionResponse } from '@/types/api';

interface UseSessionOptions {
  pollInterval?: number; // in milliseconds
  stopOnActive?: boolean; // stop polling when status becomes active
}

export function useSession(
  sessionId: number | null,
  token: string | null = null,
  options: UseSessionOptions = {}
) {
  const { pollInterval = 2000, stopOnActive = true } = options;
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<number | null>(null);

  const fetchSession = useCallback(async () => {
    if (!sessionId) return;

    try {
      const data = await api.getSession(sessionId, token ?? undefined);
      setSession(data);
      setError(null);

      // Stop polling if active and stopOnActive is true
      if (stopOnActive && data.status !== 'pending' && intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch session');
    } finally {
      setLoading(false);
    }
  }, [sessionId, token, stopOnActive]);

  useEffect(() => {
    if (!sessionId) {
      setLoading(false);
      return;
    }

    fetchSession();

    if (pollInterval > 0) {
      intervalRef.current = window.setInterval(fetchSession, pollInterval);
      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      };
    }
  }, [sessionId, pollInterval, fetchSession]);

  return { session, loading, error, refetch: fetchSession };
}
