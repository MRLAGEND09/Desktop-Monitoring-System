import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { RefreshCw, Search } from 'lucide-react';
import api from '../lib/api';
import DeviceTile from '../components/DeviceTile';

export default function DashboardPage() {
  const [filter, setFilter] = useState('');

  const { data = [], isLoading, refetch } = useQuery({
    queryKey: ['devices'],
    queryFn:  () => api.get('/devices').then((r) => r.data),
    refetchInterval: 30_000,
  });

  const devices = data.filter(
    (d) => !filter || d.name?.toLowerCase().includes(filter.toLowerCase()),
  );

  const online = devices.filter((d) => d.status === 'online').length;
  const idle   = devices.filter((d) => d.status === 'idle').length;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white">Device Grid</h1>
          <p className="text-sm text-gray-400">
            {online} online · {idle} idle · {devices.length} total
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input value={filter} onChange={(e) => setFilter(e.target.value)}
              placeholder="Search devices…"
              className="bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-4 py-2 text-sm text-white
                         placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-500 w-48" />
          </div>
          <button onClick={() => refetch()}
            className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white transition-colors">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="aspect-video bg-gray-900 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : devices.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-gray-600">
          <p className="text-lg font-medium">No devices found</p>
          <p className="text-sm mt-1">
            {filter ? 'Try a different search term' : 'Register a desktop agent to get started'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-3">
          {devices.map((device) => (
            <DeviceTile key={device.id} device={device} />
          ))}
        </div>
      )}
    </div>
  );
}
