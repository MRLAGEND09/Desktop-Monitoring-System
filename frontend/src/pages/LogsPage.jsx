import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { format } from 'date-fns';
import api from '../lib/api';

const CATEGORY_STYLES = {
  work:     'text-green-400 bg-green-900/30',
  'non-work': 'text-red-400 bg-red-900/30',
  unknown:  'text-gray-400 bg-gray-800',
};

export default function LogsPage() {
  const [deviceId, setDeviceId] = useState('');
  const [page,     setPage]     = useState(1);

  const { data: devices = [] } = useQuery({
    queryKey: ['devices'],
    queryFn:  () => api.get('/devices').then((r) => r.data),
  });

  const { data: logs = [], isLoading } = useQuery({
    queryKey: ['logs', deviceId, page],
    queryFn:  () => api.get('/logs', {
      params: { device_id: deviceId || undefined, page, page_size: 50 },
    }).then((r) => r.data),
    refetchInterval: 30_000,
  });

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-white">Activity Logs</h1>
        <select value={deviceId} onChange={(e) => { setDeviceId(e.target.value); setPage(1); }}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white
                     focus:outline-none focus:ring-2 focus:ring-brand-500">
          <option value="">All devices</option>
          {devices.map((d) => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
      </div>

      <div className="bg-gray-900 rounded-xl overflow-hidden border border-gray-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-left text-xs text-gray-500 uppercase tracking-wide">
              <th className="px-4 py-3">Time</th>
              <th className="px-4 py-3">Device</th>
              <th className="px-4 py-3">App</th>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3">Window</th>
              <th className="px-4 py-3">Idle</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 10 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 6 }).map((__, j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-4 bg-gray-800 rounded animate-pulse" />
                    </td>
                  ))}
                </tr>
              ))
            ) : logs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-gray-600">
                  No logs found
                </td>
              </tr>
            ) : logs.map((log) => (
              <tr key={log.id} className="border-t border-gray-800/50 hover:bg-gray-800/50">
                <td className="px-4 py-2.5 text-gray-400 whitespace-nowrap">
                  {format(new Date(log.created_at), 'HH:mm:ss')}
                </td>
                <td className="px-4 py-2.5 text-gray-300 max-w-[8rem] truncate">
                  {log.device_id.slice(0, 8)}…
                </td>
                <td className="px-4 py-2.5 text-white font-medium truncate max-w-[8rem]">
                  {log.active_app ?? '—'}
                </td>
                <td className="px-4 py-2.5">
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${CATEGORY_STYLES[log.app_category] ?? CATEGORY_STYLES.unknown}`}>
                    {log.app_category}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-gray-400 max-w-[16rem] truncate">
                  {log.window_title ?? '—'}
                </td>
                <td className="px-4 py-2.5 text-gray-400">
                  {log.is_idle ? `${log.idle_seconds}s` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Pagination */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800">
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}
            className="text-sm px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300
                       disabled:opacity-40 disabled:cursor-not-allowed">
            Previous
          </button>
          <span className="text-sm text-gray-500">Page {page}</span>
          <button disabled={logs.length < 50} onClick={() => setPage((p) => p + 1)}
            className="text-sm px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300
                       disabled:opacity-40 disabled:cursor-not-allowed">
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
