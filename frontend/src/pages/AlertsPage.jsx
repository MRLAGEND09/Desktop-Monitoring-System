import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { CheckCircle } from 'lucide-react';
import api from '../lib/api';
import { useAuthStore } from '../store/auth';
import { useSSE } from '../hooks/useSSE';

const SIGNAL_BASE = import.meta.env.VITE_API_URL || '';
const SSE_URL = `${SIGNAL_BASE}/api/stream/alerts`;

const SEVERITY_STYLES = {
  critical: 'text-red-400 bg-red-900/30 border-red-800',
  high:     'text-orange-400 bg-orange-900/30 border-orange-800',
  medium:   'text-yellow-400 bg-yellow-900/30 border-yellow-800',
  low:      'text-blue-400 bg-blue-900/30 border-blue-800',
};

export default function AlertsPage() {
  const qc           = useQueryClient();
  const user         = useAuthStore((s) => s.user);
  const canEdit      = ['admin', 'monitor'].includes(user?.role);
  const [showResolved, setShowResolved] = useState(false);

  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ['alerts'],
    queryFn:  () => api.get('/alerts').then((r) => r.data),
    refetchInterval: 60_000,
  });

  // Live push — invalidate query when a new alert arrives via SSE
  useSSE(SSE_URL, 'alert', () => {
    qc.invalidateQueries({ queryKey: ['alerts'] });
  }, { enabled: canEdit });

  const resolveMutation = useMutation({
    mutationFn: (id) => api.patch(`/alerts/${id}/resolve`),
    onSuccess:  () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  });

  const filtered = alerts.filter((a) => showResolved || !a.resolved_at);

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-white">Alerts</h1>
        <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
          <input type="checkbox" checked={showResolved}
            onChange={(e) => setShowResolved(e.target.checked)} className="rounded" />
          Show resolved
        </label>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[1,2,3].map((i) => <div key={i} className="h-16 bg-gray-900 rounded-xl animate-pulse" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="py-24 text-center text-gray-600">
          <CheckCircle className="w-10 h-10 mx-auto mb-3 text-green-700" />
          <p className="font-medium">No active alerts</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((alert) => (
            <div key={alert.id}
              className={`flex items-start gap-4 px-5 py-4 rounded-xl border
                ${SEVERITY_STYLES[alert.severity] ?? SEVERITY_STYLES.low}
                ${alert.resolved_at ? 'opacity-50' : ''}`}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs font-bold uppercase tracking-wide">{alert.severity}</span>
                  <span className="text-xs text-gray-500">{new Date(alert.created_at).toLocaleString()}</span>
                </div>
                <p className="text-sm font-medium text-white">{alert.message}</p>
                {alert.device_id && (
                  <p className="text-xs text-gray-500 mt-0.5">Device: {alert.device_id}</p>
                )}
              </div>
              {canEdit && !alert.resolved_at && (
                <button onClick={() => resolveMutation.mutate(alert.id)}
                  disabled={resolveMutation.isPending}
                  className="flex-shrink-0 text-xs px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700
                             text-gray-300 hover:text-white transition-colors disabled:opacity-50">
                  Resolve
                </button>
              )}
              {alert.resolved_at && (
                <span className="flex-shrink-0 text-xs text-green-500">Resolved</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
