import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Plus, Trash2 } from 'lucide-react';

export default function Accounts() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ nit: '', login_password: '', cert_password: '', preferred_api: 'mobile' });
  const [error, setError] = useState('');

  const load = () => api.accounts.list().then(setAccounts).catch(() => {});
  useEffect(() => { load(); }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await api.accounts.create(form);
      setForm({ nit: '', login_password: '', cert_password: '', preferred_api: 'mobile' });
      setShowForm(false);
      load();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function deactivate(nit: string) {
    if (!confirm(`¿Desactivar cuenta ${nit}?`)) return;
    await api.accounts.deactivate(nit);
    load();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-white">Cuentas SAT</h2>
        <button onClick={() => setShowForm(!showForm)} className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm cursor-pointer">
          <Plus size={16} /> Nueva cuenta
        </button>
      </div>

      {showForm && (
        <form onSubmit={create} className="bg-bg-card rounded-xl border border-slate-700 p-5 mb-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <input value={form.nit} onChange={e => setForm({ ...form, nit: e.target.value })} placeholder="NIT" className="px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm" required />
            <select value={form.preferred_api} onChange={e => setForm({ ...form, preferred_api: e.target.value })} className="px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm">
              <option value="mobile">Mobile API</option>
              <option value="web">Web API</option>
            </select>
            <input type="password" value={form.login_password} onChange={e => setForm({ ...form, login_password: e.target.value })} placeholder="Contraseña login" className="px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm" required />
            <input type="password" value={form.cert_password} onChange={e => setForm({ ...form, cert_password: e.target.value })} placeholder="Contraseña certificación" className="px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm" required />
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button type="submit" className="px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm cursor-pointer">Crear</button>
        </form>
      )}

      <div className="bg-bg-card rounded-xl border border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-slate-400 text-left">
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
              <tr key={a.nit} className="border-b border-slate-700/50 last:border-0">
                <td className="px-4 py-3 text-white font-mono">{a.nit}</td>
                <td className="px-4 py-3 text-slate-300">{a.name || '—'}</td>
                <td className="px-4 py-3"><span className="px-2 py-0.5 rounded text-xs bg-slate-700 text-slate-300">{a.affiliation}</span></td>
                <td className="px-4 py-3 text-slate-400">{a.preferred_api}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs ${a.status === 'active' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
                    {a.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button onClick={() => deactivate(a.nit)} className="text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 size={16} /></button>
                </td>
              </tr>
            ))}
            {accounts.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-500">Sin cuentas registradas</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
