/**
 * useAlertBadge — counts unresolved alerts for the sidebar badge.
 * Uses the SSE stream to increment without full refetch.
 */
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api';
import { useSSE } from './useSSE';
import { useAuthStore } from '../store/auth';

const SIGNAL_BASE = import.meta.env.VITE_API_URL || '';
const SSE_URL = `${SIGNAL_BASE}/api/stream/alerts`;

export function useAlertBadge() {
  const user       = useAuthStore((s) => s.user);
  const qc         = useQueryClient();
  const canMonitor = ['admin', 'monitor'].includes(user?.role);

  const { data: alerts = [] } = useQuery({
    queryKey: ['alerts'],
    queryFn:  () => api.get('/alerts').then((r) => r.data),
    refetchInterval: 60_000,
  });

  const [liveCount, setLiveCount] = useState(0);

  useSSE(SSE_URL, 'alert', () => {
    setLiveCount((c) => c + 1);
    // Invalidate so the AlertsPage reflects new data next visit
    qc.invalidateQueries({ queryKey: ['alerts'] });
  }, { enabled: canMonitor });

  const unresolvedBase = alerts.filter((a) => !a.resolved_at).length;
  const total = unresolvedBase + liveCount;

  return total > 0 ? total : null;
}
