import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Search, XCircle } from 'lucide-react';
import { useTheme } from '../lib/useThemeClasses';

export default function Query() {
  const t = useTheme();
  const [accounts, setAccounts] = useState<any[]>([]);
  const [accountNit, setAccountNit] = useState('');
  const [tab, setTab] = useState<'emitted' | 'received'>('emitted');
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [annulResult, setAnnulResult] = useState('');

  useEffect(() => { api.accounts.list().then(setAccounts).catch(() => {}); }, []);

  async function search() {
    if (!accountNit) return;
    setLoading(true);
    setError('');
    setAnnulResult('');
    try {
      const res = tab === 'emitted'
        ? await api.dte.emitted(accountNit)
        : await api.dte.received(accountNit);
      setItems(res.items || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function annul(uuid: string) {
    if (!confirm(`¿Anular DTE ${uuid}?`)) return;
    try {
      const res = await api.dte.annul({ account_nit: accountNit, uuid });
      setAnnulResult(`${uuid}: ${res.estado}`);
      search();
    } catch (err: any) {
      setAnnulResult(`Error: ${err.message}`);
    }
  }

  return (
    <div>
      <h2 className={`text-xl sm:text-2xl font-bold ${t.textH} mb-6`}>Consultar DTEs</h2>

      <div className="flex flex-col sm:flex-row items-start sm:items-end gap-3 mb-6">
        <div>
          <label className={`${t.textMuted} text-xs block mb-1`}>Cuenta</label>
          <select value={accountNit} onChange={e => setAccountNit(e.target.value)} className={`px-3 py-2 border rounded-lg text-sm ${t.input}`}>
            <option value="">Seleccionar...</option>
            {accounts.filter(a => a.status === 'active').map(a => (
              <option key={a.nit} value={a.nit}>{a.nit}</option>
            ))}
          </select>
        </div>
        <div className={`flex rounded-lg overflow-hidden border ${t.border}`}>
          <button onClick={() => setTab('emitted')} className={`px-4 py-2 text-sm cursor-pointer ${tab === 'emitted' ? 'bg-accent text-white' : `${t.text} ${t.isDark ? 'bg-slate-800' : 'bg-slate-50'}`}`}>Emitidos</button>
          <button onClick={() => setTab('received')} className={`px-4 py-2 text-sm cursor-pointer ${tab === 'received' ? 'bg-accent text-white' : `${t.text} ${t.isDark ? 'bg-slate-800' : 'bg-slate-50'}`}`}>Recibidos</button>
        </div>
        <button onClick={search} disabled={loading || !accountNit} className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm disabled:opacity-50 cursor-pointer">
          <Search size={16} /> {loading ? 'Buscando...' : 'Buscar'}
        </button>
      </div>

      {error && <p className="text-red-400 text-sm mb-4">{error}</p>}
      {annulResult && <p className="text-amber-400 text-sm mb-4">{annulResult}</p>}

      {/* Desktop table */}
      <div className={`rounded-xl border overflow-hidden ${t.card} hidden sm:block`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className={`border-b ${t.border} ${t.textMuted} text-left`}>
                <th className="px-4 py-3">UUID</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Fecha</th>
                <th className="px-4 py-3">Receptor</th>
                <th className="px-4 py-3">Total</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item: any, i: number) => {
                const uuid = item.uuid || item.UUID || item.numeroAutorizacion || '';
                const estado = item.estado || item.Estado || item.estadoDte || '';
                return (
                  <tr key={i} className={`border-b ${t.borderSub} last:border-0`}>
                    <td className={`px-4 py-3 font-mono text-xs ${t.text}`}>{uuid.slice(0, 8)}...</td>
                    <td className={`px-4 py-3 ${t.textH}`}>{item.tipo || item.Tipo || item.tipoDocumento || '—'}</td>
                    <td className={`px-4 py-3 ${t.textMuted}`}>{item.fecha || item.FechaEmision || item.fechaEmision || '—'}</td>
                    <td className={`px-4 py-3 ${t.text}`}>{item.receptor || item.NombreReceptor || item.nombreReceptor || '—'}</td>
                    <td className={`px-4 py-3 ${t.textH}`}>Q{item.total || item.MontoTotal || item.montoTotal || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${estado === 'A' || estado === 'Anulado' ? 'bg-red-900/30 text-red-400' : 'bg-green-900/30 text-green-400'}`}>
                        {estado === 'A' || estado === 'Anulado' ? 'Anulado' : 'Vigente'}
                      </span>
                    </td>
                    <td className="px-4 py-3 flex gap-2">
                      {estado !== 'A' && estado !== 'Anulado' && (
                        <button onClick={() => annul(uuid)} className={`${t.textMuted} hover:text-red-400 cursor-pointer`} title="Anular"><XCircle size={14} /></button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {items.length === 0 && (
                <tr><td colSpan={7} className={`px-4 py-8 text-center ${t.textXs}`}>{loading ? 'Cargando...' : 'Selecciona una cuenta y busca'}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Mobile cards */}
      <div className={`sm:hidden rounded-xl border ${t.card} divide-y ${t.borderSub}`}>
        {items.map((item: any, i: number) => {
          const uuid = item.uuid || item.UUID || item.numeroAutorizacion || '';
          const estado = item.estado || item.Estado || item.estadoDte || '';
          return (
            <div key={i} className="p-4 space-y-1">
              <div className="flex justify-between">
                <span className={`font-mono text-xs ${t.text}`}>{uuid.slice(0, 12)}...</span>
                <span className={`px-2 py-0.5 rounded text-xs ${estado === 'A' ? 'bg-red-900/30 text-red-400' : 'bg-green-900/30 text-green-400'}`}>
                  {estado === 'A' ? 'Anulado' : 'Vigente'}
                </span>
              </div>
              <div className={`text-sm ${t.textH}`}>{item.tipo || item.Tipo || '—'} · Q{item.total || item.MontoTotal || '—'}</div>
              <div className={`text-xs ${t.textMuted}`}>{item.fecha || item.FechaEmision || '—'}</div>
              {estado !== 'A' && <button onClick={() => annul(uuid)} className="text-xs text-red-400 cursor-pointer">Anular</button>}
            </div>
          );
        })}
        {items.length === 0 && <p className={`p-4 text-center ${t.textXs}`}>{loading ? 'Cargando...' : 'Selecciona una cuenta y busca'}</p>}
      </div>
    </div>
  );
}
