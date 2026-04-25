/**
 * AlertToast — floats in the top-right corner when a live SSE alert arrives.
 * Auto-dismisses after 8 seconds. Stacks up to 5 toasts.
 *
 * Usage: mount once in Layout; it listens to the SSE stream independently.
 */
import { useState, useCallback } from 'react';
import { X, AlertTriangle } from 'lucide-react';
import { useSSE } from '../hooks/useSSE';
import { useAuthStore } from '../store/auth';

const SIGNAL_BASE = import.meta.env.VITE_API_URL || '';
const SSE_URL     = `${SIGNAL_BASE}/api/stream/alerts`;
const AUTO_CLOSE  = 8_000;

const SEVERITY_RING = {
  critical: 'border-red-500 bg-red-950 text-red-200',
  high:     'border-orange-500 bg-orange-950 text-orange-200',
  medium:   'border-yellow-500 bg-yellow-950 text-yellow-200',
  low:      'border-blue-500 bg-blue-950 text-blue-200',
};

let _nextId = 1;

export default function AlertToast() {
  const user = useAuthStore((s) => s.user);
  const canMonitor = ['admin', 'monitor'].includes(user?.role);

  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback((data) => {
    const id = _nextId++;
    setToasts((prev) => [{ id, ...data }, ...prev].slice(0, 5));
    setTimeout(() => dismiss(id), AUTO_CLOSE);
  }, [dismiss]);

  useSSE(SSE_URL, 'alert', addToast, { enabled: canMonitor });

  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      className="fixed top-4 right-4 z-50 flex flex-col gap-2 w-80"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-start gap-3 px-4 py-3 rounded-xl border shadow-lg
            ${SEVERITY_RING[t.severity] ?? SEVERITY_RING.low}
            animate-fade-in`}
        >
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-bold uppercase tracking-wide mb-0.5">
              {t.severity} alert
            </p>
            <p className="text-sm leading-snug line-clamp-3">{t.message}</p>
            {t.device_id && (
              <p className="text-xs opacity-60 mt-1 truncate">
                Device {t.device_id}
              </p>
            )}
          </div>
          <button
            onClick={() => dismiss(t.id)}
            className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
            aria-label="Dismiss"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
