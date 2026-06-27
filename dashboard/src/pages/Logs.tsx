import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Search, RefreshCw } from 'lucide-react';

export default function Logs() {
  const [logs, setLogs] = useState<any[]>([]);
  const [filter, setFilter] = useState({ action: '', account_nit: '' });
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const params: Record<string, string> = { limit: '100' };
      if (filter.action) params.action = filter.action;
      if (filter.account_nit) params.account_nit = filter.account_nit;
      setLogs(await api.logs.list(params));
    } catch {
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-white">Audit Log</h2>
        <button onClick={load} disabled={loading} className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm disabled:opacity-50 cursor-pointer">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Actualizar
        </button>
      </div>

      <div className="flex gap-3 mb-4">
        <input value={filter.action} onChange={e => setFilter({ ...filter, action: e.target.value })} placeholder="Filtrar por acción..." className="px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm w-48" />
        <input value={filter.account_nit} onChange={e => setFilter({ ...filter, account_nit: e.target.value })} placeholder="Filtrar por NIT..." className="px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm w-48" />
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm cursor-pointer">
          <Search size={16} /> Filtrar
        </button>
      </div>

      <div className="bg-bg-card rounded-xl border border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-slate-400 text-left">
              <th className="px-4 py-3">Fecha</th>
              <th className="px-4 py-3">Acción</th>
              <th className="px-4 py-3">NIT</th>
              <th className="px-4 py-3">Key</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Duración</th>
              <th className="px-4 py-3">Fuente</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log: any) => (
              <tr key={log.id} className="border-b border-slate-700/50 last:border-0">
                <td className="px-4 py-3 text-slate-400 text-xs">{log.timestamp}</td>
                <td className="px-4 py-3 text-white font-mono text-xs">{log.action}</td>
                <td className="px-4 py-3 text-slate-300 font-mono text-xs">{log.account_nit || '—'}</td>
                <td className="px-4 py-3 text-slate-500 text-xs">{log.api_key_prefix || '—'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs ${log.response_status < 300 ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
                    {log.response_status}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-400 text-xs">{log.duration_ms}ms</td>
                <td className="px-4 py-3 text-slate-400 text-xs">{log.source || '—'}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-500">Sin registros</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
