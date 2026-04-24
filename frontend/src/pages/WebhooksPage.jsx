/**
 * WebhooksPage — admin-only webhook subscription management
 * Register URLs, filter by severity, test delivery, delete.
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, Send, CheckCircle, XCircle } from 'lucide-react';
import api from '../lib/api';

const SEVERITIES = ['low', 'medium', 'high', 'critical'];

const SEV_COLOR = {
  critical: 'text-red-400',
  high:     'text-orange-400',
  medium:   'text-yellow-400',
  low:      'text-blue-400',
};

function NewWebhookModal({ onClose }) {
  const qc = useQueryClient();
  const [url, setUrl]       = useState('');
  const [filter, setFilter] = useState([]);
  const [secret, setSecret] = useState('');
  const [created, setCreated] = useState(null);
  const [error, setError]   = useState('');

  const mut = useMutation({
    mutationFn: (body) => api.post('/webhooks', body).then((r) => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['webhooks'] });
      setCreated(data);
    },
    onError: (e) => setError(e.response?.data?.detail ?? 'Error'),
  });

  const toggleSev = (s) =>
    setFilter((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]);

  if (created) {
    return (
      <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 w-full max-w-md shadow-2xl">
          <div className="flex items-center gap-2 text-green-400 mb-3">
            <CheckCircle className="w-5 h-5" />
            <span className="font-semibold">Webhook created</span>
          </div>
          <p className="text-xs text-gray-400 mb-2">
            Save this secret — it won't be shown again:
          </p>
          <pre className="bg-gray-800 text-green-300 text-xs rounded-lg p-3 break-all whitespace-pre-wrap mb-5">
            {created.secret}
          </pre>
          <button onClick={onClose}
            className="w-full px-4 py-2 rounded-lg bg-blue-700 hover:bg-blue-600
                       text-white text-sm font-medium transition-colors">
            Done
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 w-full max-w-md shadow-2xl">
        <h2 className="text-lg font-bold text-white mb-5">Register Webhook</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Endpoint URL</label>
            <input className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2
                              text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-600"
              placeholder="https://hooks.example.com/rdm"
              value={url} onChange={(e) => setUrl(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-2">
              Severity filter <span className="text-gray-600">(empty = all severities)</span>
            </label>
            <div className="flex gap-2 flex-wrap">
              {SEVERITIES.map((s) => (
                <button key={s} type="button"
                  onClick={() => toggleSev(s)}
                  className={`px-3 py-1 rounded-full border text-xs font-medium transition-colors
                    ${filter.includes(s)
                      ? `${SEV_COLOR[s]} border-current bg-gray-800`
                      : 'text-gray-600 border-gray-700 hover:border-gray-600'}`}>
                  {s}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Signing secret <span className="text-gray-600">(optional — auto-generated if blank)</span>
            </label>
            <input className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2
                              text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-600"
              placeholder="Leave blank to auto-generate"
              value={secret} onChange={(e) => setSecret(e.target.value)} />
          </div>
          {error && <p className="text-xs text-red-400">{error}</p>}
        </div>
        <div className="flex gap-3 mt-6">
          <button onClick={onClose}
            className="flex-1 px-4 py-2 rounded-lg border border-gray-700 text-sm
                       text-gray-400 hover:text-white transition-colors">
            Cancel
          </button>
          <button
            disabled={mut.isPending || !url.startsWith('http')}
            onClick={() => mut.mutate({
              url,
              severity_filter: filter.join(','),
              ...(secret ? { secret } : {}),
            })}
            className="flex-1 px-4 py-2 rounded-lg bg-blue-700 hover:bg-blue-600 text-white
                       text-sm font-medium transition-colors disabled:opacity-50">
            {mut.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function WebhooksPage() {
  const qc         = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [testing, setTesting] = useState(null);   // id being tested
  const [testResult, setTestResult] = useState({}); // id → 'ok' | 'fail'

  const { data: hooks = [], isLoading } = useQuery({
    queryKey: ['webhooks'],
    queryFn:  () => api.get('/webhooks').then((r) => r.data),
  });

  const deleteMut = useMutation({
    mutationFn: (id) => api.delete(`/webhooks/${id}`),
    onSuccess:  () => qc.invalidateQueries({ queryKey: ['webhooks'] }),
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, is_active }) => api.patch(`/webhooks/${id}`, { is_active }),
    onSuccess:  () => qc.invalidateQueries({ queryKey: ['webhooks'] }),
  });

  const testHook = async (id) => {
    setTesting(id);
    try {
      await api.post(`/webhooks/${id}/test`);
      setTestResult((r) => ({ ...r, [id]: 'ok' }));
    } catch {
      setTestResult((r) => ({ ...r, [id]: 'fail' }));
    } finally {
      setTesting(null);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-white">Webhooks</h1>
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-700
                     hover:bg-blue-600 text-white text-sm font-medium transition-colors">
          <Plus className="w-4 h-4" />Register
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[1,2].map((i) => <div key={i} className="h-16 bg-gray-900 rounded-xl animate-pulse" />)}
        </div>
      ) : hooks.length === 0 ? (
        <div className="py-20 text-center text-gray-600">
          <p>No webhooks registered. Webhooks fire on every new alert.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {hooks.map((h) => (
            <div key={h.id}
              className={`bg-gray-900 border border-gray-800 rounded-2xl px-5 py-4
                          flex items-center gap-4 ${!h.is_active ? 'opacity-50' : ''}`}>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-mono text-white truncate">{h.url}</p>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs text-gray-500">
                    Secret: <code className="text-gray-400">{h.secret_hint ?? '—'}…</code>
                  </span>
                  {h.severity_filter ? (
                    <span className="text-xs text-gray-500">
                      Filter: {h.severity_filter.split(',').map((s) => (
                        <span key={s} className={`mr-1 font-medium ${SEV_COLOR[s] ?? ''}`}>{s}</span>
                      ))}
                    </span>
                  ) : (
                    <span className="text-xs text-gray-600">All severities</span>
                  )}
                  <span className="text-xs text-gray-600">
                    Since {new Date(h.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0">
                {testResult[h.id] === 'ok'   && <CheckCircle className="w-4 h-4 text-green-400" />}
                {testResult[h.id] === 'fail'  && <XCircle     className="w-4 h-4 text-red-400"   />}
                <button
                  onClick={() => testHook(h.id)}
                  disabled={testing === h.id}
                  title="Send test payload"
                  className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800
                             transition-colors disabled:opacity-40">
                  <Send className="w-4 h-4" />
                </button>
                <button
                  onClick={() => toggleMut.mutate({ id: h.id, is_active: !h.is_active })}
                  className="text-xs px-3 py-1.5 rounded-lg border border-gray-700 text-gray-400
                             hover:text-white hover:border-gray-600 transition-colors">
                  {h.is_active ? 'Disable' : 'Enable'}
                </button>
                <button
                  onClick={() => { if (confirm('Delete this webhook?')) deleteMut.mutate(h.id); }}
                  className="p-1.5 rounded-lg text-gray-600 hover:text-red-400 hover:bg-gray-800
                             transition-colors">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showNew && <NewWebhookModal onClose={() => setShowNew(false)} />}
    </div>
  );
}
