import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useRef } from 'react';
import { ArrowLeft, Maximize2 } from 'lucide-react';
import api from '../lib/api';
import { useWebRTC } from '../hooks/useWebRTC';
import StatusBadge from '../components/StatusBadge';

export default function DevicePage() {
  const { deviceId } = useParams();
  const navigate     = useNavigate();
  const frameRef     = useRef(null);
  const { status }   = useWebRTC(deviceId, frameRef);

  const { data: device } = useQuery({
    queryKey: ['device', deviceId],
    queryFn:  () => api.get(`/devices/${deviceId}`).then((r) => r.data),
    refetchInterval: 20_000,
  });

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate(-1)}
          className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white transition-colors">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-white">{device?.name ?? deviceId}</h1>
          <p className="text-sm text-gray-400">{device?.hostname}</p>
        </div>
        {device && <StatusBadge status={device.status} />}
      </div>

      {/* Live frame / video */}
      <div className="relative bg-black rounded-2xl overflow-hidden aspect-video shadow-2xl mb-6">
        <img ref={frameRef} alt="Live stream" className="w-full h-full object-contain" />
        {status !== 'live' && (
          <div className="absolute inset-0 flex items-center justify-center text-gray-500">
            {status === 'connecting' && <span className="animate-pulse">Connecting to stream…</span>}
            {status === 'error'      && <span className="text-red-400">Stream unavailable</span>}
            {status === 'idle'       && <span>Device is offline</span>}
          </div>
        )}
        {status === 'live' && (
          <button
            onClick={() => frameRef.current?.requestFullscreen?.()}
            className="absolute top-3 right-3 p-2 bg-black/50 hover:bg-black/70 rounded-lg text-white">
            <Maximize2 className="w-4 h-4" />
          </button>
        )}
      </div>

      {device && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'OS',         value: device.os_info    ?? '—' },
            { label: 'Active App', value: device.active_app ?? '—' },
            { label: 'IP',         value: device.ip_address ?? '—' },
            { label: 'Last Seen',  value: device.last_seen
                ? new Date(device.last_seen).toLocaleTimeString() : '—' },
          ].map(({ label, value }) => (
            <div key={label} className="bg-gray-900 rounded-xl px-4 py-3">
              <p className="text-xs text-gray-500 mb-0.5">{label}</p>
              <p className="text-sm font-medium text-white truncate">{value}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
