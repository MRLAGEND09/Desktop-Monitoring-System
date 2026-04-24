import { useNavigate } from 'react-router-dom';
import { useRef } from 'react';
import { useWebRTC } from '../hooks/useWebRTC';
import StatusBadge from './StatusBadge';

export default function DeviceTile({ device }) {
  const navigate = useNavigate();
  // Use <img> for JPEG frame fallback; <video> for WebRTC MediaStream
  const frameRef = useRef(null);
  const { status } = useWebRTC(device.id, frameRef);

  return (
    <div
      className="relative group bg-gray-900 rounded-xl overflow-hidden cursor-pointer
                 border border-gray-800 hover:border-brand-500 transition-colors aspect-video"
      onClick={() => navigate(`/device/${device.id}`)}
      role="button"
      aria-label={`View ${device.name}`}
    >
      {/* JPEG frame display */}
      <img
        ref={frameRef}
        alt=""
        className="w-full h-full object-contain bg-black"
      />

      {status !== 'live' && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/90">
          {status === 'connecting' && <span className="text-xs text-gray-400 animate-pulse">Connecting…</span>}
          {status === 'error'      && <span className="text-xs text-red-400">Unavailable</span>}
          {status === 'idle'       && <span className="text-xs text-gray-500">Offline</span>}
        </div>
      )}

      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent
                      px-3 py-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-white truncate">{device.name}</span>
          <StatusBadge status={device.status} />
        </div>
        {device.active_app && (
          <span className="text-xs text-gray-400 truncate block">{device.active_app}</span>
        )}
      </div>
    </div>
  );
}
