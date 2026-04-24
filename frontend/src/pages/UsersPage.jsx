/**
 * UsersPage — admin-only user management
 * Create, role-change, deactivate/reactivate users.
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { UserPlus, ShieldCheck, Eye, Monitor, Trash2 } from 'lucide-react';
import api from '../lib/api';
import { useAuthStore } from '../store/auth';

const ROLES = ['admin', 'monitor', 'viewer'];

const ROLE_ICON = {
  admin:   <ShieldCheck className="w-3.5 h-3.5" />,
  monitor: <Monitor     className="w-3.5 h-3.5" />,
  viewer:  <Eye         className="w-3.5 h-3.5" />,
};

const ROLE_COLOR = {
  admin:   'text-red-400   bg-red-900/30   border-red-800',
  monitor: 'text-yellow-400 bg-yellow-900/30 border-yellow-800',
  viewer:  'text-blue-400  bg-blue-900/30  border-blue-800',
};

function RoleBadge({ role }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full
      text-xs font-medium border ${ROLE_COLOR[role] ?? ''}`}>
      {ROLE_ICON[role]}{role}
    </span>
  );
}

function CreateUserModal({ onClose, onCreate }) {
  const [form, setForm] = useState({ username: '', password: '', role: 'viewer' });
  const [error, setError] = useState('');

  const mut = useMutation({
    mutationFn: (data) => api.post('/users', data).then((r) => r.data),
    onSuccess: (u) => { onCreate(u); onClose(); },
    onError:   (e) => setError(e.response?.data?.detail ?? 'Error creating user'),
  });

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 w-full max-w-md shadow-2xl">
        <h2 className="text-lg font-bold text-white mb-5">New User</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Username</label>
            <input className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2
                              text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-600"
              placeholder="e.g. jane.smith"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Password</label>
            <input type="password"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2
                         text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-600"
              placeholder="••••••••••••"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <p className="text-xs text-gray-500 mt-1">
              Min 10 chars · must include uppercase, lowercase, digit &amp; special character
            </p>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Role</label>
            <select className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2
                               text-sm text-white focus:outline-none focus:border-blue-600"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          {error && <p className="text-xs text-red-400">{error}</p>}
        </div>
        <div className="flex gap-3 mt-6">
          <button onClick={onClose}
            className="flex-1 px-4 py-2 rounded-lg border border-gray-700 text-sm
                       text-gray-400 hover:text-white hover:border-gray-600 transition-colors">
            Cancel
          </button>
          <button
            disabled={mut.isPending || !form.username || form.password.length < 10}
            onClick={() => mut.mutate(form)}
            className="flex-1 px-4 py-2 rounded-lg bg-blue-700 hover:bg-blue-600 text-white
                       text-sm font-medium transition-colors disabled:opacity-50">
            {mut.isPending ? 'Creating…' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function UsersPage() {
  const qc        = useQueryClient();
  const me        = useAuthStore((s) => s.user);
  const [showNew, setShowNew] = useState(false);

  const { data: users = [], isLoading } = useQuery({
    queryKey: ['users'],
    queryFn:  () => api.get('/users').then((r) => r.data),
  });

  const patchMut = useMutation({
    mutationFn: ({ id, ...body }) => api.patch(`/users/${id}`, body),
    onSuccess:  () => qc.invalidateQueries({ queryKey: ['users'] }),
  });

  const handleRoleChange = (id, role) => patchMut.mutate({ id, role });
  const handleToggle     = (id, is_active) => patchMut.mutate({ id, is_active });

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-white">Users</h1>
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-700
                     hover:bg-blue-600 text-white text-sm font-medium transition-colors">
          <UserPlus className="w-4 h-4" />New User
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[1,2,3].map((i) => <div key={i} className="h-14 bg-gray-900 rounded-xl animate-pulse" />)}
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase tracking-wide">
                <th className="text-left px-5 py-3">Username</th>
                <th className="text-left px-5 py-3">Role</th>
                <th className="text-left px-5 py-3">Status</th>
                <th className="text-left px-5 py-3">Created</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {users.map((u) => (
                <tr key={u.id} className={`transition-colors ${!u.is_active ? 'opacity-40' : ''}`}>
                  <td className="px-5 py-3.5 font-medium text-white">
                    {u.username}
                    {u.id === me?.id && (
                      <span className="ml-2 text-xs text-blue-400">(you)</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5">
                    {u.id === me?.id ? (
                      <RoleBadge role={u.role} />
                    ) : (
                      <select
                        value={u.role}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                        className="bg-gray-800 border border-gray-700 rounded-lg px-2 py-1
                                   text-xs text-white focus:outline-none focus:border-blue-600">
                        {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    )}
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={`text-xs font-medium ${u.is_active ? 'text-green-400' : 'text-gray-600'}`}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-gray-500 text-xs">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    {u.id !== me?.id && (
                      <button
                        onClick={() => handleToggle(u.id, !u.is_active)}
                        disabled={patchMut.isPending}
                        className="text-xs px-3 py-1.5 rounded-lg border border-gray-700
                                   text-gray-400 hover:text-white hover:border-gray-600
                                   transition-colors disabled:opacity-50">
                        {u.is_active ? 'Deactivate' : 'Reactivate'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showNew && (
        <CreateUserModal
          onClose={() => setShowNew(false)}
          onCreate={() => qc.invalidateQueries({ queryKey: ['users'] })}
        />
      )}
    </div>
  );
}
