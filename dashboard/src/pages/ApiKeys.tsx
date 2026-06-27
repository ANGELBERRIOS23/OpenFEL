import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Plus, Trash2, Copy, Check } from 'lucide-react';

export default function ApiKeys() {
  const [keys, setKeys] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', role: 'VIEWER' });
  const [newKey, setNewKey] = useState('');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');

  const load = () => api.keys.list().then(setKeys).catch(() => {});
  useEffect(() => { load(); }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      const result = await api.keys.create(form);
      setNewKey(result.full_key);
      setForm({ name: '', role: 'VIEWER' });
      setShowForm(false);
      load();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function revoke(id: number) {
    if (!confirm('¿Revocar esta API key?')) return;
    await api.keys.revoke(id);
    load();
  }

  function copyKey() {
    navigator.clipboard.writeText(newKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-white">API Keys</h2>
        <button onClick={() => setShowForm(!showForm)} className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm cursor-pointer">
          <Plus size={16} /> Nueva key
        </button>
      </div>

      {newKey && (
        <div className="bg-green-900/20 border border-green-700 rounded-xl p-4 mb-6">
          <p className="text-green-400 text-sm font-semibold mb-2">Key creada — cópiala ahora, no se mostrará de nuevo:</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-slate-800 px-3 py-2 rounded text-green-300 text-sm font-mono break-all">{newKey}</code>
            <button onClick={copyKey} className="p-2 text-green-400 hover:text-green-300 cursor-pointer">
              {copied ? <Check size={18} /> : <Copy size={18} />}
            </button>
          </div>
          <button onClick={() => setNewKey('')} className="mt-2 text-slate-400 text-xs hover:text-white cursor-pointer">Cerrar</button>
        </div>
      )}

      {showForm && (
        <form onSubmit={create} className="bg-bg-card rounded-xl border border-slate-700 p-5 mb-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Nombre (ej: Production)" className="px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm" required />
            <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })} className="px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm">
              <option value="VIEWER">VIEWER — Solo lectura</option>
              <option value="OPERATOR">OPERATOR — Emitir + anular</option>
              <option value="ADMIN">ADMIN — Control total</option>
            </select>
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button type="submit" className="px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm cursor-pointer">Generar key</button>
        </form>
      )}

      <div className="bg-bg-card rounded-xl border border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-slate-400 text-left">
              <th className="px-4 py-3">Nombre</th>
              <th className="px-4 py-3">Prefijo</th>
              <th className="px-4 py-3">Rol</th>
              <th className="px-4 py-3">Usos</th>
              <th className="px-4 py-3">Estado</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {keys.map(k => (
              <tr key={k.id} className="border-b border-slate-700/50 last:border-0">
                <td className="px-4 py-3 text-white">{k.name}</td>
                <td className="px-4 py-3 font-mono text-slate-400 text-xs">{k.key_prefix}...</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    k.role === 'ADMIN' ? 'bg-purple-900/30 text-purple-400' :
                    k.role === 'OPERATOR' ? 'bg-blue-900/30 text-blue-400' :
                    'bg-slate-700 text-slate-300'
                  }`}>{k.role}</span>
                </td>
                <td className="px-4 py-3 text-slate-400">{k.usage_count}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs ${k.is_active ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
                    {k.is_active ? 'Activa' : 'Revocada'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {k.is_active && <button onClick={() => revoke(k.id)} className="text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 size={16} /></button>}
                </td>
              </tr>
            ))}
            {keys.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-500">Sin API keys</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
