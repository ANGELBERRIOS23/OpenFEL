import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Plus, Trash2, Pencil, X, Search, Loader2 } from 'lucide-react';
import { useTheme } from '../lib/useThemeClasses';
import PasswordInput from '../components/PasswordInput';

const API_MODES = [
  { value: 'mixed', label: 'Mixta (fallback inteligente)' },
  { value: 'mobile', label: 'Solo Mobile' },
  { value: 'web', label: 'Solo Web' },
];

export default function Accounts() {
  const t = useTheme();
  const [accounts, setAccounts] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editNit, setEditNit] = useState<string | null>(null);
  const [form, setForm] = useState({ nit: '', login_password: '', cert_password: '', preferred_api: 'mixed', affiliation: 'GEN', name: '' });
  const [editForm, setEditForm] = useState({ login_password: '', cert_password: '', preferred_api: '', affiliation: '', name: '' });
  const [error, setError] = useState('');
  const [lookingUp, setLookingUp] = useState(false);
  const [nitHint, setNitHint] = useState('');

  const load = () => api.accounts.list().then(setAccounts).catch(() => {});
  useEffect(() => { load(); }, []);

  async function smartLookup() {
    if (!form.nit || form.nit.length < 4) { setNitHint('NIT muy corto'); return; }
    const activeAccount = accounts.find(a => a.status === 'active');
    if (!activeAccount) { setNitHint('Se necesita al menos una cuenta activa para buscar NIT'); return; }
    setLookingUp(true);
    setNitHint('');
    try {
      const res = await api.nit.lookup(activeAccount.nit, form.nit);
      const nombre = res.nombre || '';
      setForm(prev => ({ ...prev, name: nombre }));
      const lower = nombre.toLowerCase();
      if (lower.includes('pequeño contribuyente') || lower.includes('peq')) {
        setForm(prev => ({ ...prev, affiliation: 'PEQ' }));
        setNitHint(`${nombre} (auto-detectado: PEQ)`);
      } else {
        setForm(prev => ({ ...prev, affiliation: 'GEN' }));
        setNitHint(`${nombre} (auto-detectado: GEN)`);
      }
    } catch (err: any) {
      setNitHint(`Error: ${err.message}`);
    } finally {
      setLookingUp(false);
    }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await api.accounts.create(form);
      setForm({ nit: '', login_password: '', cert_password: '', preferred_api: 'mixed', affiliation: 'GEN', name: '' });
      setShowForm(false);
      setNitHint('');
      load();
    } catch (err: any) {
      setError(err.message);
    }
  }

  function startEdit(a: any) {
    setEditNit(a.nit);
    setEditForm({ login_password: '', cert_password: '', preferred_api: a.preferred_api, affiliation: a.affiliation, name: a.name || '' });
  }

  async function saveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editNit) return;
    setError('');
    try {
      const data: any = {};
      if (editForm.login_password) data.login_password = editForm.login_password;
      if (editForm.cert_password) data.cert_password = editForm.cert_password;
      data.preferred_api = editForm.preferred_api;
      data.affiliation = editForm.affiliation;
      data.name = editForm.name;
      await api.accounts.update(editNit, data);
      setEditNit(null);
      load();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function remove(nit: string) {
    if (!confirm(`¿Eliminar cuenta ${nit}? Esto es permanente.`)) return;
    await api.accounts.deactivate(nit);
    load();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className={`text-xl sm:text-2xl font-bold ${t.textH}`}>Cuentas SAT</h2>
        <button onClick={() => setShowForm(!showForm)} className="flex items-center gap-2 px-3 sm:px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm cursor-pointer">
          <Plus size={16} /> <span className="hidden sm:inline">Nueva cuenta</span>
        </button>
      </div>

      {showForm && (
        <form onSubmit={create} className={`rounded-xl border p-4 sm:p-5 mb-6 space-y-4 ${t.card}`}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={`${t.textXs} text-xs block mb-1`}>NIT</label>
              <div className="flex gap-2">
                <input value={form.nit} onChange={e => setForm({ ...form, nit: e.target.value })} placeholder="120405237" className={`flex-1 px-3 py-2 border rounded-lg text-sm ${t.input}`} required />
                <button type="button" onClick={smartLookup} disabled={lookingUp} className={`px-3 py-2 rounded-lg cursor-pointer ${t.btnSecondary} disabled:opacity-50`} title="Auto-detectar nombre y afiliación">
                  {lookingUp ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
                </button>
              </div>
              {nitHint && <p className={`text-xs mt-1 ${nitHint.startsWith('Error') ? 'text-red-400' : 'text-green-500'}`}>{nitHint}</p>}
            </div>
            <div>
              <label className={`${t.textXs} text-xs block mb-1`}>Nombre (opcional)</label>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Se auto-rellena con buscar NIT" className={`w-full px-3 py-2 border rounded-lg text-sm ${t.input}`} />
            </div>
            <select value={form.preferred_api} onChange={e => setForm({ ...form, preferred_api: e.target.value })} className={`px-3 py-2 border rounded-lg text-sm ${t.input}`}>
              {API_MODES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
            <select value={form.affiliation} onChange={e => setForm({ ...form, affiliation: e.target.value })} className={`px-3 py-2 border rounded-lg text-sm ${t.input}`}>
              <option value="GEN">GEN — General</option>
              <option value="PEQ">PEQ — Pequeño contribuyente</option>
            </select>
            <PasswordInput value={form.login_password} onChange={v => setForm({ ...form, login_password: v })} placeholder="Contraseña login" className={`px-3 py-2 border rounded-lg text-sm ${t.input}`} required />
            <PasswordInput value={form.cert_password} onChange={v => setForm({ ...form, cert_password: v })} placeholder="Contraseña certificación" className={`px-3 py-2 border rounded-lg text-sm ${t.input}`} required />
          </div>
          {error && !editNit && <p className="text-red-400 text-sm">{error}</p>}
          <button type="submit" className="px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm cursor-pointer">Crear</button>
        </form>
      )}

      {editNit && (
        <form onSubmit={saveEdit} className={`rounded-xl border p-4 sm:p-5 mb-6 space-y-4 ${t.card}`}>
          <div className="flex items-center justify-between mb-2">
            <h3 className={`font-semibold ${t.textH}`}>Editar {editNit}</h3>
            <button type="button" onClick={() => setEditNit(null)} className={`${t.textMuted} cursor-pointer`}><X size={18} /></button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} placeholder="Nombre (opcional)" className={`px-3 py-2 border rounded-lg text-sm ${t.input}`} />
            <select value={editForm.preferred_api} onChange={e => setEditForm({ ...editForm, preferred_api: e.target.value })} className={`px-3 py-2 border rounded-lg text-sm ${t.input}`}>
              {API_MODES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
            <PasswordInput value={editForm.login_password} onChange={v => setEditForm({ ...editForm, login_password: v })} placeholder="Nueva contraseña login (dejar vacío = no cambiar)" className={`px-3 py-2 border rounded-lg text-sm ${t.input}`} />
            <PasswordInput value={editForm.cert_password} onChange={v => setEditForm({ ...editForm, cert_password: v })} placeholder="Nueva contraseña certificación (dejar vacío = no cambiar)" className={`px-3 py-2 border rounded-lg text-sm ${t.input}`} />
            <select value={editForm.affiliation} onChange={e => setEditForm({ ...editForm, affiliation: e.target.value })} className={`px-3 py-2 border rounded-lg text-sm ${t.input}`}>
              <option value="GEN">GEN</option>
              <option value="PEQ">PEQ</option>
            </select>
          </div>
          {error && editNit && <p className="text-red-400 text-sm">{error}</p>}
          <button type="submit" className="px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm cursor-pointer">Guardar</button>
        </form>
      )}

      <div className={`rounded-xl border overflow-hidden ${t.card}`}>
        <div className="hidden sm:block overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className={`border-b ${t.border} ${t.textMuted} text-left`}>
                <th className="px-4 py-3">NIT</th>
                <th className="px-4 py-3">Nombre</th>
                <th className="px-4 py-3">Afiliación</th>
                <th className="px-4 py-3">API</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {accounts.map(a => (
                <tr key={a.nit} className={`border-b ${t.borderSub} last:border-0`}>
                  <td className={`px-4 py-3 ${t.textH} font-mono`}>{a.nit}</td>
                  <td className={`px-4 py-3 ${t.text}`}>{a.name || '—'}</td>
                  <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded text-xs ${a.affiliation === 'PEQ' ? t.badgeAmber : t.badge}`}>{a.affiliation}</span></td>
                  <td className={`px-4 py-3 ${t.textMuted}`}>{a.preferred_api}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${a.status === 'active' ? t.badgeGreen : t.badgeRed}`}>
                      {a.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 flex gap-2">
                    <button onClick={() => startEdit(a)} className={`${t.textMuted} hover:text-accent cursor-pointer`}><Pencil size={16} /></button>
                    <button onClick={() => remove(a.nit)} className={`${t.textMuted} hover:text-red-400 cursor-pointer`}><Trash2 size={16} /></button>
                  </td>
                </tr>
              ))}
              {accounts.length === 0 && (
                <tr><td colSpan={6} className={`px-4 py-8 text-center ${t.textXs}`}>Sin cuentas registradas</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="sm:hidden divide-y divide-slate-700/50">
          {accounts.map(a => (
            <div key={a.nit} className="p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className={`${t.textH} font-mono font-bold`}>{a.nit}</span>
                <span className={`px-2 py-0.5 rounded text-xs ${a.status === 'active' ? t.badgeGreen : t.badgeRed}`}>{a.status}</span>
              </div>
              <div className={`text-sm ${t.text}`}>{a.name || '—'} · {a.affiliation} · {a.preferred_api}</div>
              <div className="flex gap-2">
                <button onClick={() => startEdit(a)} className="text-xs text-accent cursor-pointer">Editar</button>
                <button onClick={() => remove(a.nit)} className="text-xs text-red-400 cursor-pointer">Eliminar</button>
              </div>
            </div>
          ))}
          {accounts.length === 0 && <p className={`p-4 text-center ${t.textXs}`}>Sin cuentas registradas</p>}
        </div>
      </div>
    </div>
  );
}
