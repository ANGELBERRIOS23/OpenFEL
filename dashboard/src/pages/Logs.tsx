import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Search, RefreshCw } from 'lucide-react';
import { useTheme } from '../lib/useThemeClasses';

export default function Logs() {
  const t = useTheme();
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
        <h2 className={`text-xl sm:text-2xl font-bold ${t.textH}`}>Audit Log</h2>
        <button onClick={load} disabled={loading} className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-lg text-sm disabled:opacity-50 cursor-pointer ${t.btnSecondary}`}>
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Actualizar
        </button>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <input value={filter.action} onChange={e => setFilter({ ...filter, action: e.target.value })} placeholder="Filtrar por acción..." className={`px-3 py-2 border rounded-lg text-sm w-full sm:w-48 ${t.input}`} />
        <input value={filter.account_nit} onChange={e => setFilter({ ...filter, account_nit: e.target.value })} placeholder="Filtrar por NIT..." className={`px-3 py-2 border rounded-lg text-sm w-full sm:w-48 ${t.input}`} />
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm cursor-pointer">
          <Search size={16} /> Filtrar
        </button>
      </div>

      {/* Desktop table */}
      <div className={`rounded-xl border overflow-hidden ${t.card} hidden sm:block`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className={`border-b ${t.border} ${t.textMuted} text-left`}>
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
                <tr key={log.id} className={`border-b ${t.borderSub} last:border-0`}>
                  <td className={`px-4 py-3 ${t.textMuted} text-xs`}>{log.timestamp}</td>
                  <td className={`px-4 py-3 ${t.textH} font-mono text-xs`}>{log.action}</td>
                  <td className={`px-4 py-3 ${t.text} font-mono text-xs`}>{log.account_nit || '—'}</td>
                  <td className={`px-4 py-3 ${t.textXs} text-xs`}>{log.api_key_prefix || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${log.response_status < 300 ? t.badgeGreen : t.badgeRed}`}>
                      {log.response_status}
                    </span>
                  </td>
                  <td className={`px-4 py-3 ${t.textMuted} text-xs`}>{log.duration_ms}ms</td>
                  <td className={`px-4 py-3 ${t.textMuted} text-xs`}>{log.source || '—'}</td>
                </tr>
              ))}
              {logs.length === 0 && (
                <tr><td colSpan={7} className={`px-4 py-8 text-center ${t.textXs}`}>Sin registros</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Mobile cards */}
      <div className={`sm:hidden rounded-xl border ${t.card} divide-y ${t.borderSub}`}>
        {logs.map((log: any) => (
          <div key={log.id} className="p-4 space-y-1">
            <div className="flex justify-between">
              <span className={`${t.textH} font-mono text-xs`}>{log.action}</span>
              <span className={`px-2 py-0.5 rounded text-xs ${log.response_status < 300 ? t.badgeGreen : t.badgeRed}`}>{log.response_status}</span>
            </div>
            <div className={`text-xs ${t.textMuted}`}>{log.timestamp} · {log.duration_ms}ms</div>
            {log.account_nit && <div className={`text-xs ${t.text}`}>NIT: {log.account_nit}</div>}
          </div>
        ))}
        {logs.length === 0 && <p className={`p-4 text-center ${t.textXs}`}>Sin registros</p>}
      </div>
    </div>
  );
}
