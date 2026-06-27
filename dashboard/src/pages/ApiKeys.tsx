import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Plus, Trash2, Copy, Check } from 'lucide-react';
import { useTheme } from '../lib/useThemeClasses';

export default function ApiKeys() {
  const t = useTheme();
  const [keys, setKeys] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', role: 'VIEWER', allowed_accounts: [] as string[] });
  const [newKey, setNewKey] = useState('');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');

  const load = () => { api.keys.list().then(setKeys).catch(() => {}); api.accounts.list().then(setAccounts).catch(() => {}); };
  useEffect(() => { load(); }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      const result = await api.keys.create({
        ...form,
        allowed_accounts: form.allowed_accounts.length > 0 ? form.allowed_accounts : [],
      });
      setNewKey(result.full_key);
      setForm({ name: '', role: 'VIEWER', allowed_accounts: [] });
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

  function toggleAccount(nit: string) {
    setForm(prev => ({
      ...prev,
      allowed_accounts: prev.allowed_accounts.includes(nit)
        ? prev.allowed_accounts.filter(n => n !== nit)
        : [...prev.allowed_accounts, nit],
    }));
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className={`text-xl sm:text-2xl font-bold ${t.textH}`}>API Keys</h2>
        <button onClick={() => setShowForm(!showForm)} className="flex items-center gap-2 px-3 sm:px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm cursor-pointer">
          <Plus size={16} /> <span className="hidden sm:inline">Nueva key</span>
        </button>
      </div>

      {newKey && (
        <div className="bg-green-900/20 border border-green-700 rounded-xl p-4 mb-6">
          <p className="text-green-400 text-sm font-semibold mb-2">Key creada — cópiala ahora, no se mostrará de nuevo:</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-slate-800 px-3 py-2 rounded text-green-300 text-xs sm:text-sm font-mono break-all">{newKey}</code>
            <button onClick={copyKey} className="p-2 text-green-400 hover:text-green-300 cursor-pointer shrink-0">
              {copied ? <Check size={18} /> : <Copy size={18} />}
            </button>
          </div>
          <button onClick={() => setNewKey('')} className={`mt-2 ${t.textMuted} text-xs hover:text-white cursor-pointer`}>Cerrar</button>
        </div>
      )}

      {showForm && (
        <form onSubmit={create} className={`rounded-xl border p-4 sm:p-5 mb-6 space-y-4 ${t.card}`}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Nombre (ej: Production)" className={`px-3 py-2 border rounded-lg text-sm ${t.input}`} required />
            <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })} className={`px-3 py-2 border rounded-lg text-sm ${t.input}`}>
              <option value="VIEWER">VIEWER — Solo lectura</option>
              <option value="OPERATOR">OPERATOR — Emitir + anular</option>
              <option value="ADMIN">ADMIN — Control total</option>
            </select>
          </div>
          {accounts.length > 0 && (
            <div>
              <p className={`text-xs ${t.textMuted} mb-2`}>Restringir a cuentas (vacío = todas):</p>
              <div className="flex flex-wrap gap-2">
                {accounts.map(a => (
                  <button
                    key={a.nit}
                    type="button"
                    onClick={() => toggleAccount(a.nit)}
                    className={`px-3 py-1 rounded-lg text-xs cursor-pointer border ${
                      form.allowed_accounts.includes(a.nit)
                        ? 'bg-accent/20 border-accent text-accent'
                        : `${t.badge} ${t.border}`
                    }`}
                  >
                    {a.nit}
                  </button>
                ))}
              </div>
            </div>
          )}
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button type="submit" className="px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm cursor-pointer">Generar key</button>
        </form>
      )}

      <div className={`rounded-xl border overflow-hidden ${t.card}`}>
        <div className="hidden sm:block overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className={`border-b ${t.border} ${t.textMuted} text-left`}>
                <th className="px-4 py-3">Nombre</th>
                <th className="px-4 py-3">Prefijo</th>
                <th className="px-4 py-3">Rol</th>
                <th className="px-4 py-3">Cuentas</th>
                <th className="px-4 py-3">Usos</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {keys.map(k => {
                const allowed = k.allowed_accounts ? JSON.parse(k.allowed_accounts) : [];
                return (
                  <tr key={k.id} className={`border-b ${t.borderSub} last:border-0`}>
                    <td className={`px-4 py-3 ${t.textH}`}>{k.name}</td>
                    <td className={`px-4 py-3 font-mono ${t.textMuted} text-xs`}>{k.key_prefix}...</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        k.role === 'ADMIN' ? 'bg-purple-900/30 text-purple-400' :
                        k.role === 'OPERATOR' ? 'bg-blue-900/30 text-blue-400' :
                        `${t.badge}`
                      }`}>{k.role}</span>
                    </td>
                    <td className={`px-4 py-3 ${t.textMuted} text-xs`}>{allowed.length > 0 ? allowed.join(', ') : 'Todas'}</td>
                    <td className={`px-4 py-3 ${t.textMuted}`}>{k.usage_count}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${k.is_active ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
                        {k.is_active ? 'Activa' : 'Revocada'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {k.is_active && <button onClick={() => revoke(k.id)} className={`${t.textMuted} hover:text-red-400 cursor-pointer`}><Trash2 size={16} /></button>}
                    </td>
                  </tr>
                );
              })}
              {keys.length === 0 && (
                <tr><td colSpan={7} className={`px-4 py-8 text-center ${t.textXs}`}>Sin API keys</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {/* Mobile cards */}
        <div className="sm:hidden divide-y divide-slate-700/50">
          {keys.map(k => (
            <div key={k.id} className="p-4 space-y-1">
              <div className="flex items-center justify-between">
                <span className={`${t.textH} font-semibold`}>{k.name}</span>
                <span className={`px-2 py-0.5 rounded text-xs ${k.is_active ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
                  {k.is_active ? 'Activa' : 'Revocada'}
                </span>
              </div>
              <div className={`text-xs font-mono ${t.textMuted}`}>{k.key_prefix}...</div>
              <div className={`text-xs ${t.text}`}>{k.role} · {k.usage_count} usos</div>
              {k.is_active && <button onClick={() => revoke(k.id)} className="text-xs text-red-400 cursor-pointer">Revocar</button>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
