import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Search, XCircle, FileText } from 'lucide-react';

export default function Query() {
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

  function downloadPdf(uuid: string) {
    const key = sessionStorage.getItem('openfel_key') || '';
    window.open(`/api/dte/${uuid}/pdf?account_nit=${accountNit}&X-API-Key=${key}`, '_blank');
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-white mb-6">Consultar DTEs</h2>

      <div className="flex items-end gap-4 mb-6">
        <div>
          <label className="text-slate-400 text-xs block mb-1">Cuenta</label>
          <select value={accountNit} onChange={e => setAccountNit(e.target.value)} className="px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm">
            <option value="">Seleccionar...</option>
            {accounts.filter(a => a.status === 'active').map(a => (
              <option key={a.nit} value={a.nit}>{a.nit}</option>
            ))}
          </select>
        </div>
        <div className="flex bg-slate-800 rounded-lg overflow-hidden border border-slate-600">
          <button onClick={() => setTab('emitted')} className={`px-4 py-2 text-sm cursor-pointer ${tab === 'emitted' ? 'bg-accent text-white' : 'text-slate-400'}`}>Emitidos</button>
          <button onClick={() => setTab('received')} className={`px-4 py-2 text-sm cursor-pointer ${tab === 'received' ? 'bg-accent text-white' : 'text-slate-400'}`}>Recibidos</button>
        </div>
        <button onClick={search} disabled={loading || !accountNit} className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm disabled:opacity-50 cursor-pointer">
          <Search size={16} /> {loading ? 'Buscando...' : 'Buscar'}
        </button>
      </div>

      {error && <p className="text-red-400 text-sm mb-4">{error}</p>}
      {annulResult && <p className="text-amber-400 text-sm mb-4">{annulResult}</p>}

      <div className="bg-bg-card rounded-xl border border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-slate-400 text-left">
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
            {items.map((item: any, i: number) => (
              <tr key={i} className="border-b border-slate-700/50 last:border-0">
                <td className="px-4 py-3 font-mono text-xs text-slate-300">{(item.uuid || item.UUID || '').slice(0, 8)}...</td>
                <td className="px-4 py-3 text-white">{item.tipo || item.Tipo || '—'}</td>
                <td className="px-4 py-3 text-slate-400">{item.fecha || item.FechaEmision || '—'}</td>
                <td className="px-4 py-3 text-slate-300">{item.receptor || item.NombreReceptor || '—'}</td>
                <td className="px-4 py-3 text-white">Q{item.total || item.MontoTotal || '—'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs ${(item.estado || item.Estado) === 'A' ? 'bg-red-900/30 text-red-400' : 'bg-green-900/30 text-green-400'}`}>
                    {(item.estado || item.Estado) === 'A' ? 'Anulado' : 'Vigente'}
                  </span>
                </td>
                <td className="px-4 py-3 flex gap-2">
                  <button onClick={() => downloadPdf(item.uuid || item.UUID)} className="text-slate-400 hover:text-blue-400 cursor-pointer" title="PDF"><FileText size={14} /></button>
                  {(item.estado || item.Estado) !== 'A' && (
                    <button onClick={() => annul(item.uuid || item.UUID)} className="text-slate-400 hover:text-red-400 cursor-pointer" title="Anular"><XCircle size={14} /></button>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-500">{loading ? 'Cargando...' : 'Selecciona una cuenta y busca'}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
